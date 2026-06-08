# Solution Design Document (SDD)
# Compliance Viewer

---

## 1. Objetivo

Construir um sistema especialista em compliance financeiro que evolui em três fases com observabilidade de produção:

- **Projeto 1:** API REST com análise via LLM puro
- **Projeto 2:** Pipeline RAG robusto — regras vêm da knowledge base, não do código
- **Projeto 3:** Agente autônomo + observabilidade (OTel + Prometheus + Grafana)

---

## 2. Problema de Negócio

**Contexto:** EY FSO (Financial Services Office) — área de serviços financeiros.

**Dor:** Analistas de compliance revisam manualmente comunicações de investimento para garantir adequação ao perfil de risco do cliente. O processo é lento, caro e sujeito a falhas humanas. Regras hardcoded tornam o sistema difícil de atualizar e impossível de auditar.

**Solução:** Sistema que automatiza a análise de conformidade recuperando trechos normativos oficiais antes de cada inferência, decidindo e agindo de forma autônoma, com rastreabilidade completa e métricas de produção.

---

## 3. Escopo

### Incluído
- Endpoint `POST /api/v1/analyze` para análise de recomendações
- Suporte a 3 perfis de risco: conservador, moderado, arrojado
- Pipeline RAG: RAG Fusion, retrieval e re-ranking híbrido
- Confidence score dinâmico
- Prompt não-estático (regras via RAG, autoatualização)
- Agente autônomo LangGraph com guardrail
- Ferramentas expostas via FastMCP (protocolo MCP)
- OpenTelemetry tracing (FileSpanExporter)
- Prometheus métricas + Grafana dashboard
- Avaliação: notebooks before/after re-ranking + RAGAS com ground truth
- Testes de integração (serviço e agente)
- Indicador de automação (70% em batch de 10 minutas)
- Containerização com Docker

### Melhorias Futuras
- Autenticação e autorização
- Persistência de resultados em banco de dados
- Monitor event-driven (watchdog) em vez de polling
- Cross-encoder para re-ranking mais preciso
- Remoção do ruído da knowledge base (e-mails de cliente)
- Prometheus multiprocess para métricas do agente/monitor

---

## 4. Stack Tecnológica

| Componente | Tecnologia |
|---|---|
| Linguagem | Python 3.11+ |
| Framework | FastAPI |
| Servidor | Uvicorn (ASGI) |
| LLM | Azure OpenAI (GPT-4) |
| Embeddings | Azure OpenAI (text-embedding-ada-002, 1536 dims) |
| Structured Output | Instructor |
| Validação | Pydantic v2 |
| Vector DB | ChromaDB (local, persistente, cosseno) |
| Chunking | LangChain RecursiveCharacterTextSplitter |
| Extração de PDF | pypdf |
| Orquestração de Agente | LangGraph |
| Protocolo de Ferramentas | FastMCP (Model Context Protocol) |
| Avaliação RAG | RAGAS 0.1.21 + datasets + langchain-openai |
| Tracing | OpenTelemetry SDK (FileSpanExporter) |
| Métricas | prometheus-client |
| Dashboard | Grafana + Prometheus (Docker Compose) |
| Containerização | Docker |
| Testes | pytest |

---

## 5. Estrutura do Projeto

```
compliance-viewer/
├── .env                              # Credenciais Azure (não versionado)
├── .gitignore
├── Dockerfile
├── requirements.txt
├── docker-compose.observability.yml  # Stack Prometheus + Grafana
├── prometheus.yml                    # Configuração de scraping
├── src/
│   ├── main.py                       # App FastAPI + endpoint /metrics
│   ├── api/
│   │   ├── router.py                 # Endpoints + record_analysis()
│   │   └── schemas/
│   │       └── analysis.py           # Contratos Pydantic
│   ├── core/
│   │   └── llm_client.py             # Azure OpenAI + OTel span
│   ├── observability/
│   │   ├── __init__.py
│   │   └── observability.py          # OTel tracer + Prometheus metrics
│   ├── services/
│   │   └── complience_service.py     # RAG Fusion + LLM + Confidence Dinâmico
│   ├── rag/
│   │   ├── ingestion.py              # Pipeline de ingestão
│   │   ├── retrieval.py              # Retrieval + re-ranking híbrido
│   └── agents/
│       ├── compliance_agent.py       # Grafo LangGraph + guardrail
│       ├── tools.py                  # Tools com @traced
│       ├── monitor.py                # Loop de vigilância data/input/
│       └── mcp_server.py             # Servidor FastMCP
├── tests/
│   ├── test_unity.py                 # Unitários P1 (mock do LLM)
│   ├── test_integration.py           # Integração P1 (LLM real via TestClient)
│   ├── test_service.py               # Integração do serviço RAG P2 (2 testes)
│   └── test_agent.py                 # Integração do agente LangGraph P3 (3 testes)
├── scripts/
│   └── run_batch.py                  # Batch runner + indicador de automação
├── notebooks/
│   ├── rag_ingestion_explained.ipynb
│   ├── rag_evaluation.ipynb
│   └── rag_ragas_evaluation.ipynb
├── data/                             # Gerado localmente — não versionado
│   ├── chroma_db/
│   ├── input/
│   ├── output/
│   │   ├── approved/
│   │   └── rejected_for_review/
│   └── logs/
│       ├── monitor.log
│       ├── alerts.log
│       ├── traces.log                # Spans OTel
│       └── batch_report.txt
├── docs/
│   ├── architecture.md
│   ├── decisions.md
│   ├── SDD.md
│   └── DEVELOPER_GUIDE.md
└── knowledge_base/
    ├── anbima_codigo_distribuicao_produtos_Investimento.pdf
    ├── resol_030_cvm.pdf
    ├── politica_adequacao_investimento_v1.2.txt
    ├── politica_investimento_agressivo_v1.0.txt
    ├── email_analise_cliente_01.txt
    └── manual_comunicacao_cliente_v1.0.txt
```

---

## 6. Contrato da API

**`POST /api/v1/analyze`**

```json
// Request
{
  "text": "Recomendo alocar 100% em ações da Petrobras.",
  "client_profile": "conservador",
  "client_id": "cliente-001"
}

// Response (200)
{
  "is_compliant": false,
  "risk_level": "alto",
  "reason": "Ações são incompatíveis com perfil conservador conforme Art. 53 do Código ANBIMA.",
  "mentioned_products": ["Ações Petrobras"],
  "recommendations": ["Substituir por Tesouro Direto ou CDB."],
  "source_documents": ["anbima_codigo_distribuicao_produtos_Investimento.pdf"],
  "source_chunk_ids": ["anbima_codigo_distribuicao_produtos_Investimento.pdf_chunk_166"],
  "confidence_score": 0.812
}
```

| Código | Situação |
|---|---|
| 200 | Análise realizada com sucesso |
| 422 | Payload inválido (Pydantic) |
| 502 | Falha na comunicação com o LLM |
| 500 | Erro interno inesperado |

---

## 7. Pipeline RAG (Projeto 2)

### Ingestão
- LangChain RecursiveCharacterTextSplitter (chunk_size=500, overlap=50)
- Azure text-embedding-ada-002 (1536 dims)
- ChromaDB, espaço cosseno, 321 chunks
- `python -m src.rag.ingestion`

### RAG Fusion
- LLM gera 4 variações semânticas da query
- Retrieval para cada variação, consolidação e re-ranking final

### Retrieval e Re-ranking
- TOP_K_RETRIEVAL=10 chunks por busca
- Re-ranking: `0.6 × semântico + 0.4 × lexical`
- TOP_K_FINAL=3 chunks para o prompt

### Confidence Dinâmico
```
confidence = 0.5 × média(similarity_score) + 0.5 × llm_confidence
```

---

## 8. Agente Autônomo (Projeto 3)

| Arquivo | Responsabilidade |
|---|---|
| `tools.py` | 3 ferramentas atômicas com @traced |
| `compliance_agent.py` | Grafo LangGraph + guardrail (confidence < 0.5) |
| `monitor.py` | Polling data/input/ a cada 5s |
| `mcp_server.py` | FastMCP com 3 tools via protocolo MCP |

### Indicador de Automação
- 10 minutas processadas: **70% automação**, 30% intervenção humana, 0 crashes

---

## 9. Observabilidade (Bônus Projeto 3)

### OpenTelemetry Tracing
- `@traced` decorator nas 3 tools de `tools.py`
- Span manual em `llm_client.py` (duração, modelo, tokens, status)
- FileSpanExporter → `data/logs/traces.log`
- Funciona offline, sem dependência de rede

### Prometheus Métricas
- Registradas no processo da API (single-process, sem multiprocess)
- `record_analysis()` chamado no `router.py` após cada `/analyze`
- Expostas via `GET /metrics`

| Métrica | Tipo |
|---|---|
| `compliance_analyses_total` | Counter |
| `compliance_analysis_duration_seconds` | Histogram |
| `compliance_automation_rate` | Gauge |
| `compliance_llm_tokens_total` | Counter |

### Grafana Dashboard
```bash
docker-compose -f docker-compose.observability.yml up -d
# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3000  (admin/compliance123)
```

---

## 10. Tratamento de Erros

| Situação | Camada | Tratamento |
|---|---|---|
| Falha no LLM | service | Lança RuntimeError |
| RuntimeError | api | HTTP 502 |
| Erro inesperado | api | HTTP 500 |
| Payload inválido | api | HTTP 422 (Pydantic) |
| Erro no analyze_document | agente | Capturado, decide → escalate_human |
| JSON inválido na minuta | agente | ValueError capturado, guardrail ativa |

---

## 11. Como Rodar

```bash
# 1. Popular o banco
python -m src.rag.ingestion

# 2. API REST
uvicorn src.main:app --reload

# 3. Agente (terminal separado)
python -m src.agents.monitor

# 4. Batch de automação
python -m scripts.run_batch

# 5. Testes
pytest tests/test_service.py -v -s
pytest tests/test_agent.py -v -s

# 6. Observabilidade
docker-compose -f docker-compose.observability.yml up -d

# 7. Docker (produção)
docker build -t complianceviewer:project3 .
docker run -p 8000:8000 --env-file .env -v $(pwd)/data:/app/data complianceviewer:project3
```