from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
 
from src.api.router import router
 
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
 
 
@app.get("/", include_in_schema=False)
def root():
    return {"message": "Welcome to the Compliance Checker API!"}
 
 
@app.get("/metrics", include_in_schema=False)
def metrics():
    """Endpoint Prometheus — expõe métricas de negócio e operacionais."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)