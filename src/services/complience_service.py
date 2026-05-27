# Este módulo implementa a lógica de análise de conformidade financeira utilizando um modelo de linguagem da Azure.

import logging
from ..core.llm_client import AzureModel
from ..api.schemas import AnalysisRequest, AnalysisResult
from ..rag.retrieval import retrieve_and_rerank

logger = logging.getLogger(__name__) 

SYSTEM_PROMPT = """
Você é um analista sênior de compliance financeiro da EY FSO.
Seu papel é verificar se recomendações de investimento estão em conformidade com as normas da CVM e ANBIMA.

Critérios obrigatórios:
- Perfil CONSERVADOR: aceita apenas renda fixa e fundos de baixo risco.
- Perfil MODERADO: aceita renda fixa, fundos balanceados e até 30% em renda variável.
- Perfil ARROJADO: aceita todos os produtos, incluindo derivativos e criptomoedas.

Baseie sua análise exclusivamente no contexto normativo fornecido.
"""

USER_PROMPT_TEMPLATE = """
PERFIL DO CLIENTE: {client_profile}
RECOMENDAÇÃO: {text}

BASE NORMATIVA RELEVANTE:
{context}
"""


def analyze_recommendation(request: AnalysisRequest) -> AnalysisResult:
    llm_client = AzureModel()

    chunks = retrieve_and_rerank(request.text)
    context = "\n\n".join([c["text"] for c in chunks])

    user_prompt = USER_PROMPT_TEMPLATE.format(
        client_profile=request.client_profile,
        text=request.text,
        context=context,
    )

    try:
        result = llm_client.invoke(
            prompt=user_prompt,
            system_prompt=SYSTEM_PROMPT,
            response_model=AnalysisResult,
        )
        result.source_documents = list({c["source"] for c in chunks})
        result.source_chunk_ids = [f"{c['source']}_chunk_{c['chunk_index']}" for c in chunks]
        return result

    except Exception as exc:
        logger.error("Erro no serviço de compliance: %s", exc)
        raise RuntimeError(f"Falha no serviço de compliance: {exc}") from exc