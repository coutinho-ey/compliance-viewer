"""
Serviço de análise de conformidade financeira (RAG + LLM).

Orquestra o fluxo completo:
1. RAG FUSION: reescreve a query em múltiplas variações
2. RETRIEVAL: recupera contexto normativo para cada variação e consolida
3. ANÁLISE: monta prompt com contexto + Many-Shot + Chain-of-Thought
4. PROMPT CHAINING: se a confiança for baixa, dispara segundo chain de refino

As regras de compliance NÃO estão no código — vêm da knowledge base via RAG,
permitindo que o agente se auto-atualize quando os documentos mudam.
"""

import logging

from ..core.llm_client import AzureModel
from ..api.schemas import AnalysisRequest, AnalysisResult
from ..rag.retrieval import retrieve_and_rerank, get_azure_client, get_embedding
from ..rag.retrieval import rerank_chunks, get_collection

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.7   # Abaixo disso, dispara o segundo chain
NUM_QUERY_VARIATIONS = 4     # Quantas variações o RAG Fusion gera


# ── Prompts ───────────────────────────────────────────────────────────────────

# O system prompt define COMPORTAMENTO, não CONTEÚDO.
# As regras de cada perfil vêm da base normativa recuperada via RAG.
SYSTEM_PROMPT = """
Você é um analista sênior de compliance financeiro da EY FSO (Financial Services Office).

Seu papel é analisar recomendações de investimento e verificar se estão em conformidade \
com o perfil de risco do cliente, baseando-se EXCLUSIVAMENTE na base normativa fornecida \
no contexto. Não invente regras — se a informação não estiver no contexto, declare isso \
e reduza sua confiança.

Processo de raciocínio obrigatório (Chain-of-Thought):
1. Identifique os produtos financeiros mencionados na recomendação.
2. Localize no contexto normativo as regras aplicáveis ao perfil do cliente.
3. Verifique cada produto contra essas regras.
4. Determine o nível de risco da recomendação.
5. Formule o veredito com justificativa citando a base normativa.
6. Atribua um confidence_score honesto entre 0.0 e 1.0:
   - Alta confiança (0.9+): regras claras e diretamente aplicáveis no contexto.
   - Confiança média (0.6-0.8): regras parcialmente presentes ou caso ambíguo.
   - Baixa confiança (<0.6): contexto insuficiente para decisão segura.
"""

FEW_SHOT_EXAMPLES = """
Exemplos do formato de análise esperado:

### Exemplo A — Conforme
Recomendação adequada ao perfil, produto permitido pela base normativa.
{{
    "is_compliant": true,
    "risk_level": "baixo",
    "reason": "O produto X é permitido para o perfil Y conforme [documento citado].",
    "mentioned_products": ["Produto X"],
    "recommendations": [],
    "confidence_score": 0.93
}}

### Exemplo B — Não conforme
Recomendação inadequada, produto proibido para o perfil pela base normativa.
{{
    "is_compliant": false,
    "risk_level": "alto",
    "reason": "O produto Z é incompatível com o perfil Y conforme [documento citado].",
    "mentioned_products": ["Produto Z"],
    "recommendations": ["Substituir por produto adequado ao perfil."],
    "confidence_score": 0.91
}}

### Exemplo C — Contexto insuficiente
A base normativa não cobre claramente o caso.
{{
    "is_compliant": false,
    "risk_level": "alto",
    "reason": "A base normativa fornecida não contém regras específicas para este produto. Recomenda-se revisão manual.",
    "mentioned_products": ["Produto desconhecido"],
    "recommendations": ["Encaminhar para análise humana especializada."],
    "confidence_score": 0.45
}}
"""

USER_PROMPT_TEMPLATE = """
{few_shot_examples}

---

Analise o caso abaixo seguindo o processo de raciocínio:

PERFIL DO CLIENTE: {client_profile}
RECOMENDAÇÃO: {text}

BASE NORMATIVA RELEVANTE (recuperada da knowledge base):
{context}
"""

REFINEMENT_PROMPT_TEMPLATE = """
Sua análise anterior teve baixa confiança (confidence_score: {confidence_score:.2f}).

Reavalie com atenção redobrada:
- Releia cada trecho da base normativa fornecida.
- Verifique se há regra explícita para cada produto mencionado.
- Se o contexto for realmente insuficiente, mantenha a confiança baixa e recomende análise humana.
- Se encontrar a regra, fundamente melhor e ajuste a confiança.

PERFIL DO CLIENTE: {client_profile}
RECOMENDAÇÃO: {text}

BASE NORMATIVA RELEVANTE:
{context}
"""

QUERY_REWRITE_PROMPT = """
Reescreva a consulta de busca abaixo em {n} variações diferentes, mantendo o mesmo \
significado mas usando termos e formulações distintas. O objetivo é melhorar a recuperação \
de documentos normativos de compliance.

Retorne APENAS as variações, uma por linha, sem numeração ou marcadores.

Consulta original: {query}
"""


# ── RAG Fusion (função de apoio) ───────────────────────────────────────────────

def generate_query_variations(query: str, llm_client: AzureModel, n: int = NUM_QUERY_VARIATIONS) -> list[str]:
    """
    RAG Fusion: pede ao LLM para reescrever a query em N variações semânticas.
    Múltiplas formulações aumentam a cobertura da recuperação.
    Retorna a query original + as variações.
    """
    prompt = QUERY_REWRITE_PROMPT.format(n=n, query=query)
    try:
        response = llm_client.invoke(prompt=prompt)
        raw = response.choices[0].message.content
        variations = [line.strip() for line in raw.split("\n") if line.strip()]
        # Garante a query original na lista e remove duplicatas
        all_queries = [query] + variations
        return list(dict.fromkeys(all_queries))[: n + 1]
    except Exception as exc:
        logger.warning(f"RAG Fusion falhou, usando query original: {exc}")
        return [query]


def fused_retrieval(query: str, llm_client: AzureModel) -> list[dict]:
    """
    Executa RAG Fusion: gera variações da query, recupera chunks para cada uma,
    consolida removendo duplicatas e re-rankeia o conjunto final.
    """
    queries = generate_query_variations(query, llm_client)
    logger.info(f"RAG Fusion: {len(queries)} variações de query geradas.")

    # Recupera para cada variação e consolida por chunk_id único
    seen = {}
    for q in queries:
        for chunk in retrieve_and_rerank(q, top_k_final=5):
            key = f"{chunk['source']}_{chunk['chunk_index']}"
            # Mantém o chunk com maior similaridade caso apareça em múltiplas queries
            if key not in seen or chunk["similarity_score"] > seen[key]["similarity_score"]:
                seen[key] = chunk

    # Re-rankeia o conjunto consolidado contra a query original
    consolidated = list(seen.values())
    reranked = rerank_chunks(query, consolidated)
    return reranked[:3]


# ── Serviço principal ──────────────────────────────────────────────────────────

def analyze_recommendation(request: AnalysisRequest) -> AnalysisResult:
    """
    Pipeline completo de análise de compliance:
    RAG FUSION → RETRIEVAL → ANÁLISE → PROMPT CHAINING
    """
    llm_client = AzureModel()

    # RAG Fusion: recupera contexto a partir de múltiplas variações da query
    chunks = fused_retrieval(request.text, llm_client)
    context = "\n\n".join([c["text"] for c in chunks])

    user_prompt = USER_PROMPT_TEMPLATE.format(
        few_shot_examples=FEW_SHOT_EXAMPLES,
        client_profile=request.client_profile,
        text=request.text,
        context=context,
    )

    try:
        result: AnalysisResult = llm_client.invoke(
            prompt=user_prompt,
            system_prompt=SYSTEM_PROMPT,
            response_model=AnalysisResult,
        )

        # Prompt chaining: baixa confiança dispara análise refinada
        if result.confidence_score < CONFIDENCE_THRESHOLD:
            logger.info(f"Confidence baixo ({result.confidence_score:.2f}). Disparando refino.")
            refinement_prompt = REFINEMENT_PROMPT_TEMPLATE.format(
                confidence_score=result.confidence_score,
                client_profile=request.client_profile,
                text=request.text,
                context=context,
            )
            result = llm_client.invoke(
                prompt=refinement_prompt,
                system_prompt=SYSTEM_PROMPT,
                response_model=AnalysisResult,
            )

        # Rastreabilidade: documentos e chunks usados + score de similaridade
        result.source_documents = list({c["source"] for c in chunks})
        result.source_chunk_ids = [f"{c['source']}_chunk_{c['chunk_index']}" for c in chunks]

        logger.info(
            f"Análise concluída | compliant={result.is_compliant} | "
            f"confidence={result.confidence_score:.2f}"
        )
        return result

    except Exception as exc:
        logger.error("Erro no serviço de compliance: %s", exc)
        raise RuntimeError(f"Falha no serviço de compliance: {exc}") from exc