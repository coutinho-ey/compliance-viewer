"""
MCP Server do Compliance Agent (FastMCP).

Expõe as ferramentas do agente via Model Context Protocol, permitindo que
outros sistemas se comuniquem com elas de forma estruturada e padronizada.

As mesmas funções de src/agents/tools.py são expostas aqui via @mcp.tool(),
sem duplicar lógica — o MCP server é apenas a interface de protocolo.

Execução: python -m src.agents.mcp_server
"""

from fastmcp import FastMCP

from src.agents.tools import analyze_compliance, create_alert, move_file

mcp = FastMCP(
    name="compliance-agent",
    instructions=(
        "Ferramentas do Compliance Agent para análise de conformidade financeira. "
        "Use analyze_compliance para analisar uma minuta, move_file para mover o "
        "arquivo após a decisão e create_alert para registrar casos que exigem "
        "revisão humana."
    ),
)


@mcp.tool()
def analyze_compliance_tool(file_path: str) -> dict:
    """
    Lê uma minuta de recomendação (JSON) e executa a análise de conformidade
    completa via RAG + LLM.

    Args:
        file_path: Caminho para o arquivo JSON da minuta.

    Returns:
        Dict com is_compliant, risk_level, reason, confidence_score e fontes.
    """
    return analyze_compliance(file_path)


@mcp.tool()
def move_file_tool(file_path: str, destination: str) -> str:
    """
    Move o arquivo de minuta para a pasta de destino.

    Args:
        file_path:   Caminho atual do arquivo.
        destination: "approved" ou "rejected_for_review".

    Returns:
        Caminho final do arquivo movido.
    """
    return move_file(file_path, destination)


@mcp.tool()
def create_alert_tool(file_name: str, reason: str, confidence_score: float) -> str:
    """
    Registra um alerta no log para casos que exigem revisão humana.

    Args:
        file_name:        Nome do arquivo que gerou o alerta.
        reason:           Motivo do alerta.
        confidence_score: Score de confiança da análise (0.0 a 1.0).

    Returns:
        Mensagem de alerta registrada.
    """
    return create_alert(file_name, reason, confidence_score)


if __name__ == "__main__":
    mcp.run()
