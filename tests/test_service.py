"""
Testes de integração do serviço de compliance (RAG + LLM).

Rodam o pipeline completo (RAG Fusion -> retrieval -> análise -> prompt chaining)
contra o Azure OpenAI real e a knowledge base já ingerida.

Pré-requisitos:
- ChromaDB populado: python -m src.rag.ingestion
- Credenciais Azure no .env

Execução:
    pytest tests/test_service.py -v -s
"""

import pytest

from src.api.schemas import AnalysisRequest
from src.services.complience_service import analyze_recommendation


# ── Testes ─────────────────────────────────────────────────────────────────────

def test_recomendacao_nao_conforme():
    """Cripto + small cap para perfil conservador deve ser NÃO conforme."""
    req = AnalysisRequest(
        text="Recomendo alocar 80% da carteira em criptomoedas e acoes small cap.",
        client_profile="conservador",
    )

    result = analyze_recommendation(req)
    print("\n[NAO CONFORME]\n" + result.model_dump_json(indent=2))

    _assert_resultado_valido(result)
    assert result.is_compliant is False, "Cripto para conservador deveria ser não conforme."


def test_recomendacao_conforme():
    """CDB + Tesouro Selic para perfil conservador deve ser conforme."""
    req = AnalysisRequest(
        text="Sugiro um CDB de banco grande e Tesouro Selic para a reserva.",
        client_profile="conservador",
    )

    result = analyze_recommendation(req)
    print("\n[CONFORME]\n" + result.model_dump_json(indent=2))

    _assert_resultado_valido(result)
    assert result.is_compliant is True, "CDB/Tesouro Selic para conservador deveria ser conforme."


# ── Funções de apoio ───────────────────────────────────────────────────────────

def _assert_resultado_valido(result):
    """Validações estruturais comuns a qualquer análise."""
    assert result.reason,                          "A justificativa (reason) não pode vir vazia."
    assert 0.0 <= result.confidence_score <= 1.0,  "confidence_score fora do intervalo 0-1."
    assert result.source_documents,                "source_documents deve apontar os documentos usados."
    assert result.source_chunk_ids,                "source_chunk_ids deve apontar os chunks usados."