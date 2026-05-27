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

## Formato de Saída do LLM — json_object

**Status:** Aceito

### Contexto
O LLM pode retornar texto fora do JSON (ex: "Claro! Aqui está:..."), quebrando o parsing.

### Decisão
Usamos `response_format={"type": "json_object"}` na chamada ao Azure OpenAI.

### Justificativa
- Garante que o modelo retorne SOMENTE JSON, sem texto adicional
- Elimina necessidade de heurísticas de parsing (strip, regex)
- Suportado nativamente pelo GPT-4 no Azure

### Alternativa Descartada
**Parsear texto livre com regex** — frágil e dependente de comportamento do modelo que pode mudar entre versões.

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
