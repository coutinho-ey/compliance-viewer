"""
Este módulo implementa a lógica de análise de conformidade financeira utilizando RAG + LLM.
Integra recuperação de contexto normativo (CVM/ANBIMA) via ChromaDB com geração estruturada
via Azure e OpenAI. Aplica Many-shot, Chain-of-Thought e Prompt Chaining para maximizar
a precisão e rastreabilidade das análises.
"""

import logging
from ..core.llm_client import AzureModel
from ..api.schemas import AnalysisRequest, AnalysisResult
from ..rag.retrieval import retrieve_and_rerank

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.7  # Abaixo disso, dispara o segundo chain

# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
Você é um analista sênior de compliance financeiro da EY FSO (Financial Services Office), \
com profundo conhecimento das normas da CVM e ANBIMA.

Seu papel é analisar recomendações de investimento e verificar se estão em conformidade \
com o perfil de risco do cliente e com a base normativa fornecida.

Regras obrigatórias por perfil:
- CONSERVADOR: aceita apenas renda fixa e fundos de baixo risco. Proibido renda variável, \
derivativos e criptomoedas.
- MODERADO: aceita renda fixa, fundos balanceados e até 30% em renda variável. Proibido \
derivativos e criptomoedas.
- ARROJADO: aceita todos os produtos, incluindo derivativos e criptomoedas.

Processo de raciocínio obrigatório (Chain-of-Thought):
1. Identifique os produtos financeiros mencionados na recomendação.
2. Verifique cada produto contra as regras do perfil do cliente.
3. Consulte a base normativa fornecida para embasar sua análise.
4. Determine o nível de risco da recomendação.
5. Formule o veredito final com justificativa detalhada.
6. Atribua um confidence_score entre 0.0 e 1.0 indicando sua certeza na análise.

Baseie sua análise exclusivamente nos dados fornecidos e na base normativa.
"""

FEW_SHOT_EXAMPLES = """
Exemplos de análise:

### Exemplo 1 — CONSERVADOR | Conforme
Perfil: conservador
Recomendação: Aplicar 100% em CDB do Banco do Brasil com vencimento em 2 anos.
Análise:
- Produto identificado: CDB (renda fixa).
- CDB é permitido para perfil conservador.
- Risco: baixo.
- Veredito: conforme.
{{
    "is_compliant": true,
    "risk_level": "baixo",
    "reason": "CDB é um instrumento de renda fixa, adequado para perfil conservador.",
    "mentioned_products": ["CDB"],
    "recommendations": [],
    "confidence_score": 0.95
}}

### Exemplo 2 — CONSERVADOR | Não conforme
Perfil: conservador
Recomendação: Alocar 50% em ações da Petrobras e 50% em Tesouro Direto.
Análise:
- Produtos identificados: ações (renda variável) e Tesouro Direto (renda fixa).
- Ações são proibidas para perfil conservador.
- Risco: alto.
- Veredito: não conforme.
{{
    "is_compliant": false,
    "risk_level": "alto",
    "reason": "Ações de renda variável são incompatíveis com perfil conservador.",
    "mentioned_products": ["Ações Petrobras", "Tesouro Direto"],
    "recommendations": ["Substituir ações por renda fixa de baixo risco."],
    "confidence_score": 0.97
}}

### Exemplo 3 — MODERADO | Conforme
Perfil: moderado
Recomendação: 70% em fundos balanceados e 30% em ações de blue chips.
Análise:
- Produtos identificados: fundos balanceados e ações (renda variável).
- Alocação em renda variável dentro do limite de 30%.
- Risco: médio.
- Veredito: conforme.
{{
    "is_compliant": true,
    "risk_level": "médio",
    "reason": "Alocação em renda variável dentro do limite permitido para perfil moderado.",
    "mentioned_products": ["Fundos Balanceados", "Ações Blue Chips"],
    "recommendations": [],
    "confidence_score": 0.90
}}

### Exemplo 4 — MODERADO | Não conforme
Perfil: moderado
Recomendação: Investir 60% em criptomoedas e 40% em renda fixa.
Análise:
- Produtos identificados: criptomoedas e renda fixa.
- Criptomoedas são proibidas para perfil moderado.
- Risco: alto.
- Veredito: não conforme.
{{
    "is_compliant": false,
    "risk_level": "alto",
    "reason": "Criptomoedas são incompatíveis com perfil moderado.",
    "mentioned_products": ["Criptomoedas", "Renda Fixa"],
    "recommendations": ["Substituir criptomoedas por fundos balanceados ou renda fixa."],
    "confidence_score": 0.93
}}

### Exemplo 5 — ARROJADO | Conforme
Perfil: arrojado
Recomendação: 40% em Bitcoin, 30% em opções de ações e 30% em renda fixa.
Análise:
- Produtos identificados: Bitcoin, opções (derivativos) e renda fixa.
- Todos os produtos são permitidos para perfil arrojado.
- Risco: alto.
- Veredito: conforme.
{{
    "is_compliant": true,
    "risk_level": "alto",
    "reason": "Perfil arrojado permite derivativos e criptomoedas. Alocação diversificada.",
    "mentioned_products": ["Bitcoin", "Opções", "Renda Fixa"],
    "recommendations": [],
    "confidence_score": 0.88
}}

### Exemplo 6 — ARROJADO | Não conforme
Perfil: arrojado
Recomendação: Concentrar 100% do patrimônio em um único token de DeFi desconhecido.
Análise:
- Produto identificado: token DeFi (ativo de altíssimo risco e baixa liquidez).
- Concentração total em ativo sem histórico regulatório fere normas ANBIMA.
- Risco: alto.
- Veredito: não conforme.
{{
    "is_compliant": false,
    "risk_level": "alto",
    "reason": "Concentração total em ativo sem regulamentação fere diretrizes ANBIMA de diversificação.",
    "mentioned_products": ["Token DeFi"],
    "recommendations": ["Diversificar portfólio e incluir ativos com maior liquidez e respaldo regulatório."],
    "confidence_score": 0.85
}}
"""

USER_PROMPT_TEMPLATE = """
{few_shot_examples}

---

Agora analise o caso abaixo seguindo o mesmo processo:

PERFIL DO CLIENTE: {client_profile}
RECOMENDAÇÃO: {text}

BASE NORMATIVA RELEVANTE:
{context}
"""

REFINEMENT_PROMPT_TEMPLATE = """
Sua análise anterior teve baixa confiança (confidence_score: {confidence_score:.2f}).

Reavalie com foco nos pontos de incerteza:
- Revise cada produto contra as normas da CVM e ANBIMA fornecidas.
- Seja mais preciso na justificativa.
- Reatribua o confidence_score com base nessa revisão.

PERFIL DO CLIENTE: {client_profile}
RECOMENDAÇÃO: {text}

BASE NORMATIVA RELEVANTE:
{context}
"""

# ── Serviço ───────────────────────────────────────────────────────────────────

def analyze_recommendation(request: AnalysisRequest) -> AnalysisResult:
    llm_client = AzureModel()

    chunks = retrieve_and_rerank(request.text)
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
            logger.info(
                f"Confidence baixo ({result.confidence_score:.2f}). Disparando segundo chain."
            )
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
