"""
Batch runner do Compliance Agent — Indicador de Automação.

Cria 10 minutas de teste, roda o agente em cada uma e calcula a taxa
de automação (Entregável #3 do Projeto 3).

Execução:
    python -m scripts.run_batch

O relatório é salvo em data/logs/batch_report.txt.
"""

import json
import logging
import time
from pathlib import Path

from src.agents.compliance_agent import run_agent

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── Configuração ───────────────────────────────────────────────────────────────
INPUT_DIR   = Path("data/input")
REPORT_PATH = Path("data/logs/batch_report.txt")
SLEEP_SEC   = 15  # pausa entre casos para evitar rate limit do Azure

# ── Casos de teste ─────────────────────────────────────────────────────────────
CASOS = [
    # 4 conservador conforme
    {
        "id": "CLT001", "profile": "conservador",
        "text": "Recomendo CDB de banco grande e Tesouro Selic para a reserva de emergência.",
    },
    {
        "id": "CLT002", "profile": "conservador",
        "text": "Sugiro LCI com liquidez após 90 dias e fundo DI com taxa zero.",
    },
    {
        "id": "CLT003", "profile": "conservador",
        "text": "Indico Tesouro IPCA+ com vencimento em 2 anos e LCA de banco de primeira linha.",
    },
    {
        "id": "CLT004", "profile": "conservador",
        "text": "Proponho alocação 100% em renda fixa: 50% Tesouro Selic e 50% CDB com garantia FGC.",
    },
    # 3 conservador não conforme
    {
        "id": "CLT005", "profile": "conservador",
        "text": "Recomendo alocar 80% da carteira em criptomoedas e ações small cap.",
    },
    {
        "id": "CLT006", "profile": "conservador",
        "text": "Sugiro fundo de ações alavancado com exposição a derivativos e mercado futuro.",
    },
    {
        "id": "CLT007", "profile": "conservador",
        "text": "Indico BDRs de empresas de tecnologia emergente e ETFs internacionais de alto risco.",
    },
    # 2 moderado conforme
    {
        "id": "CLT008", "profile": "moderado",
        "text": "Recomendo fundo multimercado com exposição moderada e mix de 60% renda fixa e 40% ações.",
    },
    {
        "id": "CLT009", "profile": "moderado",
        "text": "Sugiro FII de lajes corporativas consolidadas e debêntures incentivadas.",
    },
    # 1 edge case — produto fora da base (esperado: escalate_human)
    {
        "id": "CLT010", "profile": "moderado",
        "text": "Recomendo investimento em NFTs de arte digital e tokens de carbono fracionados.",
    },
]


# ── Função principal ───────────────────────────────────────────────────────────

def run_batch() -> list:
    """
    Orquestra o batch completo:
    1. Cria minutas de teste em data/input/
    2. Roda o agente para cada uma
    3. Coleta os resultados
    """
    logger.info(f"Iniciando batch com {len(CASOS)} casos.")
    resultados = []

    for i, caso in enumerate(CASOS, 1):
        file_path = criar_minuta(caso)
        logger.info(f"[{i}/{len(CASOS)}] Processando {caso['id']}...")

        try:
            estado = run_agent(file_path)
            resultados.append({
                "id":         caso["id"],
                "profile":    caso["profile"],
                "decision":   estado.get("decision"),
                "confidence": estado.get("analysis", {}).get("confidence_score", 0.0)
                              if estado.get("analysis") else 0.0,
                "error":      estado.get("error"),
            })
        except Exception as exc:
            logger.error(f"Erro em {caso['id']}: {exc}")
            resultados.append({
                "id": caso["id"], "profile": caso["profile"],
                "decision": "error", "confidence": 0.0, "error": str(exc),
            })

        if i < len(CASOS):
            logger.info(f"Aguardando {SLEEP_SEC}s (rate limit)...")
            time.sleep(SLEEP_SEC)

    return resultados


# ── Funções de apoio ───────────────────────────────────────────────────────────

def criar_minuta(caso: dict) -> str:
    """Cria o arquivo JSON da minuta em data/input/ e retorna o caminho."""
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    file_name = f"minuta_{caso['id']}.json"
    path = INPUT_DIR / file_name
    path.write_text(
        json.dumps({
            "client_id":      caso["id"],
            "client_profile": caso["profile"],
            "text":           caso["text"],
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(path)


def gerar_relatorio(resultados: list) -> str:
    """Consolida os resultados do batch e salva em data/logs/batch_report.txt."""
    total        = len(resultados)
    aprovados    = sum(1 for r in resultados if r["decision"] == "approved")
    rejeitados   = sum(1 for r in resultados if r["decision"] == "rejected")
    escalados    = sum(1 for r in resultados if r["decision"] == "escalate_human")
    erros        = sum(1 for r in resultados if r["decision"] == "error")

    automatizados    = aprovados + rejeitados
    taxa_automacao   = (automatizados / total) * 100
    taxa_intervencao = ((escalados + erros) / total) * 100

    linhas = [
        "=" * 60,
        "RELATÓRIO DE AUTOMAÇÃO — COMPLIANCE AGENT",
        "=" * 60,
        "",
        f"Total de minutas processadas : {total}",
        f"Aprovadas automaticamente    : {aprovados}",
        f"Rejeitadas automaticamente   : {rejeitados}",
        f"Escaladas para humano        : {escalados}",
        f"Erros                        : {erros}",
        "",
        f"Taxa de automação            : {taxa_automacao:.1f}%",
        f"Intervenção humana necessária: {taxa_intervencao:.1f}%",
        "",
        "ANTES: 100% de análise manual.",
        f"DEPOIS: {taxa_automacao:.1f}% automatizado, "
        f"{taxa_intervencao:.1f}% requer atenção humana.",
        "",
        "-" * 60,
        "DETALHE POR CASO:",
        "-" * 60,
    ]

    for r in resultados:
        linhas.append(
            f"  {r['id']} | {r['profile']:<12} | "
            f"decisão={r['decision']:<15} | confidence={r['confidence']:.3f}"
        )

    relatorio = "\n".join(linhas)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(relatorio, encoding="utf-8")
    return relatorio


# ── Execução ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    resultados = run_batch()
    relatorio  = gerar_relatorio(resultados)
    print("\n" + relatorio)
    print(f"\nRelatório salvo em: {REPORT_PATH}")