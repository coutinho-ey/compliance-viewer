# Solution Design Document (SDD)
# Projeto 1 — Compliance Viewer

---

## 1. Objetivo

Construir um serviço especialista em formato de API REST que simula um analista de compliance financeiro, fornecendo análise automatizada de recomendações de investimento usando um LLM (Azure OpenAI).

---
 
## 2. Problema de Negócio

**Contexto:** EY FSO (Financial Services Office) — área de serviços financeiros.

**Dor:** Analistas de compliance revisam manualmente comunicações de investimento para garantir adequação ao perfil de risco do cliente. O processo é lento, caro e sujeito a falhas humanas.

**Solução:** API que automatiza a análise inicial, identificando potenciais violações em segundos e liberando o analista para casos mais complexos.

---

## 3. Escopo

### Incluído
- Endpoint `POST /api/v1/analyze` para análise de recomendações
- Suporte a 3 perfis de risco: conservador, moderado, arrojado
- Resposta estruturada com conformidade, nível de risco, produtos mencionados e recomendações
- Documentação automática via Swagger UI
- Testes unitários e de integração
- Containerização com Docker

### Melhorias Futuras
- Consulta a base de conhecimento via RAG
- Agente autônomo para decisões complexas
- Autenticação e autorização
- Persistência de resultados em banco de dados
- Cache de respostas para análises idênticas
- Retry automático para rate limit do Azure

---

## 4. Stack Tecnológica

| Componente | Tecnologia |
|---|---|
| Linguagem | Python 3.11+ |
| Framework | FastAPI |
| Servidor | Uvicorn (ASGI) |
| LLM | Azure OpenAI (GPT-4) |
| Validação | Pydantic v2 |
| Containerização | Docker |
| Testes | pytest + unittest.mock |

---

## 5. Estrutura do Projeto

```
project-1/
├── .env                          # Credenciais Azure (não versionado)
├── .gitignore
├── Dockerfile
├── requirements.txt
├── conftest.py                   # Configuração global do pytest
├── src/
│   ├── __init__.py
│   ├── main.py                   # App FastAPI — ponto de entrada
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py             # Endpoints da API
│   │   └── schemas/
│   │       ├── __init__.py
│   │       └── analysis.py       # Contratos Pydantic (Request/Response)
│   ├── core/
│   │   ├── __init__.py
│   │   └── llm_client.py         # Cliente Azure OpenAI reutilizável
│   ├── services/
│   │   ├── __init__.py
│   │   └── complience_service.py # Lógica de negócio + prompt de compliance
│   ├── rag/                      # Reservado para melhorias futuras
│   └── agents/                   # Reservado para melhorias futuras
├── tests/
│   ├── test_integration.py       # Testes ponta a ponta com LLM real
│   └── test_unit.py              # Testes unitários com mock do LLM
├── data/                         # Dados de entrada/saída
├── docs/                         # Documentação técnica
└── knowledge_base/               # Reservado para melhorias futuras
```

---

## 6. Contrato da API

### Endpoint Principal

**`POST /api/v1/analyze`**

**Request:**
```json
{
  "text": "Recomendo alocar 100% do patrimônio em opções alavancadas.",
  "client_profile": "conservador",
  "client_id": "cliente-001"
}
```

**Response (200):**
```json
{
  "is_compliant": false,
  "risk_level": "alto",
  "reason": "Opções alavancadas são instrumentos de alta volatilidade, incompatíveis com perfil conservador.",
  "mentioned_products": ["opções alavancadas"],
  "recommendations": [
    "Substituir por Tesouro Direto ou CDB de banco sólido.",
    "Revisar processo de suitability com o cliente."
  ]
}
```

### Códigos de Resposta

| Código | Situação |
|---|---|
| 200 | Análise realizada com sucesso |
| 422 | Payload inválido (Pydantic) |
| 502 | Falha na comunicação com o LLM |

### Perfis de Risco Suportados

| Perfil | Produtos aceitos |
|---|---|
| conservador | Renda fixa e fundos de baixo risco |
| moderado | Renda fixa, fundos balanceados e até 30% em renda variável |
| arrojado | Todos os produtos, incluindo derivativos e criptomoedas |

---

## 7. Tratamento de Erros

| Situação | Camada | Tratamento |
|---|---|---|
| JSON inválido do LLM | service | Retorna `AnalysisResult` com `is_compliant=False` e mensagem de falha |
| Erro genérico no service | service | Lança `RuntimeError` |
| RuntimeError no router | api | Retorna HTTP 502 Bad Gateway |
| Payload inválido | api | Pydantic retorna automaticamente HTTP 422 |

---

## 8. Estratégia de Testes

### Testes Unitários (3 testes)
- LLM mockado com `unittest.mock` — sem chamadas reais ao Azure
- Rápidos, sem custo de API e sem dependência de internet
- Cobrem: caso não-conforme, caso conforme, JSON inválido do LLM

### Testes de Integração (4 testes)
- Chamadas reais ao Azure OpenAI via `TestClient` do FastAPI
- Validam o fluxo ponta a ponta com o modelo real
- Cobrem: não-conforme, conforme, health check, payload inválido

**Resultado:** 7 testes passando.

---

## 9. Deploy

### Local (desenvolvimento)
```bash
uvicorn src.main:app --reload
```

### Docker (produção)
```bash
sudo docker build -t compliancechecker:project1 .
sudo docker run -p 8000:8000 --env-file .env compliancechecker:project1
```

> Testado e validado via WSL (Windows Subsystem for Linux).
