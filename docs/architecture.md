# Arquitetura — Compliance Viewer

---

## Visão Geral

A Compliance Viewer é um serviço especialista construído em FastAPI que utiliza RAG (Retrieval-Augmented Generation) + LLM (Azure OpenAI) para automatizar a análise de conformidade de recomendações de investimento. O sistema recupera contexto normativo relevante da knowledge base antes de cada inferência, garantindo respostas embasadas nas normas da CVM e ANBIMA.

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
│   → Chama o pipeline RAG para recuperar contexto normativo  │
│   → Monta prompt com Many-Shot + Chain-of-Thought           │
│   → Aplica Prompt Chaining via confidence_score             │
│   → Chama o llm_client com structured output                │
└──────────────┬──────────────────────────┬───────────────────┘
               │ chama invoke()           │ chama retrieve_and_rerank()
               ▼                          ▼
┌──────────────────────────┐  ┌──────────────────────────────┐
│       CAMADA CORE        │  │         CAMADA RAG            │
│  src/core/llm_client.py  │  │  src/rag/retrieval.py         │
│  → Conecta Azure OpenAI  │  │  → Busca chunks no ChromaDB   │
│  → Structured output via │  │  → Re-ranking híbrido         │
│    Instructor            │  │    (semântico + lexical)      │
└──────────────┬───────────┘  └──────────────┬───────────────┘
               │ API call (HTTPS)             │ consulta
               ▼                              ▼
┌──────────────────────────┐  ┌──────────────────────────────┐
│      AZURE OPENAI        │  │          CHROMADB             │
│  (GPT-4 — Instructor)    │  │  data/chroma_db/              │
└──────────────────────────┘  └──────────────┬───────────────┘
                                             │ populado por
                                             ▼
                              ┌──────────────────────────────┐
                              │       PIPELINE DE INGESTÃO   │
                              │  src/rag/ingestion.py         │
                              │  → Lê PDFs e TXTs             │
                              │  → Chunking com overlap       │
                              │  → Embeddings via             │
                              │    SentenceTransformers       │
                              └──────────────┬───────────────┘
                                             │ lê
                                             ▼
                              ┌──────────────────────────────┐
                              │       KNOWLEDGE BASE         │
                              │  knowledge_base/              │
                              │  → Resolução CVM 30           │
                              │  → Código ANBIMA              │
                              │  → Política de Adequação PAI  │
                              └──────────────────────────────┘
```

---

## Fluxo de uma Requisição

```
1.  Cliente envia POST /api/v1/analyze com AnalysisRequest
2.  router.py valida o payload com Pydantic
3.  router.py chama analyze_recommendation(request)
4.  complience_service.py chama retrieve_and_rerank(query)
5.  retrieval.py busca os chunks mais relevantes no ChromaDB
6.  retrieval.py aplica re-ranking híbrido e retorna top 3 chunks
7.  complience_service.py monta o prompt com contexto normativo
8.  llm_client.py envia ao Azure OpenAI via Instructor
9.  Azure OpenAI retorna AnalysisResult validado pelo Pydantic
10. Se confidence_score < 0.7, dispara segundo chain de refinamento
11. complience_service.py popula source_documents e source_chunk_ids
12. router.py retorna o AnalysisResult como JSON ao cliente
```

---

## Separação de Camadas

| Camada | Pasta | Responsabilidade |
|---|---|---|
| API | `src/api/` | Receber requisições HTTP, validar entrada/saída, retornar respostas |
| Serviço | `src/services/` | Orquestrar RAG + LLM, aplicar prompt chaining |
| Core | `src/core/` | Infraestrutura — conexão com Azure OpenAI via Instructor |
| RAG | `src/rag/` | Ingestão, retrieval e avaliação da knowledge base |
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
  "recommendations": ["lista de sugestões de ajuste"],
  "source_documents": ["documentos da knowledge base consultados"],
  "source_chunk_ids": ["IDs dos chunks utilizados na análise"],
  "confidence_score": "float entre 0.0 e 1.0"
}
```

---

## Avaliação do RAG

O script `src/rag/evaluate.py` permite validar a qualidade do pipeline de recuperação via linha de comando:

```bash
python -m src.rag.evaluate
```

Métricas geradas:
- Relevância dos chunks recuperados por query
- Distribuição de scores semânticos e lexicais
- Cobertura dos documentos da knowledge base

---

## Melhorias Futuras

A pasta `src/agents/` já está estruturada no repositório e será implementada na próxima fase do programa, aproveitando o pipeline RAG como base para o agente de compliance.
