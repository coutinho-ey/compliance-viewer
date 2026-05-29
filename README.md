# 🔍 Compliance Viewer

Serviço especialista de análise automatizada de recomendações de investimento, combinando RAG (Retrieval-Augmented Generation) + LLM (Azure OpenAI) para simular um analista de compliance financeiro embasado em documentos normativos oficiais.

---

## 📚 Visão Geral
 
### O Problema
Analistas de compliance gastam horas revisando manualmente comunicações de investimento para garantir a adequação ao perfil de risco do cliente. O processo é lento, caro e sujeito a falhas humanas.

### A Solução
A **Compliance Viewer** automatiza essa análise. O serviço recebe uma recomendação de investimento e o perfil do cliente, recupera os trechos normativos mais relevantes da knowledge base (CVM, ANBIMA, PAI) e retorna uma análise estruturada com conformidade, nível de risco, justificativa embasada e rastreabilidade das fontes utilizadas.

### Posição no Programa

```
  Projeto 1                Projeto 2            Projeto 3
Compliance Viewer    →    RAG Pipeline   →   Agente Autônomo
  (concluído)             (concluído)          (em breve)
```

---

## 🚀 Como Executar Localmente

### 1. Pré-requisitos

- Python 3.11+
- Git
- Credenciais válidas do Azure OpenAI

### 2. Instalação

Clone o repositório e acesse a pasta do projeto:

```bash
git clone https://github.com/coutinho-ey/compliance-viewer.git
cd compliance-viewer
```

Crie e ative o ambiente virtual:

```bash
python -m venv .venv

# Windows (Git Bash):
source .venv/Scripts/activate

# macOS/Linux:
source .venv/bin/activate
```

Instale as dependências:

```bash
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

Antes de subir a API, é necessário popular o ChromaDB com os documentos normativos:

```bash
python -m src.rag.ingestion
```

> Execute apenas uma vez. Re-execuções são seguras — o upsert evita duplicatas.

### 5. Execução

```bash
uvicorn src.main:app --reload
```

Acesse a documentação interativa: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🐳 Docker

### Build

```bash
sudo docker build -t complianceviewer:project2 .
```

### Run

```bash
DATA_PATH=$(pwd)/data
sudo docker run -p 8000:8000 --env-file .env -v "$DATA_PATH:/app/data" complianceviewer:project2
```

> O `-v` monta o ChromaDB gerado na ingestão dentro do container. Rode a ingestão antes do build.

Acesse a documentação interativa: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

> ℹ️ Testado e validado via WSL (Windows Subsystem for Linux).

---

## 🧮 Embeddings

O projeto utiliza um embedding determinístico e fixo implementado localmente via numpy (`SimpleEmbedding`).

**Por que isso importa:** para que o RAG funcione corretamente, o vetor gerado para uma query na hora da busca precisa estar no mesmo espaço vetorial dos chunks indexados durante a ingestão. Se os embeddings mudarem entre execuções, a busca retorna resultados inconsistentes.

O `SimpleEmbedding` garante isso: dado o mesmo texto, sempre gera o mesmo vetor — sem dependência de modelo externo, sem variação entre execuções.

> ⚠️ **Não troque o método de embedding sem reingestão completa.** Se o `SimpleEmbedding` for substituído por outro modelo, delete `data/chroma_db/` e rode `python -m src.rag.ingestion` novamente para reindexar toda a knowledge base com o novo vetor.

---

## 🗂️ Estrutura de Pastas

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
│   │   └── complience_service.py # Lógica de negócio + RAG + prompts
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── ingestion.py          # Pipeline de ingestão da knowledge base
│   │   ├── retrieval.py          # Recuperação e re-ranking de chunks
│   │   └── evaluate.py           # Avaliação da qualidade do RAG
│   └── agents/                   # Reservado para Projeto 3
│       └── __init__.py
├── tests/
│   ├── test_integration.py       # Testes ponta a ponta com LLM
│   └── test_unit.py              # Testes unitários com mock do LLM
├── data/
│   └── chroma_db/                # Base vetorial ChromaDB (gerada pela ingestão)
├── docs/
│   ├── architecture.md           # Diagrama e fluxo da arquitetura
│   ├── decisions.md              # Registro de decisões técnicas
│   ├── SDD.md                    # Solution Design Document
│   └── DEVELOPER_GUIDE.md        # Guia do desenvolvedor
└── knowledge_base/
    ├── Anbima_codigo_distribuicao_produtos_Investimento.pdf
    ├── resol_030_cvm.pdf
    └── analise_de_perfil_do_investidor.txt
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
  "reason": "Ações são instrumentos de renda variável, incompatíveis com perfil conservador.",
  "mentioned_products": ["Ações Petrobras"],
  "recommendations": ["Substituir por Tesouro Direto ou CDB de banco sólido."],
  "source_documents": ["Anbima_codigo_distribuicao_produtos_Investimento.pdf"],
  "source_chunk_ids": ["Anbima_codigo_distribuicao_produtos_Investimento.pdf_chunk_42"],
  "confidence_score": 0.97
}
```

### Perfis de Risco Suportados

| Perfil | Produtos aceitos |
|---|---|
| `conservador` | Renda fixa e fundos de baixo risco |
| `moderado` | Renda fixa, fundos balanceados e até 30% em renda variável |
| `arrojado` | Todos os produtos, incluindo derivativos e criptomoedas |

---

## 🧪 Testes

### Testes de Integração (chamam o LLM real)

```bash
python -m pytest tests/test_integration.py -v
```

### Testes Unitários (mock do LLM, sem custo de API)

```bash
python -m pytest tests/test_unit.py -v
```

### Avaliação do RAG

```bash
python -m src.rag.evaluate
```

---

## 🏛️ Decisões Técnicas

| Decisão | Escolha | Motivo |
|---|---|---|
| Framework | FastAPI | Documentação automática OpenAPI + validação nativa com Pydantic |
| Validação de saída do LLM | Pydantic + Instructor | Structured output — elimina json.loads manual |
| Temperature | 0 | Máximo determinismo — compliance exige consistência e auditabilidade |
| Vector DB | ChromaDB | Leve, local, sem dependência de serviço externo |
| Embeddings | SimpleEmbedding (numpy) | Sem download externo — compatível com rede corporativa |
| Re-ranking | Híbrido (semântico + lexical) | 60% distância cosine + 40% frequência de termos |
| Prompt Engineering | Many-Shot + CoT + Chaining | Maximiza precisão e rastreabilidade das análises |

Para detalhes completos, veja [`docs/decisions.md`](docs/decisions.md).

---

## ✅ Entregáveis

- [x] Endpoint `POST /api/v1/analyze` funcional com RAG
- [x] Pipeline de ingestão (`src/rag/ingestion.py`) — PDFs e TXTs
- [x] Serviço de retrieval com re-ranking híbrido (`src/rag/retrieval.py`)
- [x] Script de avaliação do RAG (`src/rag/evaluate.py`)
- [x] Resposta JSON com `source_documents`, `source_chunk_ids` e `confidence_score`
- [x] Prompt Chaining com threshold de confiança
- [x] Many-Shot + Chain-of-Thought aplicados
- [x] Documentação automática via Swagger UI (`/docs`)
- [x] Dockerfile funcional com volume para ChromaDB

---

## 🔜 Próximos Passos

| Projeto | Descrição | Pasta base |
|---|---|---|
| Projeto 3 | Agente Autônomo — orquestrar decisões de compliance sem intervenção humana | `src/agents/` |

---

## 📝 Boas Práticas Adotadas

- Versionamento seguindo **GitFlow** (branches `main`, `develop`, `feature/xxx`)
- **Conventional Commits** para mensagens padronizadas (`feat:`, `docs:`, `fix:`)
- `.env` nunca versionado — credenciais protegidas via `.gitignore`
- Separação clara de responsabilidades entre camadas (`api/`, `services/`, `core/`, `rag/`)

---

## 🖇️ Referência

O projeto foi produzido a partir da estrutura feita pelo Carlos Ribeiro (carlos.ribeiro@br.ey.com).
Link do diretório base: https://github.com/carlos-augusto-ey/development-program-ai_engineer

---

## 📞 Contato

Dúvidas ou sugestões:
- Davi Fernandes Coutinho — [davi.fernandes.coutinho@br.ey.com]

---

&copy; 2026 EY FSO — Financial Services Office
