"""
Monitor do Compliance Agent.

Vigia o diretório data/input/ e dispara o agente para cada novo arquivo
de minuta (.json) encontrado. Roda em loop contínuo até ser interrompido.

Execução: python -m src.agents.monitor
"""

import logging
import time
from pathlib import Path

from src.agents.compliance_agent import run_agent

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/logs/monitor.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── Configurações ──────────────────────────────────────────────────────────────
INPUT_DIR      = Path("data/input")
POLL_INTERVAL  = 5   # segundos entre cada varredura da pasta


# ── Monitor ────────────────────────────────────────────────────────────────────

def monitor():
    """
    Loop principal: varre data/input/ a cada POLL_INTERVAL segundos.
    Para cada .json encontrado, dispara o agente e aguarda o resultado.
    Arquivos processados são movidos pelo próprio agente — não ficam em input/.
    """
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Monitor iniciado. Vigiando: {INPUT_DIR.resolve()}")
    logger.info(f"Intervalo de varredura: {POLL_INTERVAL}s. Ctrl+C para parar.")

    while True:
        arquivos = sorted(INPUT_DIR.glob("*.json"))

        if arquivos:
            for arquivo in arquivos:
                logger.info(f"Novo arquivo detectado: {arquivo.name}")
                try:
                    estado_final = run_agent(str(arquivo))
                    logger.info(
                        f"Agente concluído | arquivo={arquivo.name} | "
                        f"decisão={estado_final.get('decision')} | "
                        f"resultado={estado_final.get('action_result', '')}"
                    )
                except Exception as exc:
                    logger.error(f"Erro ao processar {arquivo.name}: {exc}")
        else:
            logger.debug("Nenhum arquivo em data/input/. Aguardando...")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    try:
        monitor()
    except KeyboardInterrupt:
        logger.info("Monitor encerrado pelo usuário.")
