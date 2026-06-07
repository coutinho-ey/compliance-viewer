"""
Serviço de recuperação de chunks (Retrieval).

Fluxo:
1. Gera o embedding da query via Azure OpenAI
2. Busca os chunks mais similares no ChromaDB (similaridade semântica)
3. Aplica re-ranking híbrido (semântico + lexical) para refinar a ordem
4. Retorna os chunks com similarity_score em cada um

Execução de teste: python -m src.rag.retrieval
"""

import os
import logging

import chromadb
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()
logger = logging.getLogger(__name__)

# ── Configurações ─────────────────────────────────────────────────────────────
CHROMA_DB_PATH  = "data/chroma_db"
COLLECTION_NAME = "compliance_docs"
EMBEDDING_MODEL = "text-embedding-ada-002"
TOP_K_RETRIEVAL = 10
TOP_K_FINAL     = 3


# ── Função principal ───────────────────────────────────────────────────────────

def retrieve_and_rerank(query: str, top_k_final: int = TOP_K_FINAL) -> list[dict]:
    """
    Pipeline completo de recuperação:
    1. Recupera os TOP_K_RETRIEVAL chunks mais similares
    2. Aplica re-ranking híbrido (60% semântico + 40% lexical)
    3. Retorna os top_k_final melhores
    """
    chunks   = retrieve_chunks(query, top_k=TOP_K_RETRIEVAL)
    reranked = rerank_chunks(query, chunks)
    return reranked[:top_k_final]


# ── Funções de recuperação ─────────────────────────────────────────────────────

def retrieve_chunks(query: str, top_k: int = TOP_K_RETRIEVAL) -> list[dict]:
    """
    Busca os chunks mais similares à query no ChromaDB.

    Gera o embedding da query via Azure e passa direto pro ChromaDB
    (query_embeddings), garantindo consistência com a ingestão.

    Retorna cada chunk com:
    - text: conteúdo do chunk
    - source: documento de origem
    - chunk_index: posição no documento
    - distance: distância cosine (menor = mais relevante)
    - similarity_score: 1 - distance (maior = mais relevante)
    """
    azure_client = get_azure_client()
    collection   = get_collection()

    query_embedding = get_embedding(query, azure_client)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text":             doc,
            "source":           meta.get("source", ""),
            "chunk_index":      meta.get("chunk_index", -1),
            "distance":         dist,
            "similarity_score": 1 - dist,
        })

    return chunks


def rerank_chunks(query: str, chunks: list[dict]) -> list[dict]:
    """
    Re-ranking híbrido: combina similaridade semântica com frequência de termos.

    - semantic_score: vem do embedding (1 - distance)
    - term_score: quantos termos da query (>= 4 chars) aparecem no chunk
    - score_final: 60% semântico + 40% lexical

    Ordena do maior score_final para o menor.
    """
    query_tokens = [t.lower() for t in query.split() if len(t) >= 4]

    for chunk in chunks:
        semantic_score = chunk["similarity_score"]

        if query_tokens:
            text_lower = chunk["text"].lower()
            hits       = sum(1 for term in query_tokens if term in text_lower)
            term_score = hits / len(query_tokens)
        else:
            term_score = 0.0

        chunk["score_final"] = 0.6 * semantic_score + 0.4 * term_score

    return sorted(chunks, key=lambda c: c["score_final"], reverse=True)


# ── Funções de apoio ───────────────────────────────────────────────────────────

def get_azure_client() -> AzureOpenAI:
    """Cria o cliente Azure OpenAI a partir das variáveis de ambiente."""
    return AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    )


def get_embedding(text: str, client: AzureOpenAI) -> list[float]:
    """Gera o embedding de um texto via Azure OpenAI (1536 dimensões)."""
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding


def get_collection() -> chromadb.Collection:
    """Conecta ao ChromaDB e retorna a collection."""
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    return client.get_collection(name=COLLECTION_NAME)


# ── Execução ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    query_teste = "perfil conservador renda fixa suitability"
    print(f"Query: {query_teste}\n")

    resultados = retrieve_and_rerank(query_teste)

    for i, chunk in enumerate(resultados, 1):
        print(f"Resultado {i}:")
        print(f"  Fonte: {chunk['source']} (chunk {chunk['chunk_index']})")
        print(f"  Similaridade: {chunk['similarity_score']:.4f}")
        print(f"  Score final:  {chunk['score_final']:.4f}")
        print(f"  Texto: {chunk['text'][:200]}...")
        print()