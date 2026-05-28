"""
Pipeline de ingestão de dados para o projeto de RAG (Retrieval-Augmented Generation)
- Ler os docs do knowledge base
- Divisão de chunks
- Gerar embeddings e armazenar no ChromaDB

execução: python -m src.rag.ingestion
"""

import os
import chromadb
from pypdf import PdfReader
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

os.environ["HUGGINGFACE_HUB_VERBOSITY"] = "error"
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""

# ── Configurações ─────────────────────────────────────────────────────────────
KNOWLEDGE_BASE_DIR = "knowledge_base"
CHROMA_DB_PATH     = "data/chroma_db"
COLLECTION_NAME    = "compliance_docs"
CHUNK_SIZE         = 500   # Tamanho de cada chunk em caracteres
CHUNK_OVERLAP      = 50    # Sobreposição entre chunks para preservar contexto
EMBEDDING_MODEL    = "all-MiniLM-L6-v2"  # Modelo leve e eficiente para embeddings


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extrai o texto bruto de um arquivo PDF página por página.
    Retorna o texto completo concatenado.
    """
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


def extract_text_from_txt(txt_path: str) -> str:
    """
    Lê o conteúdo bruto de um arquivo TXT.
    Retorna o texto completo.
    """
    with open(txt_path, "r", encoding="utf-8") as f:
        return f.read()


def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Divide o texto em chunks com sobreposição.
    A sobreposição garante que o contexto não seja perdido nas bordas dos chunks.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += chunk_size - overlap
    return [c for c in chunks if c]  # Remove chunks vazios


def ingest_documents():
    """
    Fluxo principal de ingestão:
    1. Lê todos os PDFs e TXTs da knowledge_base/
    2. Extrai e divide o texto em chunks
    3. Armazena no ChromaDB com metadados de rastreabilidade
    """
    # Inicializa o cliente ChromaDB persistente
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    # Usa SentenceTransformer para gerar embeddings localmente
    embedding_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)

    # Cria ou recupera a collection — operação idempotente
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )

    # Processa cada arquivo da knowledge_base/
    files = [f for f in os.listdir(KNOWLEDGE_BASE_DIR) if f.endswith(".pdf") or f.endswith(".txt")]

    if not files:
        print("Nenhum arquivo encontrado na knowledge_base/.")
        return

    for file in files:
        file_path = os.path.join(KNOWLEDGE_BASE_DIR, file)
        print(f"Processando: {file}")

        # Extrai texto de acordo com o tipo de arquivo
        text = extract_text_from_pdf(file_path) if file.endswith(".pdf") else extract_text_from_txt(file_path)

        if not text.strip():
            print(f"  ⚠️ Nenhum texto extraído de {file}. Pulando.")
            continue

        # Divide em chunks
        chunks = split_into_chunks(text)
        print(f"  {len(chunks)} chunks gerados.")

        # Prepara os dados para inserção no ChromaDB
        ids       = [f"{file}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"source": file, "chunk_index": i} for i in range(len(chunks))]

        # Insere no ChromaDB — upsert evita duplicatas em re-execuções
        collection.upsert(
            ids=ids,
            documents=chunks,
            metadatas=metadatas,
        )
        print(f" Aeee!🎆 {file} indexado com sucesso.")

    print(f"\nIngestão concluída. Total de documentos na collection: {collection.count()}")


if __name__ == "__main__":
    ingest_documents()