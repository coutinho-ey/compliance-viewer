"""
Ferramentas (tools) do Compliance Agent.

Cada função é uma ação atômica que o agente pode executar:
- analyze_compliance: lê uma minuta e analisa a conformidade via RAG + LLM
- move_file:          move o arquivo para approved/ ou rejected_for_review/
- create_alert:       registra um alerta no log de execução

Estas funções são usadas diretamente pelo grafo LangGraph e também
expostas via FastMCP (mcp_server.py) com protocolo formal.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from src.api.schemas import AnalysisRequest, AnalysisResult
from src.services.complience_service import analyze_recommendation

logger = logging.getLogger(__name__)

# ── Caminhos base ──────────────────────────────────────────────────────────────
INPUT_DIR          = Path("data/input")
OUTPUT_APPROVED    = Path("data/output/approved")
OUTPUT_REJECTED    = Path("data/output/rejected_for_review")
LOGS_DIR           = Path("data/logs")
ALERT_LOG          = LOGS_DIR / "alerts.log"

# Garante que os diretórios existam na inicialização do módulo
for _dir in [INPUT_DIR, OUTPUT_APPROVED, OUTPUT_REJECTED, LOGS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)


# ── Tools ──────────────────────────────────────────────────────────────────────

def analyze_compliance(file_path: str) -> dict:
    """
    Lê uma minuta de recomendação (JSON) e executa a análise de conformidade
    completa via RAG + LLM (pipeline do Projeto 2).

    Formato esperado do arquivo:
        {
            "client_id":      "CLT001",
            "client_profile": "conservador",
            "text":           "Texto da recomendação de investimento."
        }

    Retorna um dict com o resultado da análise + metadados do arquivo.
    """
    path = Path(file_path)
    logger.info(f"[analyze_compliance] Lendo arquivo: {path.name}")

    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    required = {"client_id", "client_profile", "text"}
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"Campos ausentes no arquivo {path.name}: {missing}")

    request = AnalysisRequest(
        text=payload["text"],
        client_profile=payload["client_profile"],
        client_id=payload.get("client_id"),
    )

    result: AnalysisResult = analyze_recommendation(request)

    output = result.model_dump()
    output["file_name"]     = path.name
    output["client_id"]     = payload["client_id"]
    output["client_profile"] = payload["client_profile"]

    logger.info(
        f"[analyze_compliance] {path.name} | "
        f"compliant={result.is_compliant} | confidence={result.confidence_score:.3f}"
    )
    return output


def move_file(file_path: str, destination: str) -> str:
    """
    Move o arquivo para a pasta de destino correta.

    destination: "approved" ou "rejected_for_review"

    Retorna o caminho final do arquivo movido.
    """
    path = Path(file_path)

    if destination == "approved":
        dest_dir = OUTPUT_APPROVED
    elif destination == "rejected_for_review":
        dest_dir = OUTPUT_REJECTED
    else:
        raise ValueError(f"Destino inválido: '{destination}'. Use 'approved' ou 'rejected_for_review'.")

    dest_path = dest_dir / path.name
    shutil.move(str(path), str(dest_path))

    logger.info(f"[move_file] {path.name} → {dest_dir.name}/")
    return str(dest_path)


def create_alert(file_name: str, reason: str, confidence_score: float) -> str:
    """
    Registra um alerta no log de execução para casos não conformes ou de
    baixa confiança que exigem revisão humana.

    Retorna a mensagem de alerta registrada.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    alert_line = (
        f"[{timestamp}] ALERTA | arquivo={file_name} | "
        f"confidence={confidence_score:.3f} | motivo={reason}\n"
    )

    with open(ALERT_LOG, "a", encoding="utf-8") as f:
        f.write(alert_line)

    logger.warning(f"[create_alert] {alert_line.strip()}")
    return alert_line.strip()