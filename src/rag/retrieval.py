"""
Serviço de recuperação de chunks.
- Recebe uma query de texto
- Busca os chunks mais relevantes no ChromaDB usando embeddings
- Aplica re-ranking pra refinar ordem de resultados
"""

import os
import chromadb
import ssl
import numpy as np
from pypdf import PdfReader
from chromadb import EmbeddingFunction

ssl._create_default_https_context = ssl._create_unverified_context
os.environ["PYTHONHTTPSVERIFY"] = "0"

class SimpleEmbedding(EmbeddingFunction):
    def __call__(self, input):
        result = []
        for text in input:
            vec = np.zeros(128, dtype=np.float32)
            for i, char in enumerate(text):
                vec[i % 128] += ord(char)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            result.append(vec.tolist())
        return result
    
# ── Configurações ─────────────────────────────────────────────────────────────
CHROMA_DB_PATH     = "data/chroma_db"
COLLECTION_NAME    = "compliance_docs"
TOP_K_RETRIEVAL    = 10  # Número de chunks a recuperar
TOP_K_FINAL        = 3  # Número de chunks a retornar após re-ranking

def get_collection() -> chromadb.Collection:
    """
    Conecta ao ChromaDB e retorna a collection.
    """
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    embedding_fn = SimpleEmbedding()

    collection = client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )
    return collection


def retrieve_chunks(query: str, top_k: int = TOP_K_RETRIEVAL) -> list[dict]:
    """
    Busca os chunks mais similares para a query usando ChromaDB.
    Retorna uma lista:
    - Text: conteúdo do chunk
    - SOurce: nome do documento original
    - Chunk_index: posição do chunk no documento
    - Distance: distancia com a query (quanto menor, mais relevante)
    """
    collection = get_collection()

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    chunks = []
    for doc, meta, dist in zip(
        results['documents'][0], 
        results['metadatas'][0], 
        results['distances'][0]
    ):
        chunks.append({
            'text': doc,
            'source': meta.get('source', ''),
            'chunk_index': meta.get('chunk_index', -1),
            'distance': dist,
        })

    return chunks

def rerank_chunks(query: str, chunks: list[dict]) -> list[dict]:
    """
    Re-rank por frequencia de termos da query no chunk.
    - Tokeniza a query (>= 4 chars)
    - Conta quantas vezes cada token aparece no chunk
    - Score final = hits de termos / total de tokens da query
    - Combina distância semântica 
    - Ordena: maior score_final primeiro
    """
    query_tokens = [t.lower() for t in query.split() if len(t) >= 4]

    if not query_tokens:
        return chunks

    # Calcula o score para cada chunk
    for chunk in chunks:
        text_lower = chunk['text'].lower()
        hits = sum(1 for term in query_tokens if term in text_lower)
        term_score = hits / len(query_tokens)  

        semantic_score = 1 - chunk['distance']  # distancia menor, score maior

        chunk['score_final'] = 0.6 * semantic_score + 0.4 * term_score # 60% semantico, 40% lexical
    
    return sorted(chunks, key=lambda x: x['score_final'], reverse=True)

def retrieve_and_rerank(query: str, top_k_final: int = TOP_K_FINAL) -> list[dict]:
    """
    Combina recuperação e re-ranking:
    1. Recupera chunks relevantes
    2. Re-rank usando frequencia de termos + distancia semântica
    3. Retorna top_k_final resultados
    """
    chunks = retrieve_chunks(query, top_k=TOP_K_RETRIEVAL)
    # reranked = rerank_chunks(query, chunks)
    # return reranked[:top_k_final]
    return chunks[:top_k_final]

if __name__ == "__main__":
    query_teste = "perfil conservador renda fixa suitability"
    print(f"Query: {query_teste}\n")

    resultados = retrieve_and_rerank(query_teste)

    for i, chunk in enumerate(resultados, 1):
        print(f"Resultado {i}:")
        print(f"  Fonte: {chunk['source']} (chunk {chunk['chunk_index']})")
        print(f"  Score final: {chunk['score_final']:.4f}")
        print(f"  Text: {chunk['text'][:200]}...")  
        print()