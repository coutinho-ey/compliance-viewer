# Arquitetura — Compliance Viewer

---

## Visão Geral

A Compliance Viewer é um serviço especialista construído em FastAPI que utiliza um LLM (Azure OpenAI) para automatizar a análise de conformidade de recomendações de investimento.

---

## Diagrama de Arquitetura 

```
┌─────────────────────────────────────────────────────────────┐
│                        CLIENTE                              │
│              (Swagger UI / curl / Agente)                   │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP POST /api/v1/analyze
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     CAMADA DE API                           │
│   src/main.py          → Inicializa FastAPI + middlewares   │
│   src/api/router.py    → Define endpoints e trata HTTP      │
│   src/api/schemas/     → Contratos Pydantic                 │
└─────────────────────────┬───────────────────────────────────┘
                          │ chama analyze_recommendation()
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   CAMADA DE SERVIÇO                         │
│   src/services/complience_service.py                        │
│   → Monta o prompt com regras de compliance por perfil      │
│   → Chama o llm_client                                      │
│   → Parseia e valida a resposta com Pydantic                │
└─────────────────────────┬───────────────────────────────────┘
                          │ chama invoke(prompt)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    CAMADA CORE                              │
│   src/core/llm_client.py (AzureModel)                       │
│   → Carrega credenciais do .env                             │
│   → Conecta ao Azure OpenAI                                 │
│   → Envia o prompt e retorna a resposta                     │
└─────────────────────────┬───────────────────────────────────┘
                          │ API call (HTTPS)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    AZURE OPENAI                             │
│              (GPT-4 — response_format: json)                │
└─────────────────────────────────────────────────────────────┘
```

---

## Fluxo de uma Requisição

```
1. Cliente envia POST /api/v1/analyze com AnalysisRequest
2. router.py valida o payload com Pydantic
3. router.py chama analyze_recommendation(request)
4. complience_service.py monta o prompt com perfil e texto
5. llm_client.py envia o prompt ao Azure OpenAI
6. Azure OpenAI retorna JSON com a análise
7. complience_service.py parseia com json.loads()
8. Pydantic valida e instancia AnalysisResult
9. router.py retorna o AnalysisResult como JSON ao cliente
```

---

## Separação de Camadas

| Camada | Pasta | Responsabilidade |
|---|---|---|
| API | `src/api/` | Receber requisições HTTP, validar entrada/saída, retornar respostas |
| Serviço | `src/services/` | Lógica de negócio — montar prompt, orquestrar chamada ao LLM |
| Core | `src/core/` | Infraestrutura — conexão com Azure OpenAI |
| Schemas | `src/api/schemas/` | Contratos de dados (Pydantic) |

---

## Contratos de Dados

### AnalysisRequest (Entrada)
```json
{
  "text": "texto da recomendação de investimento",
  "client_profile": "conservador | moderado | arrojado",
  "client_id": "identificador do cliente (opcional)"
}
```

### AnalysisResult (Saída)
```json
{
  "is_compliant": "boolean",
  "risk_level": "baixo | médio | alto",
  "reason": "explicação detalhada",
  "mentioned_products": ["lista de produtos identificados"],
  "recommendations": ["lista de sugestões de ajuste"]
}
```

---

## Melhorias Futuras

As pastas `src/rag/` e `src/agents/` já estão estruturadas no repositório e serão implementadas nas próximas fases do programa.
