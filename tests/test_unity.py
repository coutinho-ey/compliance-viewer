"""
Testes unitários — testa a l[ogica estabelecida, sem o Azure
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from src.api.schemas import AnalysisRequest, AnalysisResult


@pytest.fixture
def conservative_request():
    return AnalysisRequest(
        text="Recomendo alocar 100% do patrimônio em opções alavancadas.",
        client_profile="conservador",
        client_id="cliente-001",
    )

@pytest.fixture
def compliant_request():
    return AnalysisRequest(
        text="Sugiro aplicar em Tesouro Direto e CDB de banco sólido.",
        client_profile="conservador",
        client_id="cliente-002",
    )

def _mock_llm_response(payload: dict):
    message = MagicMock()
    message.content = json.dumps(payload)
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


@patch("src.services.complience_service.AzureModel")
def test_non_compliant(mock_model_cls, conservative_request):
    mock_model_cls.return_value.invoke.return_value = _mock_llm_response({
        "is_compliant": False,
        "risk_level": "alto",
        "reason": "Opções alavancadas são inadequadas para perfil conservador.",
        "mentioned_products": ["opções alavancadas"],
        "recommendations": ["Substituir por Tesouro Direto ou CDB."],
    })
    from src.services.complience_service import analyze_recommendation
    result = analyze_recommendation(conservative_request)
    assert result.is_compliant is False
    assert result.risk_level == "alto"
    assert len(result.mentioned_products) > 0


@patch("src.services.complience_service.AzureModel")
def test_compliant(mock_model_cls, compliant_request):
    mock_model_cls.return_value.invoke.return_value = _mock_llm_response({
        "is_compliant": True,
        "risk_level": "baixo",
        "reason": "Tesouro Direto e CDB são adequados para perfil conservador.",
        "mentioned_products": ["Tesouro Direto", "CDB"],
        "recommendations": [],
    })
    from src.services.complience_service import analyze_recommendation
    result = analyze_recommendation(compliant_request)
    assert result.is_compliant is True
    assert result.risk_level == "baixo"
    assert "Tesouro Direto" in result.mentioned_products


@patch("src.services.complience_service.AzureModel")
def test_invalid_json(mock_model_cls, conservative_request):
    message = MagicMock()
    message.content = "resposta inválida"
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    mock_model_cls.return_value.invoke.return_value = response

    from src.services.complience_service import analyze_recommendation
    result = analyze_recommendation(conservative_request)
    assert result.is_compliant is False
    assert "Falha" in result.reason