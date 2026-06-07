# 🔍 Compliance Viewer

Sistema especialista de análise automatizada de recomendações de investimento, combinando **RAG (Retrieval-Augmented Generation)** + **LLM (Azure OpenAI)** + **Agente Autônomo** para simular e automatizar o trabalho de um analista de compliance financeiro embasado em documentos normativos oficiais.

---

## 📚 Visão Geral

### O Problema
Analistas de compliance gastam horas revisando manualmente comunicações de investimento para garantir a adequação ao perfil de risco do cliente. O processo é lento, caro e sujeito a falhas humanas. Além disso, sistemas com regras hardcoded no código não acompanham mudanças normativas sem reimplantação.

### A Solução
O **Compliance Viewer** automatiza esse fluxo em três camadas:

1. **API RAG** — Recebe uma recomendação, recupera trechos normativos relevantes (CVM, ANBIMA, PAI) e retorna análise estruturada com rastreabilidade completa.
2. **Pipeline RAG Robusto** — RAG Fusion, re-ranking híbrido, confidence score dinâmico e regras que se autoatualizam com a knowledge base.
3. **Agente Autônomo** — Monitora uma pasta, analisa cada minuta, decide e age (aprova / rejeita / escala para humano) sem intervenção humana.

### Posição no Programa

```
  Projeto 1                Projeto 2                   Projeto 3
Compliance Viewer    →    RAG Pipeline     →      Agente Autônomo
  (concluído)             (concluído)               (concluído)
```

---

## 🚀 Como Executar Localmente

### 1. Pré-requisitos

- Python 3.11+
- Git
- Credenciais válidas do Azure OpenAI

### 2. Instalação

```bash
git clone https://github.com/coutinho-ey/compliance-viewer.git
cd compliance-viewer

python -m venv .venv

# Windows (Git Bash):
source .venv/Scripts/activate

# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configuração

Crie o arquivo `.env` na raiz do projeto:

```ini
AZURE_OPENAI_ENDPOINT="seu-endpoint-aqui"
AZURE_OPENAI_KEY="sua-chave-aqui"
AZURE_OPENAI_API_VERSION="2024-06-01"
AZURE_DEPLOYMENT_NAME="seu-deployment-name-aqui"
```

> ⚠️ **Nunca versione o `.env`.** Ele já está no `.gitignore`.

### 4. Ingestão da Knowledge Base

Antes de subir a API ou o agente, popule o ChromaDB:

```bash
python -m src.rag.ingestion
```

> Execute sempre que adicionar documentos à `knowledge_base/`. A pasta `data/` (banco vetorial) está no `.gitignore` — cada desenvolvedor precisa gerar localmente.

### 5. API REST

```bash
uvicorn src.main:app --reload
```

Acesse a documentação interativa: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 6. Agente Autônomo

Em um terminal separado:

```bash
python -m src.agents.monitor
```

O monitor varre `data/input/` a cada 5 segundos. Coloque uma minuta `.json` na pasta e o agente processa automaticamente.

**Formato da minuta:**
```json
{
  "client_id": "CLT001",
  "client_profile": "conservador",
  "text": "Recomendo alocar 80% em criptomoedas e ações small cap."
}
```

---

## 🐳 Docker

```bash
# Build
docker build -t complianceviewer:project3 .

# Run
DATA_PATH=$(pwd)/data
docker run -p 8000:8000 --env-file .env -v "$DATA_PATH:/app/data" complianceviewer:project3
```

> O `-v` monta o ChromaDB e os diretórios do agente dentro do container. Rode a ingestão antes do build.

---

## 🗂️ Estrutura de Pastas

```
compliance-viewer/
├── .env                              # Credenciais Azure (não versionado)
├── .gitignore
├── Dockerfile
├── requirements.txt
├── src/
│   ├── main.py                       # App FastAPI — ponto de entrada
│   ├── api/
│   │   ├── router.py                 # Endpoints + tratamento de erros HTTP
│   │   └── schemas/
│   │       └── analysis.py           # Contratos Pydantic (Request/Response)
│   ├── core/
│   │   └── llm_client.py             # Cliente Azure OpenAI + Instructor
│   ├── services/
│   │   └── complience_service.py     # RAG Fusion + LLM + Confidence Dinâmico
│   ├── rag/
│   │   ├── ingestion.py              # Pipeline de ingestão da knowledge base
│   │   ├── retrieval.py              # Retrieval + re-ranking híbrido
│   │   └── evaluate.py              # Avaliação da qualidade do RAG
│   └── agents/
│       ├── compliance_agent.py       # Grafo LangGraph + guardrail
│       ├── tools.py                  # Ferramentas atômicas do agente
│       ├── monitor.py                # Loop de vigilância data/input/
│       └── mcp_server.py             # Servidor FastMCP (protocolo MCP)
├── tests/
│   ├── test_service.py               # Integração do serviço RAG (2 testes)
│   └── test_agent.py                 # Integração do agente LangGraph (3 testes)
├── scripts/
│   └── run_batch.py                  # Batch runner + indicador de automação
├── notebooks/
│   ├── rag_ingestion_explained.ipynb # Didático: pipeline de ingestão passo a passo
│   ├── rag_evaluation.ipynb          # Antes/depois do re-ranking (3 queries)
│   └── rag_ragas_evaluation.ipynb    # Avaliação RAGAS com ground truth
├── data/                             # Gerado localmente — não versionado
│   ├── chroma_db/                    # Base vetorial ChromaDB
│   ├── input/                        # Minutas a processar pelo agente
│   ├── output/
│   │   ├── approved/                 # Minutas aprovadas automaticamente
│   │   └── rejected_for_review/      # Minutas rejeitadas para revisão humana
│   └── logs/
│       ├── monitor.log               # Log do agente em tempo real
│       ├── alerts.log                # Alertas gerados pelo agente
│       └── batch_report.txt          # Relatório do batch de automação
├── docs/
│   ├── architecture.md               # Diagrama e fluxo da arquitetura completa
│   ├── decisions.md                  # Registro de decisões técnicas (ADRs)
│   ├── rag_evaluation.md             # Avaliação antes/depois do re-ranking
│   ├── SDD.md                        # Solution Design Document
│   └── DEVELOPER_GUIDE.md            # Guia do desenvolvedor
└── knowledge_base/
    ├── anbima_codigo_distribuicao_produtos_Investimento.pdf
    ├── resol_030_cvm.pdf
    ├── politica_adequacao_investimento_v1.2.txt
    └── politica_investimento_agressivo_v1.0.txt
```

---

## 🌐 Endpoints

| Método | Rota | Descrição |
|---|---|---|
| POST | `/api/v1/analyze` | Analisa uma recomendação de investimento |
| GET | `/api/v1/health` | Health check da API |

### Exemplo de Request

```json
POST /api/v1/analyze
{
  "text": "Recomendo alocar 100% do patrimônio em ações da Petrobras.",
  "client_profile": "conservador",
  "client_id": "cliente-001"
}
```

### Exemplo de Response

```json
{
  "is_compliant": false,
  "risk_level": "alto",
  "reason": "Ações são instrumentos de renda variável, incompatíveis com perfil conservador conforme Art. 53 do Código ANBIMA.",
  "mentioned_products": ["Ações Petrobras"],
  "recommendations": ["Substituir por Tesouro Direto ou CDB de banco sólido."],
  "source_documents": ["anbima_codigo_distribuicao_produtos_Investimento.pdf"],
  "source_chunk_ids": ["anbima_codigo_distribuicao_produtos_Investimento.pdf_chunk_166"],
  "confidence_score": 0.812
}
```

> O `confidence_score` é **dinâmico**: calculado como 50% da similaridade dos chunks recuperados + 50% da autoavaliação do LLM. Não é um número fixo.

### Perfis de Risco Suportados

| Perfil | Produtos aceitos |
|---|---|
| `conservador` | Renda fixa e fundos de baixo risco |
| `moderado` | Renda fixa, fundos balanceados e até 30% em renda variável |
| `arrojado` | Todos os produtos, incluindo derivativos e criptomoedas |

---

## 🤖 Agente Autônomo

O agente monitora `data/input/`, processa cada minuta e age de acordo com o resultado:

| Decisão | Condição | Ação |
|---|---|---|
| `approved` | `is_compliant=true` e `confidence ≥ 0.5` | Move para `data/output/approved/` |
| `rejected` | `is_compliant=false` e `confidence ≥ 0.5` | Move para `data/output/rejected_for_review/` + alerta |
| `escalate_human` | `confidence < 0.5` ou erro | Alerta em `data/logs/alerts.log` — não move |

**Guardrail:** abaixo de 0.5 de confidence o agente nunca decide sozinho, independente do veredito do LLM.

### Indicador de Automação

Batch de 10 minutas de teste:

| Métrica | Resultado |
|---|---|
| Taxa de automação | **70%** |
| Intervenção humana | 30% |
| Erros / crashes | 0 |

**Antes:** 100% de análise manual.
**Depois:** 70% automatizado, 30% requer atenção humana — zero falhas não tratadas.

Para rodar o batch:
```bash
python -m scripts.run_batch
```

---

## 🧮 Embeddings

O projeto utiliza **Azure OpenAI text-embedding-ada-002** (1536 dimensões, espaço cosseno).

> ⚠️ **Não troque o modelo de embedding sem reingestão completa.** Se o modelo mudar, delete `data/chroma_db/` e rode `python -m src.rag.ingestion` novamente. O vetor de busca e o vetor indexado precisam estar no mesmo espaço.

---

## 🧪 Testes

```bash
# Testa o serviço RAG (calls reais ao Azure)
pytest tests/test_service.py -v -s    # 2 passed

# Testa o agente LangGraph (calls reais ao Azure)
pytest tests/test_agent.py -v -s      # 3 passed

# Avalia o RAG
python -m src.rag.evaluate
```

Os notebooks de avaliação ficam em `notebooks/` e devem ser abertos no Jupyter.

---

## 🏛️ Decisões Técnicas

| Decisão | Escolha | Motivo |
|---|---|---|
| Framework | FastAPI | Documentação OpenAPI automática + validação Pydantic nativa |
| Validação LLM | Instructor + Pydantic | Structured output — elimina json.loads manual |
| Temperature | 0 | Determinismo máximo — compliance exige consistência |
| Vector DB | ChromaDB (cosseno) | Leve, local, similarity_score interpretável (0-1) |
| Embeddings | Azure text-embedding-ada-002 | Semântica real, mesmo provider do LLM, sem SSL issues |
| Chunking | LangChain RecursiveCharacterTextSplitter | Preserva estrutura dos artigos normativos |
| Re-ranking | Híbrido (60% semântico + 40% lexical) | Melhora precisão para vocabulário jurídico específico |
| RAG Fusion | 4 variações de query via LLM | Aumenta cobertura da recuperação |
| Confidence | Dinâmico (retrieval signal + LLM) | Evita score fixo/inventado |
| Agente | LangGraph | Grafo de estados explícito, edges condicionais, rastreável |
| Protocolo tools | FastMCP | Model Context Protocol formal, interoperável |
| Guardrail | confidence < 0.5 → escala | Em compliance, melhor escalar que errar |
| Monitor | Polling 5s | Simples, sem dependência externa |

Para detalhes completos, veja [`docs/decisions.md`](docs/decisions.md).

---

## ✅ Entregáveis

**Projeto 1 — API Base**
- [x] Endpoint `POST /api/v1/analyze` funcional
- [x] Structured output com Instructor + Pydantic
- [x] Many-Shot + Chain-of-Thought + Prompt Chaining
- [x] Documentação Swagger automática
- [x] Dockerfile funcional

**Projeto 2 — RAG Robusto**
- [x] Pipeline de ingestão (`src/rag/ingestion.py`) — 321 chunks
- [x] Azure embedding (text-embedding-ada-002, 1536 dims, cosseno)
- [x] LangChain RecursiveCharacterTextSplitter
- [x] Retrieval + re-ranking híbrido (`src/rag/retrieval.py`)
- [x] RAG Fusion (4 variações de query)
- [x] Confidence score dinâmico
- [x] Prompt não-estático (regras via RAG, autoatualização)
- [x] `source_documents` + `source_chunk_ids` (rastreabilidade)
- [x] Notebook didático de ingestão
- [x] Notebook de avaliação antes/depois do re-ranking
- [x] Avaliação RAGAS com ground truth (4 métricas)
- [x] Testes de integração do serviço (2 testes)
- [x] Diagrama em `docs/architecture.md`

**Projeto 3 — Agente Autônomo**
- [x] Ferramentas atômicas (`src/agents/tools.py`)
- [x] Grafo LangGraph com guardrail (`src/agents/compliance_agent.py`)
- [x] Monitor de diretório (`src/agents/monitor.py`)
- [x] Servidor FastMCP — protocolo MCP formal (`src/agents/mcp_server.py`)
- [x] Logs e rastreabilidade (`data/logs/`)
- [x] Batch runner + indicador de automação (70%)
- [x] Testes de integração do agente (3 testes)
- [x] `docs/decisions.md` atualizado com design do agente e contratos MCP

---

## 📝 Boas Práticas Adotadas

- Versionamento com **GitFlow** (`main`, `develop`, `feature/xxx`)
- **Conventional Commits** (`feat:`, `docs:`, `fix:`, `test:`, `chore:`)
- `.env` nunca versionado — credenciais via `.gitignore`
- `data/` nunca versionada — gerada localmente via ingestão
- Separação clara de responsabilidades entre camadas

---

## 🖇️ Referência

Produzido a partir da estrutura base do Carlos Ribeiro (carlos.ribeiro@br.ey.com).
Repositório base: https://github.com/carlos-augusto-ey/development-program-ai_engineer

---

## 📞 Contato

Davi Fernandes Coutinho — davi.fernandes.coutinho@br.ey.com

---

&copy; 2026 EY FSO — Financial Services Office
