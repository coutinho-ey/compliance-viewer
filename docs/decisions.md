# Registro de Decisões

---

## Framework Web — FastAPI

**Status:** Aceito

### Contexto
Precisávamos de um framework Python para construir a API REST com documentação automática e validação de dados.

### Decisão
Adotamos o **FastAPI**.

### Justificativa
- Gera documentação OpenAPI/Swagger automaticamente a partir das type hints
- Validação nativa integrada com Pydantic — sem libs adicionais
- Alta performance por ser assíncrono (ASGI)
- Padrão de mercado para APIs Python modernas

### Alternativa Descartada
**Flask** — exige bibliotecas extras para atingir o mesmo resultado, aumentando complexidade sem ganho real.

---

## Validação de Dados — Pydantic

**Status:** Aceito

### Contexto
LLMs são não-determinísticos. A saída pode variar em estrutura entre chamadas, quebrando o consumidor silenciosamente.

### Decisão
Usamos **Pydantic** para validar tanto a entrada (AnalysisRequest) quanto a saída do LLM (AnalysisResult).

### Justificativa
- Qualquer campo ausente ou com tipo errado lança ValidationError imediatamente
- Erros ficam explícitos e tratáveis, nunca silenciosos
- Essencial em contexto regulatório onde auditabilidade é requisito

### Alternativa Descartada
**Parsing manual com json.loads() + if/else** — frágil, verbose e difícil de manter.

---

## Structured Output — Instructor

**Status:** Aceito

### Contexto
O Projeto 1 usava `json.loads()` manual para parsear a resposta do LLM, gerando falsos-negativos silenciosos quando o modelo retornava JSON mal formatado.

### Decisão
Adotamos o **Instructor** para structured output via Pydantic diretamente na chamada ao LLM.

### Justificativa
- Elimina `json.loads()` manual — sem falsos-negativos silenciosos
- O Instructor aplica retry automático se o modelo errar o formato
- O `AnalysisResult` é retornado já validado pelo Pydantic
- Integra nativamente com o cliente Azure OpenAI

### Alternativa Descartada
**response_format={"type": "json_object"}** — garante JSON mas não valida o schema.

---

## Temperature do LLM — 0

**Status:** Aceito

### Contexto
Análise de compliance é uma tarefa regulatória que exige consistência e previsibilidade.

### Decisão
Definimos `temperature=0` na chamada ao Azure OpenAI.

### Justificativa
- Maximiza o determinismo: mesmo input = mesmo output
- Reduz alucinações do modelo
- Torna o sistema auditável — requisito regulatório em FSO

### Alternativa Descartada
**Temperature entre 0.3 e 0.7** — introduz variabilidade desnecessária em análises que precisam ser consistentes.

---

## Separação de Camadas — services/ desacoplado de api/

**Status:** Aceito

### Contexto
Precisávamos de uma arquitetura que permitisse testar a lógica de negócio de forma isolada.

### Decisão
A lógica de negócio vive em `src/services/`, completamente desacoplada da camada HTTP em `src/api/`.

### Justificativa
- Permite testar `analyze_recommendation()` unitariamente sem subir o servidor
- Permite trocar o LLM sem alterar os endpoints
- Facilita reutilização em melhorias futuras

### Alternativa Descartada
**Toda a lógica diretamente no router** — viola o princípio de responsabilidade única e dificulta testes.

---

## Vector DB — ChromaDB Local

**Status:** Aceito

### Contexto
Precisávamos de um banco de dados vetorial para armazenar e consultar os embeddings da knowledge base.

### Decisão
Adotamos o **ChromaDB** em modo persistente local (`data/chroma_db/`).

### Justificativa
- Leve, sem dependência de serviço externo ou infraestrutura cloud
- Persistência em disco — sobrevive a reinicializações do container via volume Docker
- API simples e direta, ideal para o estágio atual do projeto
- Facilmente substituível por um serviço gerenciado (Pinecone, Weaviate) no futuro

### Alternativa Descartada
**FAISS** — não tem persistência nativa. **Pinecone/Weaviate** — dependência externa desnecessária neste estágio.

---

## Embeddings — SimpleEmbedding (numpy)

**Status:** ~~Aceito~~ → **Substituído** — ver *[Projeto 2] Embeddings — Azure OpenAI text-embedding-ada-002*

### Contexto original
O modelo `all-MiniLM-L6-v2` do HuggingFace falha em ambientes corporativos com inspeção SSL (rede EY).

### Por que foi substituído
O SimpleEmbedding produzia scores máximos de 0.38, tornando o re-ranking inefetivo. A migração para Azure OpenAI Embeddings elevou os scores para 0.6–0.75, tornando o RAG semanticamente funcional.

---

## Re-ranking — Híbrido (Semântico + Lexical)

**Status:** Aceito

### Contexto
A busca vetorial por similaridade semântica nem sempre traz os chunks mais relevantes para documentos jurídicos com vocabulário técnico específico.

### Decisão
Aplicamos re-ranking híbrido após o retrieval inicial: **60% semântico + 40% lexical**.

### Justificativa
- Score semântico (distância cosine) captura similaridade de significado
- Score lexical (frequência de termos da query no chunk) captura precisão terminológica
- Documentos jurídicos têm vocabulário técnico que o embedding pode subestimar

### Alternativa Descartada
**Somente busca vetorial** — subótimo para textos normativos com terminologia específica.

---

## Prompt Engineering — Many-Shot + CoT + Chaining

**Status:** Aceito

### Contexto
O prompt do Projeto 1 era simples e sem exemplos, gerando análises inconsistentes em casos limítrofes.

### Decisão
Três técnicas combinadas: **Many-Shot** + **Chain-of-Thought** + **Prompt Chaining** (se `confidence_score < 0.7`, dispara segundo chain de refinamento).

### Justificativa
- Many-Shot ensina o modelo o padrão de análise esperado
- CoT reduz alucinações ao forçar raciocínio passo a passo
- Prompt Chaining garante segunda opinião em casos de baixa confiança

### Alternativa Descartada
**Zero-Shot simples** — inconsistente em casos ambíguos e sem rastreabilidade do raciocínio.

---

## Estratégia de Testes — Integração com LLM Real

**Status:** Aceito

### Decisão
Testes de integração que chamam o Azure OpenAI real: `test_service.py` (2 testes) e `test_agent.py` (3 testes).

### Justificativa
- Valida o fluxo ponta a ponta com o modelo real
- Compliance exige comportamento real, não mockado

---

## [Projeto 2] Embeddings — Azure OpenAI text-embedding-ada-002

**Status:** Aceito

### Contexto
O SimpleEmbedding produzia scores máximos de 0.38, tornando o re-ranking inefetivo. A rede EY bloqueia downloads HuggingFace por SSL, mas permite chamadas à API Azure OpenAI.

### Decisão
Adotar **text-embedding-ada-002** do Azure OpenAI (1536 dimensões, espaço cosseno).

### Justificativa
- Scores saltaram de max 0.38 para 0.6–0.75
- Mesmo provider do LLM — sem nova dependência de rede
- Consistência: mesmo modelo na ingestão e no retrieval

### Alternativa Descartada
**all-MiniLM-L6-v2** — bloqueado por SSL corporativo da EY.

---

## [Projeto 2] Chunking — LangChain RecursiveCharacterTextSplitter

**Status:** Aceito

### Contexto
O chunking precisa preservar o significado das normas, evitando cortes arbitrários no meio de artigos ou cláusulas.

### Decisão
**RecursiveCharacterTextSplitter** do LangChain com `chunk_size=500` e `chunk_overlap=50`.

### Justificativa
- Tenta quebrar primeiro em parágrafos, depois frases, depois palavras — preserva estrutura
- Overlap de 50 chars evita perda de contexto nas bordas
- Resultado: 321 chunks da knowledge base, cobertura completa

### Alternativa Descartada
**Split fixo por número de caracteres** — ignora estrutura do texto.

---

## [Projeto 2] Métrica de Distância — Cosseno no ChromaDB

**Status:** Aceito

### Contexto
O ChromaDB usa distância L2 por padrão. A fórmula `similarity_score = 1 - distance` só produz valores interpretáveis (0 a 1) com distância cosseno.

### Decisão
Configurar a collection com `metadata={"hnsw:space": "cosine"}`.

### Justificativa
- similarity_score cosseno é diretamente interpretável: 0 = sem relação, 1 = idêntico
- Essencial para o confidence dinâmico, que usa a média das similaridades

### Alternativa Descartada
**L2 (padrão do ChromaDB)** — produz distâncias em escala diferente; `1 - distance` não é interpretável da mesma forma.

---

## [Projeto 2] RAG Fusion — Múltiplas Variações de Query

**Status:** Aceito

### Contexto
Uma única formulação da query pode não cobrir todo o vocabulário normativo relevante.

### Decisão
Antes do retrieval, o LLM reescreve a query original em **4 variações semânticas**. O retrieval é executado para cada variação e os chunks são consolidados e re-rankeados contra a query original.

### Justificativa
- Aumenta a cobertura da recuperação sem alterar o pipeline de retrieval
- Diferentes formulações recuperam diferentes chunks relevantes
- Custo adicional controlado: 1 chamada extra ao LLM por análise

### Alternativa Descartada
**Query única** — pode perder chunks relevantes por vocabulário diferente.

---

## [Projeto 2] Confidence Score Dinâmico

**Status:** Aceito

### Contexto
O LLM auto-reportava seu confidence de forma subjetiva, tendendo a valores redondos (0.9, 0.85) desconectados da qualidade real da recuperação.

### Decisão
`confidence = 0.5 × retrieval_signal + 0.5 × llm_confidence`, onde `retrieval_signal` é a média das similaridades dos chunks utilizados.

### Justificativa
- Ancora o score num sinal **objetivo** (qualidade real dos chunks recuperados)
- Mantém a autoavaliação do LLM como sinal **subjetivo**
- Recalculado após o refino do Prompt Chaining

### Alternativa Descartada
**Apenas confidence do LLM** — número inventado sem âncora objetiva.

---

## [Projeto 2] Prompt Não-Estático — Regras via RAG

**Status:** Aceito

### Contexto
No Projeto 1, as regras dos perfis estavam hardcoded no SYSTEM_PROMPT. Atualizar uma norma exigia modificar e reimplantar o código.

### Decisão
O SYSTEM_PROMPT define apenas **comportamento**. As **regras** vêm exclusivamente do contexto recuperado via RAG.

### Justificativa
- Atualizar um documento na knowledge_base e re-ingerir faz o agente se "autoatualizar" sem tocar no código
- Separação clara entre comportamento (estável) e conhecimento (evolutivo)

### Alternativa Descartada
**Regras hardcoded no prompt** — exige manutenção de código para cada atualização normativa.

---

## [Projeto 3] Orquestração do Agente — LangGraph

**Status:** Aceito

### Contexto
O Compliance Agent precisa de um fluxo de estados com decisões condicionais e rastreabilidade de cada etapa.

### Decisão
**LangGraph** como orquestrador do grafo de estados.

### Grafo de Estados
```
[analyze_document] → [decide] →(approved)→ [take_action] → [log_result] → FIM
                              →(rejected)→ [take_action]
                              →(escalate_human)→ [take_action]
```

### Justificativa
- Modelo de estados explícito com responsabilidade única por nó
- Arestas condicionais nativas para roteamento
- Padrão de mercado para agentes multi-step com LangChain ecosystem

### Alternativa Descartada
**Orquestração manual com if/else** — frágil e difícil de expandir.

---

## [Projeto 3] Protocolo de Ferramentas — FastMCP

**Status:** Aceito

### Contexto
O README do Projeto 3 exige o uso do Model Context Protocol (MCP) para comunicação estruturada entre os componentes.

### Decisão
**FastMCP** para expor as ferramentas do agente via protocolo MCP formal.

### Contratos MCP

| Tool | Input | Output |
|---|---|---|
| `analyze_compliance_tool` | `file_path: str` | `dict` com resultado da análise |
| `move_file_tool` | `file_path: str, destination: str` | `str` com caminho final |
| `create_alert_tool` | `file_name: str, reason: str, confidence_score: float` | `str` com mensagem registrada |

### Justificativa
- Padrão aberto: qualquer sistema compatível com MCP pode consumir as ferramentas
- Sem duplicação de lógica: `@mcp.tool()` decora as mesmas funções de `tools.py`

### Alternativa Descartada
**Chamadas Python diretas apenas** — sem protocolo formal, não atende o requisito de MCP.

---

## [Projeto 3] Guardrail — Threshold de Confiança

**Status:** Aceito

### Contexto
O agente não deve tomar decisões autônomas em casos onde a análise é incerta.

### Decisão
Se `confidence_score < 0.5`, o agente escala para **revisão humana**, independente do veredito `is_compliant`.

### Justificativa
- 0.5 é o ponto de equilíbrio entre excesso de escalações e risco de decisões incorretas
- O confidence dinâmico torna esse threshold mais confiável que o antigo score fixo do LLM
- Em compliance, é melhor escalar do que errar

### Alternativa Descartada
**Confiar apenas em `is_compliant`** — ignora a incerteza da análise.

---

## [Projeto 3] Monitor de Diretório — Polling

**Status:** Aceito

### Contexto
O agente precisa de um mecanismo para detectar novos arquivos de minuta em `data/input/`.

### Decisão
Loop de **polling** a cada 5 segundos, implementado como processo separado (`src/agents/monitor.py`).

### Justificativa
- Sem dependências externas além da stdlib Python
- Separado do servidor FastAPI: os dois escalam independentemente
- Intervalo de 5s é suficiente para o volume de minutas esperado

### Alternativa Descartada
**watchdog (file system events)** — dependência adicional sem ganho real no volume atual.

---

## [Bônus] Tracing — OpenTelemetry com FileSpanExporter

**Status:** Aceito

### Contexto
O README do Projeto 3 pede rastreamento de chamadas ao LLM e às ferramentas com OpenTelemetry. A rede corporativa da EY bloqueia por SSL os serviços externos de observabilidade (LangSmith, Arize AI).

### Decisão
OpenTelemetry SDK com **FileSpanExporter** customizado, escrevendo spans em `data/logs/traces.log`. O decorator `@traced` é aplicado às tools e o tracer é usado diretamente no `llm_client.py`.

### Justificativa
- Sem dependência de rede — funciona em qualquer ambiente, incluindo EY
- Instrumentação manual (`@traced`) dá controle total sobre o que é trackeado
- O arquivo de traces é auditável e exportável para qualquer backend OTel

### Alternativa Descartada
**LangSmith** — bloqueado por SSL corporativo da EY (mesmo problema do HuggingFace). **OTLP Collector local** — complexidade de infra desnecessária para o escopo do projeto.

---

## [Bônus] Métricas — Prometheus Single-Process

**Status:** Aceito

### Contexto
O README do Projeto 3 pede métricas de negócio como `automation_success_rate`, `average_analysis_time` e `total_tokens_used`. O agente (monitor) e a API rodam em processos separados, tornando o compartilhamento de métricas complexo.

### Decisão
Métricas Prometheus registradas **no processo da API** (quando `/analyze` é chamado), expostas via `GET /metrics`. O Prometheus multiprocess foi descartado em favor de um modelo simples e confiável.

### Métricas implementadas

| Métrica | Tipo | Descrição |
|---|---|---|
| `compliance_analyses_total` | Counter | Total de análises por resultado e perfil |
| `compliance_analysis_duration_seconds` | Histogram | Duração das análises |
| `compliance_automation_rate` | Gauge | Taxa de automação acumulada |
| `compliance_llm_tokens_total` | Counter | Total de tokens usados |

### Justificativa
- Single-process é simples, previsível e sem risco de conflito entre processos
- O `/analyze` endpoint é o ponto de entrada principal — instrumentá-lo captura o dado mais relevante
- O tracing OTel cobre os dados do monitor/agente

### Alternativa Descartada
**Prometheus multiprocess** — requer `PROMETHEUS_MULTIPROC_DIR` setado antes de qualquer import de prometheus_client, complexidade de configuração em ambiente Windows + Docker, e comportamento imprevisível com a rede EY.

---

## [Bônus] Dashboard — Grafana + Docker Compose

**Status:** Aceito

### Contexto
O README pede um dashboard para visualizar as métricas coletadas.

### Decisão
**Grafana** + **Prometheus** via Docker Compose (`docker-compose.observability.yml`). O Prometheus scrapa `http://host.docker.internal:8000/metrics` (a API FastAPI rodando no host Windows).

### Justificativa
- Grafana é o padrão de mercado para dashboards de observabilidade
- Docker Compose sobe o stack completo com um comando
- `host.docker.internal` resolve o acesso do container ao host Windows

### Alternativa Descartada
**Grafana Cloud** — requer conta e conexão externa. **Grafana instalado localmente** — mais complexo que Docker Compose.