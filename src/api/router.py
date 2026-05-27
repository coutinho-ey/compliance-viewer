# Este módulo define as rotas da API para análise de conformidade.

import logging
from fastapi import APIRouter, HTTPException, status
from .schemas import AnalysisRequest, AnalysisResult
from ..services.complience_service import analyze_recommendation
 
logger = logging.getLogger(__name__)
  
router = APIRouter(prefix="/api/v1", tags=["Compliance"])
 
@router.post(
    "/analyze",
    response_model=AnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Analisar a recomendação de investimento",
)
def analyze(request: AnalysisRequest) -> AnalysisResult:
    try:
        return analyze_recommendation(request)
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