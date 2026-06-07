# Este módulo define as rotas da API para análise de conformidade.

import logging
import time

from fastapi import APIRouter, HTTPException, status

from .schemas import AnalysisRequest, AnalysisResult
from ..services.complience_service import analyze_recommendation
from ..observability.observability import record_analysis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Compliance"])


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


@router.get("/health", tags=["Infra"], summary="Health check")
def health():
    return {"status": "ok"}