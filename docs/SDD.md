# Solution Design Document (SDD)
# Compliance Viewer

---

## 1. Objetivo

Construir um serviço especialista em formato de API REST que simula um analista de compliance financeiro, fornecendo análise automatizada de recomendações de investimento usando RAG (Retrieval-Augmented Generation) + LLM (Azure OpenAI). O sistema recupera contexto normativo relevante da knowledge base antes de cada inferência, garantindo respostas embasadas nas normas da CVM e ANBIMA.

---

## 2. Problema de Negócio

**Contexto:** EY FSO (Financial Services Office) — área de serviços financeiros.

**Dor:** Analistas de compliance revisam manualmente comunicações de investimento para garantir adequação ao perfil de risco do cliente. O processo é lento, caro e sujeito a falhas humanas. Além disso, regras hardcoded no prompt tornam o sistema difícil de atualizar e impossível de auditar — não é possível apontar a cláusula exata da norma que embasou uma decisão.

**Solução:** API que automatiza a análise inicial recuperando trechos normativos oficiais antes de cada inferência, identificando potenciais violações em segundos com rastreabilidade completa das fontes utilizadas.

---

## 3. Escopo

### Incluído
- Endpoint `POST /api/v1/analyze` para análise de recomendações
- Suporte a 3 perfis de risco: conservador, moderado, arrojado
- Pipeline RAG: ingestão, retrieval e re-ranking da knowledge base
- Resposta estruturada com conformidade, risco, produtos, justificativa, fontes e confidence score
- Prompt Engineering: Many-Shot, Chain-of-Thought e Prompt Chaining
- Script de avaliação da qualidade do RAG
- Documentação automática via Swagger UI
- Testes unitários e de integração
- Containerização com Docker

### Melhorias Futuras
- Agente autônomo para decisões complexas (Projeto 3)
- Autenticação e autorização
- Persistência de resultados em banco de dados
- Cache de respostas para análises idênticas
- Retry automático para rate limit do Azure
- Substituição do SimpleEmbedding por modelo semântico quando a rede permitir

---

## 4. Stack Tecnológica

| Componente | Tecnologia |
|---|---|
| Linguagem | Python 3.11+ |
| Framework | FastAPI |
| Servidor | Uvicorn (ASGI) |
| LLM | Azure OpenAI (GPT-4) |
| Structured Output | Instructor |
| Validação | Pydantic v2 |
| Vector DB | ChromaDB (local, persistente) |
| Embeddings | SimpleEmbedding (numpy) |
| Extração de PDF | pypdf |
| Containerização | Docker |
| Testes | pytest + unittest.mock |

---

## 5. Estrutura do Projeto

```
compliance-viewer/
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
│   │   ├── router.py             # Endpoints da API + tratamento de erros
│   │   └── schemas/
│   │       ├── __init__.py
│   │       └── analysis.py       # Contratos Pydantic (Request/Response)
│   ├── core/
│   │   ├── __init__.py
│   │   └── llm_client.py         # Cliente Azure OpenAI com structured output
│   ├── services/
│   │   ├── __init__.py
│   │   └── complience_service.py # Orquestra RAG + LLM + Prompt Chaining
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── ingestion.py          # Pipeline de ingestão da knowledge base
│   │   ├── retrieval.py          # Retrieval + re-ranking híbrido
│   │   └── evaluate.py           # Avaliação da qualidade do RAG
│   └── agents/                   # Reservado para Projeto 3
│       └── __init__.py
├── tests/
│   ├── test_integration.py       # Testes ponta a ponta com LLM real
│   └── test_unit.py              # Testes unitários com mock do LLM
├── data/
│   ├── chroma_db/                # Base vetorial ChromaDB (gerada pela ingestão)
│   ├── input/
│   └── output/
├── docs/
│   ├── architecture.md
│   ├── decisions.md
│   ├── DEVELOPER_GUIDE.md
│   └── SDD.md
└── knowledge_base/
    ├── anbima_codigo_distribuicao_produtos_Investimento.pdf
    ├── resol_030_cvm.pdf
    ├── email_analise_cliente_01.txt
    ├── manual_comunicacao_cliente_v1.0.txt
    ├── politica_adequacao_investimento_v1.2.txt
    └── politica_investimento_agressivo_v1.0.txt
```

---

## 6. Contrato da API

### Endpoint Principal

**`POST /api/v1/analyze`**

**Request:**
```json
{
  "text": "Recomendo alocar 100% do patrimônio em ações da Petrobras.",
  "client_profile": "conservador",
  "client_id": "cliente-001"
}
```

**Response (200):**
```json
{
  "is_compliant": false,
  "risk_level": "alto",
  "reason": "Ações são instrumentos de renda variável, incompatíveis com perfil conservador.",
  "mentioned_products": ["Ações Petrobras"],
  "recommendations": ["Substituir por Tesouro Direto ou CDB de banco sólido."],
  "source_documents": ["anbima_codigo_distribuicao_produtos_Investimento.pdf"],
  "source_chunk_ids": ["anbima_codigo_distribuicao_produtos_Investimento.pdf_chunk_42"],
  "confidence_score": 0.97
}
```

### Códigos de Resposta

| Código | Situação |
|---|---|
| 200 | Análise realizada com sucesso |
| 422 | Payload inválido (Pydantic) |
| 502 | Falha na comunicação com o LLM |
| 500 | Erro interno inesperado |

### Perfis de Risco Suportados

| Perfil | Produtos aceitos |
|---|---|
| conservador | Renda fixa e fundos de baixo risco |
| moderado | Renda fixa, fundos balanceados e até 30% em renda variável |
| arrojado | Todos os produtos, incluindo derivativos e criptomoedas |

---

## 7. Pipeline RAG

### Ingestão (`src/rag/ingestion.py`)
- Lê todos os `.pdf` e `.txt` da `knowledge_base/`
- Divide em chunks de 500 chars com overlap de 50
- Gera embeddings via `SimpleEmbedding` (numpy, sem downloads externos)
- Persiste no ChromaDB em `data/chroma_db/`
- Execução: `python -m src.rag.ingestion`

### Retrieval (`src/rag/retrieval.py`)
- Busca os 10 chunks mais similares no ChromaDB
- Aplica re-ranking híbrido: 60% semântico + 40% lexical
- Retorna os top 3 chunks para o service

### Prompt Chaining (`complience_service.py`)
- Se `confidence_score < 0.7`, dispara segundo chain de refinamento
- Caso contrário, retorna direto — sem custo extra

---

## 8. Tratamento de Erros

| Situação | Camada | Tratamento |
|---|---|---|
| Falha no retrieval ou LLM | service | Lança `RuntimeError` |
| RuntimeError no router | api | Retorna HTTP 502 Bad Gateway |
| Erro inesperado no router | api | Loga traceback, retorna HTTP 500 |
| Payload inválido | api | Pydantic retorna automaticamente HTTP 422 |

---

## 9. Estratégia de Testes

### Testes Unitários (3 testes)
- LLM mockado com `unittest.mock` — sem chamadas reais ao Azure
- Rápidos, sem custo de API e sem dependência de internet
- Cobrem: caso não-conforme, caso conforme, JSON inválido do LLM

### Testes de Integração (4 testes)
- Chamadas reais ao Azure OpenAI via `TestClient` do FastAPI
- Validam o fluxo ponta a ponta com o modelo real
- Cobrem: não-conforme, conforme, health check, payload inválido

### Avaliação do RAG
- 8 queries de avaliação cobrindo os 3 perfis
- Métricas: Source Hit Rate e Avg Score Global
- Execução: `python -m src.rag.evaluate`

---

## 10. Deploy

### Pré-requisito — Ingestão
```bash
python -m src.rag.ingestion
```

### Local (desenvolvimento)
```bash
uvicorn src.main:app --reload
```

### Docker (produção)
```bash
sudo docker build -t complianceviewer:project2 .
DATA_PATH=$(pwd)/data
sudo docker run -p 8000:8000 --env-file .env -v "$DATA_PATH:/app/data" complianceviewer:project2
```

> O volume `-v` é obrigatório para montar o ChromaDB gerado na ingestão dentro do container.
