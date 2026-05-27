# Este módulo define os esquemas de dados para as requisições e respostas da análise de conformidade.

from pydantic import BaseModel, Field
from typing import List, Optional

class AnalysisRequest(BaseModel):
    text: str = Field(..., description="Texto da recomendação de investimento.")
    client_profile: str = Field(..., description="Perfil de risco do cliente.")
    client_id: Optional[str] = Field(default=None, description="Indicador opcional do cliente.")

class AnalysisResult(BaseModel):
    is_compliant: bool = Field(..., description="Indica se a recomendação é conforme.")
    risk_level: str = Field(..., description="Nível de risco associado à recomendação.")
    reason: str = Field(..., description="Explicação da análise.")
    mentioned_products: List[str] = Field(..., description="Produtos financeiros recomendados.")
    recommendations: List[str] = Field(default_factory=list, description="Sugestão de ajuste.")
    source_documents: List[str] = Field(default_factory=list, description="Documentos utilizados na análise.")
    source_chunk_ids: List[str] = Field(default_factory=list, description="IDs dos chunks utilizados.") 