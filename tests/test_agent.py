"""
Testes de integração do Compliance Agent.

Rodam o agente completo (LangGraph + tools + RAG + LLM) para um arquivo
de minuta real, validando o fluxo ponta a ponta.

Pré-requisitos:
- ChromaDB populado: python -m src.rag.ingestion
- Credenciais Azure no .env
- Diretórios data/input/, data/output/ criados automaticamente pelas tools

Execução:
    pytest tests/test_agent.py -v -s
"""

import json
from pathlib import Path

import pytest

from src.agents.compliance_agent import run_agent

# ── Configuração ───────────────────────────────────────────────────────────────
INPUT_DIR = Path("data/input")
APPROVED  = Path("data/output/approved")
REJECTED  = Path("data/output/rejected_for_review")


# ── Testes ─────────────────────────────────────────────────────────────────────

def test_agente_rejeita_nao_conforme():
    """
    Cripto/small cap para conservador deve ser rejeitado.
    O arquivo deve ser movido para rejected_for_review/.
    """
    file_name = "minuta_teste_rejeitado.json"
    file_path = _criar_minuta(
        file_name=file_name,
        client_profile="conservador",
        text="Recomendo alocar 80% da carteira em criptomoedas e acoes small cap.",
    )

    try:
        estado = run_agent(file_path)
        print(f"\n[REJEITADO] decisão={estado['decision']} | "
              f"confidence={estado['analysis']['confidence_score']:.3f}")

        assert estado["decision"] == "rejected"
        assert not (INPUT_DIR / file_name).exists(), "Arquivo deveria ter saído de input/."
        assert (REJECTED / file_name).exists(), "Arquivo deveria estar em rejected_for_review/."
    finally:
        _limpar(file_name)


def test_agente_aprova_conforme():
    """
    CDB/Tesouro Selic para conservador deve ser aprovado.
    O arquivo deve ser movido para approved/.
    """
    file_name = "minuta_teste_aprovado.json"
    file_path = _criar_minuta(
        file_name=file_name,
        client_profile="conservador",
        text="Sugiro um CDB de banco grande e Tesouro Selic para a reserva.",
    )

    try:
        estado = run_agent(file_path)
        print(f"\n[APROVADO] decisão={estado['decision']} | "
              f"confidence={estado['analysis']['confidence_score']:.3f}")

        assert estado["decision"] == "approved"
        assert not (INPUT_DIR / file_name).exists(), "Arquivo deveria ter saído de input/."
        assert (APPROVED / file_name).exists(), "Arquivo deveria estar em approved/."
    finally:
        _limpar(file_name)


def test_guardrail_escala_para_humano():
    """
    Arquivo com JSON inválido (sem campos obrigatórios) deve acionar o
    guardrail e escalar para humano sem derrubar o agente.
    """
    file_name = "minuta_teste_invalida.json"
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = INPUT_DIR / file_name
    path.write_text(json.dumps({"campo_errado": "valor"}), encoding="utf-8")

    try:
        estado = run_agent(str(path))
        print(f"\n[GUARDRAIL] decisão={estado['decision']} | erro={estado.get('error')}")

        assert estado["decision"] == "escalate_human"
        assert estado.get("error") is not None
    finally:
        _limpar(file_name)


# ── Funções de apoio ───────────────────────────────────────────────────────────

def _criar_minuta(file_name: str, client_profile: str, text: str) -> str:
    """Cria um arquivo de minuta temporário em data/input/ para o teste."""
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = INPUT_DIR / file_name
    path.write_text(
        json.dumps({"client_id": "TST001", "client_profile": client_profile, "text": text},
                   ensure_ascii=False),
        encoding="utf-8",
    )
    return str(path)


def _limpar(file_name: str):
    """Remove o arquivo de qualquer pasta onde ele possa ter parado."""
    for folder in [INPUT_DIR, APPROVED, REJECTED]:
        target = folder / file_name
        if target.exists():
            target.unlink()