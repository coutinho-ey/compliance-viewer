"""
Teste rodando a logica atribuida e o Azure
"""

import pytest 
from fastapi.testclient import TestClient
from src.main import app    

client = TestClient(app)

def test_analyze_non_compliant():
    "Teste de recomendação de alto risco para perfil conservador, esperando resultado de não conformidade."
    response = client.post("/api/v1/analyze", json={
        "text": "Recomendo alocar 100% do patrimônio em opções alavancadas",
        "client_profile": "conservador",
        "client_id": "teste-001"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["is_compliant"] is False
    assert data["risk_level"] == "alto"
    assert len(data["mentioned_products"]) > 0

def test_analyze_compliant():
    "Teste de recomendação adequada para perfil moderado, esperando resultado de conformidade."
    response = client.post("/api/v1/analyze", json={
        "text": "Recomendo aplicar em Tesouro Direto e CDB de banco sólido",
        "client_profile": "conservador",
        "client_id": "teste-002"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["is_compliant"] is True
    assert data["risk_level"] == "baixo"

def test_health_check():
    "Teste para verificar se a rota de health check está funcionando corretamente."
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_missing_fields():
    "Teste de request de campos ausentes, retornando 422."
    response = client.post("/api/v1/analyze", json={})
    assert response.status_code == 422  # Unprocessable Entity