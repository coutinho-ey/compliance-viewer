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
**Flask** — exige bibliotecas extras (marshmallow, flasgger) para atingir o mesmo resultado, aumentando complexidade sem ganho real.

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
**response_format={"type": "json_object"}** — garante JSON mas não valida o schema. Ainda exige parsing manual e tratamento de campos ausentes.

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
**FAISS** — não tem persistência nativa, exige serialização manual. **Pinecone/Weaviate** — dependência de serviço externo desnecessária neste estágio.

---

## Embeddings — SimpleEmbedding (numpy)

**Status:** Aceito

### Contexto
O modelo `all-MiniLM-L6-v2` do HuggingFace falha em ambientes corporativos com inspeção SSL (rede EY), pois tenta baixar o modelo na inicialização e o certificado corporativo bloqueia a conexão.

### Decisão
Implementamos o **SimpleEmbedding** — função de embedding local baseada em numpy, sem downloads externos.

### Justificativa
- Funciona em qualquer ambiente, incluindo redes corporativas com proxy SSL
- Zero dependências externas além do numpy (já instalado)
- Suficiente para o pipeline RAG funcional com re-ranking híbrido

### Alternativa Descartada
**SentenceTransformerEmbeddingFunction** e **DefaultEmbeddingFunction** — ambas tentam baixar modelos externos na inicialização, incompatível com a rede corporativa da EY.

---

## Re-ranking — Híbrido (Semântico + Lexical)

**Status:** Aceito

### Contexto
A busca vetorial por similaridade semântica nem sempre traz os chunks mais relevantes para documentos jurídicos, que possuem vocabulário técnico específico.

### Decisão
Aplicamos re-ranking híbrido após o retrieval inicial: **60% semântico + 40% lexical**.

### Justificativa
- Score semântico (distância cosine) captura similaridade de significado
- Score lexical (frequência de termos da query no chunk) captura precisão terminológica
- Documentos jurídicos têm vocabulário técnico que o embedding pode subestimar
- A combinação melhora a relevância dos chunks retornados ao LLM

### Alternativa Descartada
**Somente busca vetorial** — suficiente para linguagem natural, mas subótimo para textos normativos com terminologia específica.

---

## Prompt Engineering — Many-Shot + CoT + Chaining

**Status:** Aceito

### Contexto
O prompt do Projeto 1 era simples e sem exemplos, gerando análises inconsistentes em casos limítrofes.

### Decisão
Adotamos três técnicas combinadas:
- **Many-Shot:** 6 exemplos (2 por perfil) com raciocínio explícito
- **Chain-of-Thought:** 6 passos de raciocínio obrigatórios antes do veredito
- **Prompt Chaining:** se `confidence_score < 0.7`, dispara segundo chain de refinamento

### Justificativa
- Many-Shot ensina o modelo o padrão de análise esperado por exemplos concretos
- CoT reduz alucinações ao forçar raciocínio passo a passo
- Prompt Chaining garante segunda opinião em casos de baixa confiança, sem custo extra nos casos claros

### Alternativa Descartada
**Zero-Shot simples** — inconsistente em casos ambíguos e sem rastreabilidade do raciocínio.

---

## Estratégia de Testes — Mock + LLM Real

**Status:** Aceito

### Contexto
Precisávamos de testes confiáveis sem depender sempre de chamadas ao Azure OpenAI.

### Decisão
Dois níveis de teste:
- **Unitários:** LLM mockado com `unittest.mock`
- **Integração:** Chamadas reais ao Azure via `TestClient` do FastAPI

### Justificativa
- Unitários são rápidos, sem custo de API e sem latência
- Integração valida o fluxo ponta a ponta com o modelo real
- Combinação dos dois garante cobertura completa

### Alternativa Descartada
**Sempre testar com o LLM real** — lento, caro e não-determinístico.
