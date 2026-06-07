"""
Compliance Agent — grafo de estados LangGraph.

Fluxo:
    INÍCIO → analyze_document → decide → take_action → log_result → FIM

Guardrail: se confidence_score < GUARDRAIL_THRESHOLD (0.5), o agente
escala para revisão humana independente do veredito — não age sozinho
em casos ambíguos.
"""

import logging
from typing import Optional, TypedDict

from langgraph.graph import END, StateGraph

from src.agents.tools import analyze_compliance, create_alert, move_file

logger = logging.getLogger(__name__)

GUARDRAIL_THRESHOLD = 0.5  # Abaixo disso: escala para humano


# ── Estado do agente ───────────────────────────────────────────────────────────

class ComplianceState(TypedDict):
    file_path:     str
    analysis:      Optional[dict]
    decision:      Optional[str]   # "approved" | "rejected" | "escalate_human"
    action_result: Optional[str]
    error:         Optional[str]


# ── Nós do grafo ───────────────────────────────────────────────────────────────

def analyze_document(state: ComplianceState) -> dict:
    """Nó 1: lê o arquivo e executa a análise de conformidade via RAG + LLM."""
    logger.info(f"[analyze_document] Processando: {state['file_path']}")
    try:
        analysis = analyze_compliance(state["file_path"])
        return {"analysis": analysis, "error": None}
    except Exception as exc:
        logger.error(f"[analyze_document] Erro: {exc}")
        return {"error": str(exc)}


def decide(state: ComplianceState) -> dict:
    """
    Nó 2: decide a ação com base no resultado da análise.

    Guardrail: confidence < GUARDRAIL_THRESHOLD → escala para humano,
    independente do veredito do LLM.
    """
    if state.get("error"):
        return {"decision": "escalate_human"}

    analysis  = state["analysis"]
    confidence   = analysis.get("confidence_score", 0.0)
    is_compliant = analysis.get("is_compliant", False)

    if confidence < GUARDRAIL_THRESHOLD:
        logger.warning(
            f"[decide] Guardrail ativado: confidence={confidence:.3f} "
            f"< {GUARDRAIL_THRESHOLD}. Escalando para humano."
        )
        return {"decision": "escalate_human"}

    decision = "approved" if is_compliant else "rejected"
    logger.info(f"[decide] Decisão: {decision} (confidence={confidence:.3f})")
    return {"decision": decision}


def take_action(state: ComplianceState) -> dict:
    """Nó 3: move o arquivo e cria alerta se necessário."""
    decision   = state["decision"]
    analysis   = state.get("analysis") or {}
    file_path  = state["file_path"]
    file_name  = analysis.get("file_name", file_path)
    confidence = analysis.get("confidence_score", 0.0)

    if decision == "approved":
        result = move_file(file_path, "approved")
        return {"action_result": f"Aprovado → {result}"}

    elif decision == "rejected":
        result = move_file(file_path, "rejected_for_review")
        alert  = create_alert(
            file_name=file_name,
            reason=analysis.get("reason", "Recomendação não conforme."),
            confidence_score=confidence,
        )
        return {"action_result": f"Rejeitado → {result} | Alerta: {alert}"}

    else:  # escalate_human
        alert = create_alert(
            file_name=file_name,
            reason=state.get("error") or "Confiança baixa — revisão humana obrigatória.",
            confidence_score=confidence,
        )
        return {"action_result": f"Escalado para humano | Alerta: {alert}"}


def log_result(state: ComplianceState) -> dict:
    """Nó 4: registra o resultado final da execução."""
    analysis = state.get("analysis") or {}
    logger.info(
        f"[log_result] CONCLUÍDO | "
        f"arquivo={analysis.get('file_name', state['file_path'])} | "
        f"decisão={state.get('decision')} | "
        f"confidence={analysis.get('confidence_score', 0.0):.3f} | "
        f"resultado={state.get('action_result', '')}"
    )
    return {}


# ── Roteador condicional ───────────────────────────────────────────────────────

def route_decision(state: ComplianceState) -> str:
    return state.get("decision", "escalate_human")


# ── Montagem do grafo ──────────────────────────────────────────────────────────

def build_agent():
    graph = StateGraph(ComplianceState)

    graph.add_node("analyze_document", analyze_document)
    graph.add_node("decide",           decide)
    graph.add_node("take_action",      take_action)
    graph.add_node("log_result",       log_result)

    graph.set_entry_point("analyze_document")
    graph.add_edge("analyze_document", "decide")
    graph.add_conditional_edges(
        "decide",
        route_decision,
        {
            "approved":       "take_action",
            "rejected":       "take_action",
            "escalate_human": "take_action",
        },
    )
    graph.add_edge("take_action", "log_result")
    graph.add_edge("log_result",  END)

    return graph.compile()


# ── Ponto de entrada público ───────────────────────────────────────────────────

def run_agent(file_path: str) -> dict:
    """
    Executa o agente para um arquivo de minuta de recomendação.
    Retorna o estado final com análise, decisão e resultado da ação.
    """
    agent = build_agent()
    initial_state: ComplianceState = {
        "file_path":     file_path,
        "analysis":      None,
        "decision":      None,
        "action_result": None,
        "error":         None,
    }
    return agent.invoke(initial_state)
