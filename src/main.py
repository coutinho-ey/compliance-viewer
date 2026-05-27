from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.router import router

app = FastAPI(
    tittle="Complience Checker API",
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
    return {"message": "Welcome to the Complience Checker API!"}