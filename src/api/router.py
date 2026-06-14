# Este módulo define as rotas da API para análise de conformidade.

import json
import logging
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from .schemas import AnalysisRequest, AnalysisResult
from ..services.complience_service import analyze_recommendation
from ..observability.observability import record_analysis
from ..agents.compliance_agent import build_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Compliance"])

INPUT_DIR = Path("data/input")
INPUT_DIR.mkdir(parents=True, exist_ok=True)


# ── Endpoint original — mantido intacto ───────────────────────────────────────

@router.post(
    "/analyze",
    response_model=AnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Analisar a recomendação de investimento",
)
def analyze(request: AnalysisRequest) -> AnalysisResult:
    start = time.time()
    try:
        result = analyze_recommendation(request)
        record_analysis(
            is_compliant=result.is_compliant,
            client_profile=request.client_profile,
            duration_seconds=time.time() - start,
        )
        return result
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Erro inesperado no endpoint /analyze: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno inesperado.",
        ) from exc


# ── Endpoint novo — agente com streaming SSE ──────────────────────────────────

@router.post(
    "/analyze/agent",
    status_code=status.HTTP_200_OK,
    summary="Analisar via agente autônomo com rastreio em tempo real",
    description=(
        "Grava a requisição em data/input/, reserva o arquivo (.processing), "
        "dispara o agente LangGraph e transmite o estado de cada nó via "
        "Server-Sent Events conforme executa. "
        "Eventos: analyze_document · decide · take_action · log_result · done · error"
    ),
    response_class=StreamingResponse,
)
def analyze_agent(request: AnalysisRequest):
    """
    Fluxo:
        1. Serializa o request em data/input/req_<timestamp>.json
        2. Reserva o arquivo renomeando para .processing (evita colisão com o monitor)
        3. Dispara graph.stream() com o caminho reservado
        4. Emite um evento SSE por nó concluído
        5. Emite evento final 'done' com o estado completo
    """
    # 1. Grava o arquivo em data/input/
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    file_name = f"req_{timestamp}.json"
    file_path = INPUT_DIR / file_name

    payload = {
        "client_id":      request.client_id or f"api_{timestamp}",
        "client_profile": request.client_profile,
        "text":           request.text,
    }

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info(f"[analyze/agent] Arquivo gravado: {file_path}")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao gravar arquivo de entrada: {exc}",
        ) from exc

    # 2. Reserva o arquivo atomicamente — mesmo mecanismo do monitor
    #    Evita que o monitor consuma o arquivo enquanto o endpoint o processa.
    reserved_path = file_path.with_suffix(".processing")
    try:
        file_path.rename(reserved_path)
        logger.info(f"[analyze/agent] Arquivo reservado: {reserved_path.name}")
    except Exception as exc:
        # Se o rename falhar (corrida muito improvável), aborta com erro claro
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao reservar arquivo de entrada: {exc}",
        ) from exc

    # 3. Gerador SSE — cada yield é um evento enviado ao cliente
    def event_stream():
        graph = build_agent()
        initial_state = {
            "file_path":     str(reserved_path),
            "analysis":      None,
            "decision":      None,
            "action_result": None,
            "error":         None,
        }

        accumulated_state = dict(initial_state)
        start = time.time()

        try:
            for step in graph.stream(initial_state):
                node_name, state_delta = next(iter(step.items()))
                if state_delta:
                    accumulated_state.update(state_delta)

                event = {
                    "node":    node_name,
                    "delta":   state_delta,
                    "state":   accumulated_state,
                    "elapsed": round(time.time() - start, 3),
                }

                logger.info(f"[analyze/agent] nó concluído: {node_name} ({event['elapsed']}s)")
                yield _sse("node_complete", event)

            done_event = {
                "file_name":     file_name,
                "decision":      accumulated_state.get("decision"),
                "action_result": accumulated_state.get("action_result"),
                "analysis":      accumulated_state.get("analysis"),
                "total_elapsed": round(time.time() - start, 3),
            }
            yield _sse("done", done_event)

        except Exception as exc:
            logger.exception(f"[analyze/agent] Erro durante streaming: {exc}")
            # Devolve o arquivo pra fila se o agente falhar no meio do caminho
            if reserved_path.exists():
                try:
                    reserved_path.rename(file_path)
                except Exception:
                    pass
            yield _sse("error", {"message": str(exc), "file": file_name})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Health check ──────────────────────────────────────────────────────────────

@router.get("/health", tags=["Infra"], summary="Health check")
def health():
    return {"status": "ok"}


# ── Utilitário SSE ────────────────────────────────────────────────────────────

def _sse(event: str, data: dict) -> str:
    """Formata um evento no protocolo Server-Sent Events."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"