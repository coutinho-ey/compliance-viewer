"""
src/rag/evaluate.py

Script de avaliação do pipeline RAG.
Valida qualidade do retrieval contra queries de compliance reais.

Execução: python -m src.rag.evaluate
"""

from src.rag.retrieval import retrieve_and_rerank

# ── Queries de avaliação ───────────────────────────────────────────────────────
# Cobrem os três perfis (conforme e não conforme) + casos limítrofes
EVAL_QUERIES = [
    {
        "query": "perfil conservador pode investir em renda fixa CDB tesouro direto",
        "expected_sources": ["Anbima_codigo_distribuicao_produtos_investimento.pdf", "analise_de_perfil_do_investidor.txt"],
    },
    {
        "query": "perfil conservador ações renda variável é permitido",
        "expected_sources": ["analise_de_perfil_do_investidor.txt"],
    },
    {
        "query": "perfil moderado limite renda variável fundos balanceados",
        "expected_sources": ["analise_de_perfil_do_investidor.txt"],
    },
    {
        "query": "perfil moderado criptomoedas derivativos permitido",
        "expected_sources": ["analise_de_perfil_do_investidor.txt"],
    },
    {
        "query": "perfil arrojado derivativos opções futuros criptoativos",
        "expected_sources": ["analise_de_perfil_do_investidor.txt"],
    },
    {
        "query": "suitability adequação produto investidor normas CVM",
        "expected_sources": ["resol_030_cvm.pdf", "analise_de_perfil_do_investidor.txt"],
    },
    {
        "query": "distribuição produtos investimento obrigações distribuidor ANBIMA",
        "expected_sources": ["Anbima_codigo_distribuicao_produtos_investimento.pdf"],
    },
    {
        "query": "concentração patrimônio único ativo risco diversificação",
        "expected_sources": ["analise_de_perfil_do_investidor.txt"],
    },
]


# ── Função principal ───────────────────────────────────────────────────────────

def run_evaluation() -> None:
    """
    Roda todas as queries de avaliação e imprime o relatório.
    Chama evaluate_query() para cada item de EVAL_QUERIES.
    """
    print("=" * 60)
    print("Avaliação do Pipeline RAG — Compliance Viewer")
    print("=" * 60)

    results = []
    for item in EVAL_QUERIES:
        result = evaluate_query(item["query"], item["expected_sources"])
        results.append(result)

        status = "✅" if result["source_hit"] else "❌"
        print(f"\n{status} Query: {result['query'][:60]}...")
        print(f"   Top source:  {result['top_source']}")
        print(f"   Avg score:   {result['avg_score']:.4f}")
        print(f"   Fontes retornadas: {result['returned_sources']}")

    total      = len(results)
    hits       = sum(1 for r in results if r["source_hit"])
    avg_global = sum(r["avg_score"] for r in results) / total

    print("\n" + "=" * 60)
    print(f"Source Hit Rate: {hits}/{total} ({(hits/total)*100:.0f}%)")
    print(f"Avg Score Global: {avg_global:.4f}")
    print("=" * 60)


# ── Função de apoio ────────────────────────────────────────────────────────────

def evaluate_query(query: str, expected_sources: list[str]) -> dict:
    """
    Executa o pipeline de retrieval para uma query e calcula métricas:
    - source_hit: ao menos um chunk retornado veio de uma fonte esperada
    - avg_score:  média dos scores finais dos chunks retornados
    - top_source: fonte do chunk com maior score
    """
    results = retrieve_and_rerank(query)

    returned_sources = [r["source"] for r in results]
    scores           = [r["score_final"] for r in results]

    source_hit = any(s in expected_sources for s in returned_sources)
    avg_score  = sum(scores) / len(scores) if scores else 0.0
    top_source = returned_sources[0] if returned_sources else "N/A"

    return {
        "query":            query,
        "source_hit":       source_hit,
        "avg_score":        avg_score,
        "top_source":       top_source,
        "returned_sources": returned_sources,
    }


# ── Execução ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_evaluation()