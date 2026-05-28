# 🔍 Compliance Viewer

Serviço especialista de análise automatizada de recomendações de investimento, simulando um analista de compliance financeiro com uso de LLM (Azure OpenAI).

---

## 📚 Visão Geral
 
### O Problema
Analistas de compliance gastam horas revisando manualmente comunicações de investimento para garantir a adequação ao perfil de risco do cliente. O processo é lento, caro e sujeito a falhas humanas.

### A Solução
A **Compliance Viewer** automatiza essa análise. O serviço recebe uma recomendação de investimento e o perfil do cliente, e retorna uma análise estruturada indicando se há ou não conformidade — com justificativa, nível de risco e sugestões de ajuste.

### Posição no Programa
Este projeto é a **fundação** do pipeline completo. Algumas pastas já estão estruturadas para receber os próximos projetos:

```
  Projeto 1                Projeto 2            Projeto 3
Compliance Viewer    →    RAG Pipeline   →   Agente Autônomo
     (concluído)             (em breve)           (em breve)
```

> As pastas `src/rag/` e `src/agents/` já existem no repositório como base para os Projetos 2 e 3. Atualmente estão vazias — serão implementadas nas próximas fases.

---

## 🚀 Como Executar Localmente

### 1. Pré-requisitos

- Python 3.11+
- Git
- Credenciais válidas do Azure OpenAI

### 2. Instalação

Clone o repositório e acesse a pasta do projeto:

```bash
git clone https://github.com/coutinho-ey/complience-checker.git
cd complience-checker
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

### 4. Execução

```bash
uvicorn src.main:app --reload
```

Acesse a documentação interativa: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 🐳 Docker

### Build

```bash
sudo docker build -t compliancechecker:project1 .
```

### Run

```bash
sudo docker run -p 8000:8000 --env-file .env compliancechecker:project1
```

Acesse a documentação interativa: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

> ℹ️ Testado e validado via WSL (Windows Subsystem for Linux).

---

## 🗂️ Estrutura de Pastas

```
project-1/
├── .env                          # Credenciais Azure
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
│   ├── rag/                      # Proximas atualizações
│   │   └── __init__.py
│   └── agents/                   # Próximas atualizações 
│       └── __init__.py
├── tests/
│   ├── test_integration.py       # Testes ponta a ponta com LLM 
│   └── test_unit.py              # Testes unitários com mock do LLM
├── data/                         # Dados de entrada/saída
├── docs/
│   └── decisions.md              # Documento de decisões técnicas
└── knowledge_base/               # Base de conhecimento para RAG - proximas atualizações
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
  "text": "Recomendo alocar 100% do patrimônio em opções alavancadas.",
  "client_profile": "conservador",
  "client_id": "cliente-001"
}
```

### Exemplo de Response

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

### Todos os testes

```bash
python -m pytest tests/ -v
```

**Resultado esperado:** 7 testes passando (4 integração + 3 unitários).

---

## 🏛️ Decisões Técnicas

| Decisão | Escolha | Motivo |
|---|---|---|
| Framework | FastAPI | Documentação automática OpenAPI + validação nativa com Pydantic |
| Validação de saída do LLM | Pydantic | Garante contrato rígido — LLMs são não-determinísticos |
| Temperature | 0 | Máximo determinismo — compliance exige consistência e auditabilidade |
| Separação de camadas | services/ desacoplado de api/ | Testabilidade, reutilização e manutenção |
| Formato de saída do LLM | json_object | Elimina texto fora do JSON sem necessidade de heurísticas de parsing |

Para detalhes completos, veja [`docs/decisions.md`](docs/decisions.md).

---

## ✅ Entregáveis

- [x] Endpoint `POST /api/v1/analyze` funcional
- [x] Resposta JSON validada com Pydantic (`is_compliant`, `risk_level`, `reason`, `mentioned_products`, `recommendations`)
- [x] Documentação automática via Swagger UI (`/docs`)
- [x] Schemas Pydantic em `src/api/schemas/`
- [x] Testes unitários e de integração
- [x] Documento de decisões técnicas em `docs/decisions.md`
- [x] Dockerfile funcional — build e run validados via WSL

---

## 🔜 Próximos Passos

| Projeto | Descrição | Pasta base |
|---|---|---|
| Projeto 2 | RAG Pipeline — enriquecer análises com documentos da `knowledge_base/` | `src/rag/` |
| Projeto 3 | Agente Autônomo — orquestrar decisões de compliance sem intervenção humana | `src/agents/` |

---

## 📝 Boas Práticas Adotadas

- Versionamento seguindo **GitFlow** (branches `main`, `develop`, `feature/xxx`)
- **Conventional Commits** para mensagens padronizadas (`feat:`, `docs:`, `test:`)
- `.env` nunca versionado — credenciais protegidas via `.gitignore`
- Separação clara de responsabilidades entre camadas (`api/`, `services/`, `core/`)

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
