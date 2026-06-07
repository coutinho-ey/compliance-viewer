"""
Ponto de entrada da API Compliance Checker.

Inicializa o FastAPI, configura middlewares, inclui as rotas
e expõe o endpoint de métricas Prometheus.
"""

import os

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    generate_latest,
    multiprocess,
)

from src.api.router import router

# ── Aplicação ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Compliance Checker API",
    description="Análise automatizada de recomendações de investimento.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/metrics", include_in_schema=False)
def metrics():
    """Expõe métricas Prometheus para scraping."""
    if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/", include_in_schema=False)
def root():
    return {"message": "Welcome to the Compliance Checker API!"}