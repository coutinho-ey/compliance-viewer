# Avaliação do Pipeline RAG — Antes e Depois do Re-ranking

Este documento compara os resultados da busca vetorial **sem re-ranking** (ordem bruta do ChromaDB) vs **com re-ranking** híbrido (semântico + lexical) para 3 queries de compliance.

---

## Metodologia

**Sem re-ranking:** top 3 chunks retornados diretamente pelo ChromaDB, ordenados por distância cosine.

**Com re-ranking:** os mesmos 10 chunks recuperados, reordenados pelo score híbrido:
- 60% score semântico (`1 - distância cosine`)
- 40% score lexical (frequência de termos da query no chunk)

> ⚠️ **Nota sobre embeddings:** O pipeline utiliza `SimpleEmbedding` (numpy), solução adotada por compatibilidade com ambientes corporativos com restrição de SSL. Por ser baseado em caracteres e não em semântica, os scores de similaridade são mais baixos do que seriam com um modelo treinado. O re-ranking léxico compensa parcialmente essa limitação.

---

## Query 1 — Perfil conservador e produtos permitidos

**Query:** `"perfil conservador renda fixa suitability"`

### Sem Re-ranking (ordem bruta do ChromaDB)

| # | Fonte | Chunk | Distância |
|---|---|---|---|
| 1 | `manual_comunicacao_cliente_v1.0.txt` | 1 | 0.6318 |
| 2 | `email_analise_cliente_01.txt` | 2 | 0.7158 |
| 3 | `politica_investimento_agressivo_v1.0.txt` | 3 | 0.7267 |

### Com Re-ranking

| # | Fonte | Chunk | Score Final |
|---|---|---|---|
| 1 | `email_analise_cliente_01.txt` | 2 | 0.3305 |
| 2 | `manual_comunicacao_cliente_v1.0.txt` | 1 | 0.2209 |
| 3 | `anbima_codigo_distribuicao_produtos_Investimento.pdf` | 224 | 0.2032 |

**Diferença:** O re-ranking promoveu o `email_analise_cliente_01.txt` para o topo por conter o termo "Conservador" explicitamente no texto, aumentando o score lexical. Mais relevante: o `anbima_codigo_distribuicao_produtos_Investimento.pdf` entrou no top 3 após o re-ranking — não aparecia na busca bruta — pois contém terminologia normativa alinhada à query.

---

## Query 2 — Restrições para perfil moderado

**Query:** `"perfil moderado criptomoedas derivativos proibido"`

### Sem Re-ranking (ordem bruta do ChromaDB)

| # | Fonte | Chunk | Distância |
|---|---|---|---|
| 1 | `manual_comunicacao_cliente_v1.0.txt` | 1 | 0.4864 |
| 2 | `politica_investimento_agressivo_v1.0.txt` | 3 | 0.6170 |
| 3 | `email_analise_cliente_01.txt` | 2 | 0.6219 |

### Com Re-ranking

| # | Fonte | Chunk | Score Final |
|---|---|---|---|
| 1 | `politica_investimento_agressivo_v1.0.txt` | 3 | 0.3098 |
| 2 | `manual_comunicacao_cliente_v1.0.txt` | 1 | 0.3082 |
| 3 | `email_analise_cliente_01.txt` | 2 | 0.3069 |

**Diferença:** O re-ranking promoveu `politica_investimento_agressivo_v1.0.txt` para o topo, desbancando o `manual_comunicacao_cliente_v1.0.txt` que liderava na busca bruta. O chunk da política contém termos como "Termo de Ciência de Risco Elevado", mais alinhados à query sobre restrições e produtos proibidos.

---

## Query 3 — Adequação normativa CVM

**Query:** `"suitability adequação produto investidor normas CVM resolução"`

### Sem Re-ranking (ordem bruta do ChromaDB)

| # | Fonte | Chunk | Distância |
|---|---|---|---|
| 1 | `politica_investimento_agressivo_v1.0.txt` | 3 | 0.4765 |
| 2 | `manual_comunicacao_cliente_v1.0.txt` | 1 | 0.5354 |
| 3 | `email_analise_cliente_01.txt` | 2 | 0.6045 |

### Com Re-ranking

| # | Fonte | Chunk | Score Final |
|---|---|---|---|
| 1 | `politica_investimento_agressivo_v1.0.txt` | 3 | 0.3808 |
| 2 | `manual_comunicacao_cliente_v1.0.txt` | 1 | 0.3454 |
| 3 | `email_analise_cliente_01.txt` | 2 | 0.3040 |

**Diferença:** Nesta query, o re-ranking confirmou a ordem da busca bruta — os chunks já estavam relativamente bem posicionados. O score lexical reforçou o `politica_investimento_agressivo_v1.0.txt` no topo por conter termos como "risco" e "cliente" presentes na query.

---

## Conclusão

| Métrica | Sem Re-ranking | Com Re-ranking |
|---|---|---|
| Mudanças de posição observadas | — | 2 de 3 queries |
| Novos documentos promovidos ao top 3 | — | 1 (ANBIMA na Query 1) |
| Ordem confirmada | — | 1 de 3 queries |

O re-ranking demonstrou valor mesmo com um embedding de baixa dimensionalidade semântica:

1. **Promoção de fontes normativas** — na Query 1, o `anbima_codigo_distribuicao_produtos_Investimento.pdf` entrou no top 3 apenas após o re-ranking, trazendo uma fonte regulatória que a busca vetorial pura havia ignorado.

2. **Reordenação por relevância terminológica** — na Query 2, o documento com terminologia mais alinhada ao tema (restrições e risco elevado) foi promovido ao topo.

3. **Limitação do embedding atual** — os scores baixos (máximo 0.38) refletem a limitação do `SimpleEmbedding`. A substituição por um modelo semântico treinado (ex: `all-MiniLM-L6-v2` ou Azure OpenAI Embeddings) elevaria significativamente a qualidade do retrieval e os scores finais.
