# Arquitetura — Compliance Viewer

---

## Visão Geral

O Compliance Viewer é um sistema de análise de conformidade financeira composto por três camadas evolutivas com observabilidade integrada:

- **Projeto 1:** API REST com LLM puro
- **Projeto 2:** Pipeline RAG com re-ranking, RAG Fusion e confidence dinâmico
- **Projeto 3:** Agente autônomo + OpenTelemetry + Prometheus + Grafana

---

## Diagrama de Arquitetura Completo

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     CLIENTES / TRIGGERS                                  │
│      Swagger UI / curl           |        Monitor (data/input/)          │
└──────────────┬───────────────────┘──────────────────┬────────────────────┘
               │ HTTP POST /api/v1/analyze             │ arquivo .json
               ▼                                       ▼
┌──────────────────────────────┐   ┌────────────────────────────────────────┐
│        CAMADA DE API         │   │          CAMADA DE AGENTES             │
│  src/main.py                 │   │  src/agents/monitor.py                 │
│  → FastAPI + /metrics        │   │  → Polling data/input/ a cada 5s       │
│  src/api/router.py           │   │  src/agents/compliance_agent.py        │
│  → record_analysis()         │   │  → Grafo LangGraph (4 nós + guardrail) │
│  src/api/schemas/            │   │  src/agents/tools.py                   │
│  → Contratos Pydantic        │   │  → @traced: analyze, move, alert       │
└──────────────┬───────────────┘   │  src/agents/mcp_server.py              │
               │                   │  → FastMCP (protocolo MCP)             │
               └──────────┬────────┘                                        │
                          │ analyze_recommendation()                        │
                          ▼                                                 │
┌─────────────────────────────────────────────────────────────────────────┤
│                       CAMADA DE SERVIÇO                                  │
│  src/services/complience_service.py                                      │
│  → RAG Fusion: 4 variações da query via LLM                              │
│  → fused_retrieval(): consolida chunks de múltiplas queries              │
│  → Prompt (Many-Shot + Chain-of-Thought + contexto normativo)            │
│  → confidence = 0.5×retrieval_signal + 0.5×llm_confidence               │
│  → Prompt Chaining: se confidence < 0.7, dispara refino                  │
│  → Popula source_documents e source_chunk_ids                            │
└──────────────┬──────────────────────────────┬───────────────────────────┘
               │ invoke()                     │ fused_retrieval()
               ▼                              ▼
┌──────────────────────────┐  ┌───────────────────────────────────────────┐
│       CAMADA CORE        │  │               CAMADA RAG                  │
│  src/core/llm_client.py  │  │  src/rag/retrieval.py                     │
│  → Azure OpenAI GPT-4    │  │  → retrieve_chunks(): busca top 10        │
│  → Instructor (structured│  │    no ChromaDB (cosseno)                  │
│    output + retry)       │  │  → rerank_chunks(): 60% semântico          │
│  → OTel span (duração,   │  │    + 40% lexical                          │
│    modelo, tokens)       │  │  → retrieve_and_rerank(): pipeline         │
└──────────────┬───────────┘  │    completo (top 3 final)                 │
               │ HTTPS        └──────────────────┬────────────────────────┘
               ▼                                 │ consulta
┌──────────────────────────┐                     ▼
│      AZURE OPENAI        │  ┌───────────────────────────────────────────┐
│  GPT-4 (LLM)             │  │              CHROMADB                     │
│  text-embedding-ada-002  │  │  data/chroma_db/                          │
│  (Embeddings 1536 dims)  │  │  collection: compliance_docs              │
└──────────────────────────┘  │  métrica: cosseno | 321 chunks            │
                              └──────────────────┬────────────────────────┘
                                                 │ populado por
                                                 ▼
                              ┌───────────────────────────────────────────┐
                              │         PIPELINE DE INGESTÃO              │
                              │  src/rag/ingestion.py                     │
                              │  → LangChain RecursiveCharacterTextSplitter│
                              │    chunk_size=500, overlap=50             │
                              │  → Azure text-embedding-ada-002           │
                              │  → ChromaDB (cosseno)                     │
                              └──────────────────┬────────────────────────┘
                                                 │ lê
                                                 ▼
                              ┌───────────────────────────────────────────┐
                              │            KNOWLEDGE BASE                 │
                              │  → resol_030_cvm.pdf                      │
                              │  → anbima_codigo_distribuicao_...pdf      │
                              │  → politica_adequacao_investimento_v1.2   │
                              │  → politica_investimento_agressivo_v1.0   │
                              │  → email_analise_cliente_01.txt           │
                              │  → manual_comunicacao_cliente_v1.0.txt    │
                              └───────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                        CAMADA DE OBSERVABILIDADE                        │
│                                                                         │
│  src/observability/observability.py                                     │
│  ┌─────────────────────────────┐  ┌──────────────────────────────────┐  │
│  │   OpenTelemetry (Tracing)   │  │   Prometheus (Métricas)          │  │
│  │  @traced nas tools          │  │  compliance_analyses_total        │  │
│  │  span manual no llm_client  │  │  compliance_analysis_duration_s   │  │
│  │  FileSpanExporter           │  │  compliance_automation_rate       │  │
│  │  → data/logs/traces.log     │  │  compliance_llm_tokens_total      │  │
│  └─────────────────────────────┘  └──────────────┬───────────────────┘  │
└──────────────────────────────────────────────────┼──────────────────────┘
                                                   │ GET /metrics
                                                   ▼
                              ┌───────────────────────────────────────────┐
                              │         STACK DE VISUALIZAÇÃO             │
                              │  docker-compose.observability.yml         │
                              │  Prometheus (localhost:9090)               │
                              │  → scrapa host.docker.internal:8000/metrics│
                              │  Grafana (localhost:3000)                  │
                              │  → dashboards com métricas compliance_*   │
                              └───────────────────────────────────────────┘
```

---

## Fluxo de uma Requisição via API

```
1.  Cliente envia POST /api/v1/analyze
2.  router.py valida o payload com Pydantic
3.  router.py inicia timer (para métrica de duração)
4.  analyze_recommendation(request) chamado
5.  RAG Fusion: LLM gera 4 variações da query
6.  fused_retrieval(): chunks para cada variação, consolidação, re-ranking
7.  Prompt montado com contexto normativo + Many-Shot + CoT
8.  llm_client.py: span OTel aberto → chamada Azure OpenAI → span fechado
9.  compute_dynamic_confidence(): 0.5×retrieval + 0.5×llm
10. Se confidence < 0.7 → Prompt Chaining (segundo chain de refino)
11. Popula source_documents e source_chunk_ids
12. router.py chama record_analysis() → métricas Prometheus atualizadas
13. Retorna AnalysisResult ao cliente
```

---

## Fluxo do Agente Autônomo

```
1.  monitor.py varre data/input/ a cada 5 segundos
2.  Arquivo .json detectado → run_agent(file_path)
3.  [analyze_document]: chama analyze_compliance()
    → @traced abre span
    → executa pipeline completo (RAG + LLM)
    → @traced fecha span → registra em traces.log
4.  [decide]: avalia is_compliant + confidence_score
    → confidence < 0.5 (guardrail) → escalate_human
    → is_compliant = true → approved
    → is_compliant = false → rejected
5.  [take_action]: executa + record_agent_decision()
    → approved → move_file() (com @traced)
    → rejected → move_file() + create_alert() (com @traced)
    → escalate_human → create_alert()
6.  [log_result]: registra resultado final
```

---

## Grafo de Estados LangGraph

```
        ┌──────────────────┐
        │ analyze_document  │  ← OTel @traced via tools.py
        └────────┬──────────┘
                 │
        ┌────────▼──────────┐
        │       decide       │  ← guardrail: confidence < 0.5
        └──┬──────────┬───┬──┘
     approved    rejected  escalate_human
           │          │   │
        ┌──▼──────────▼───▼──┐
        │     take_action     │  ← record_agent_decision()
        └────────┬────────────┘
                 │
        ┌────────▼──────────┐
        │    log_result      │
        └────────┬───────────┘
                 │
               [END]
```

---

## Arquitetura das Ferramentas e MCP

```
┌─────────────────────────────────────────────────────────┐
│               src/agents/tools.py                       │
│  (Lógica pura + @traced para OTel)                      │
│                                                         │
│  @traced("tool.analyze_compliance")                     │
│  def analyze_compliance(file_path) → dict               │
│                                                         │
│  @traced("tool.move_file")                              │
│  def move_file(file_path, destination) → str            │
│                                                         │
│  @traced("tool.create_alert")                           │
│  def create_alert(file_name, reason, confidence) → str  │
└──────────────┬──────────────────────────────────────────┘
               │ importado por
       ┌───────┴──────────────────────┐
       │                              │
┌──────▼──────────┐    ┌─────────────▼──────────────────┐
│ compliance_agent│    │       mcp_server.py             │
│ (LangGraph)     │    │  (FastMCP — protocolo MCP)      │
│ Python direto   │    │  @mcp.tool() decora as mesmas   │
└─────────────────┘    │  funções de tools.py            │
                       └────────────────────────────────┘
```

---

## Separação de Camadas

| Camada | Pasta | Responsabilidade |
|---|---|---|
| API | `src/api/` | HTTP, validação Pydantic, métricas Prometheus |
| Agentes | `src/agents/` | Orquestração autônoma, tools, MCP, monitor |
| Serviço | `src/services/` | RAG Fusion, Prompt Engineering, Confidence |
| Core | `src/core/` | Azure OpenAI + Instructor + OTel span |
| RAG | `src/rag/` | Ingestão, retrieval, re-ranking, avaliação |
| Observabilidade | `src/observability/` | OTel tracer, Prometheus metrics, @traced |
| Schemas | `src/api/schemas/` | Contratos de dados Pydantic |

---

## Indicador de Automação

| Métrica | Valor |
|---|---|
| Minutas processadas | 10 |
| Aprovadas automaticamente | 2 |
| Rejeitadas automaticamente | 5 |
| Escaladas para humano | 3 |
| **Taxa de automação** | **70%** |
| Erros / crashes | 0 |

**Antes:** 100% análise manual. **Depois:** 70% automatizado, zero falhas não tratadas.