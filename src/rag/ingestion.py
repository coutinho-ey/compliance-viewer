"""
Pipeline de ingestão de dados para o sistema RAG (Retrieval-Augmented Generation).

Fluxo:
1. LÊ os documentos da knowledge_base/ (PDF e TXT)
2. EXTRAI o texto bruto
3. CORTA o texto em chunks com overlap (LangChain)
4. EMBEDA os chunks em batch via Azure OpenAI (text-embedding-ada-002)
5. JOGA os chunks + embeddings + metadados no ChromaDB

Execução: python -m src.rag.ingestion
"""

import os
import time
import logging

import chromadb
from dotenv import load_dotenv
from openai import AzureOpenAI
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ── Configurações ─────────────────────────────────────────────────────────────
KNOWLEDGE_BASE_DIR = "knowledge_base"
CHROMA_DB_PATH     = "data/chroma_db"
COLLECTION_NAME    = "compliance_docs"
CHUNK_SIZE         = 500   # Tamanho de cada chunk em caracteres
CHUNK_OVERLAP      = 50    # Sobreposição entre chunks para preservar contexto
EMBEDDING_MODEL    = "text-embedding-ada-002"
BATCH_SIZE         = 16    # Quantos chunks enviar por chamada ao Azure
RATE_LIMIT_SLEEP   = 2.0   # Pausa entre batches para não estourar rate limit


# ── Cliente Azure e embeddings (funções de apoio) ──────────────────────────────

def get_azure_client() -> AzureOpenAI:
    """Cria o cliente Azure OpenAI a partir das variáveis de ambiente."""
    return AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    )


def get_embeddings_batch(texts: list[str], client: AzureOpenAI) -> list[list[float]]:
    """
    Gera embeddings de vários textos numa só chamada ao Azure.
    Reduz drasticamente o número de requisições e evita o rate limit (429).
    Cada embedding tem 1536 dimensões.
    """
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [item.embedding for item in response.data]


# ── Extração de texto ──────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrai o texto bruto de um PDF, página por página."""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


def extract_text_from_txt(txt_path: str) -> str:
    """Lê o conteúdo bruto de um arquivo TXT."""
    with open(txt_path, "r", encoding="utf-8") as f:
        return f.read()


# ── Chunking (LangChain) ───────────────────────────────────────────────────────

def split_into_chunks(text: str) -> list[str]:
    """
    Divide o texto em chunks usando o RecursiveCharacterTextSplitter do LangChain.
    Quebra primeiro em parágrafos, depois frases, depois palavras — preservando
    o significado melhor que um corte cego por tamanho.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(text)
    return [c.strip() for c in chunks if c.strip()]


# ── Pipeline principal ─────────────────────────────────────────────────────────

def ingest_documents():
    """
    Pipeline completo de ingestão:
    LÊ → EXTRAI → CORTA → EMBEDA (em batch) → JOGA NO CHROMADB
    """
    logger.info("Iniciando ingestão...")

    azure_client = get_azure_client()
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    # Recria a collection do zero para garantir consistência dos embeddings
    try:
        chroma_client.delete_collection(COLLECTION_NAME)
        logger.info(f"Collection '{COLLECTION_NAME}' antiga removida.")
    except Exception:
        pass

    collection = chroma_client.create_collection(name=COLLECTION_NAME)

    files = [f for f in os.listdir(KNOWLEDGE_BASE_DIR) if f.endswith((".pdf", ".txt"))]
    if not files:
        logger.warning("Nenhum arquivo encontrado na knowledge_base/.")
        return

    total_chunks = 0
    for file in files:
        file_path = os.path.join(KNOWLEDGE_BASE_DIR, file)
        logger.info(f"Processando: {file}")

        text = extract_text_from_pdf(file_path) if file.endswith(".pdf") else extract_text_from_txt(file_path)
        if not text.strip():
            logger.warning(f"  Nenhum texto extraído de {file}. Pulando.")
            continue

        chunks = split_into_chunks(text)
        logger.info(f"  {len(chunks)} chunks gerados. Gerando embeddings em batch...")

        # Processa em batches para reduzir requisições e evitar rate limit
        for start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[start : start + BATCH_SIZE]
            embeddings = get_embeddings_batch(batch, azure_client)

            ids = [f"{file}_chunk_{start + j}" for j in range(len(batch))]
            metadatas = [
                {"source": file, "chunk_index": start + j, "chunk_id": f"{file}_chunk_{start + j}"}
                for j in range(len(batch))
            ]

            collection.add(
                ids=ids,
                documents=batch,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            time.sleep(RATE_LIMIT_SLEEP)  # respeita o rate limit do Azure

        total_chunks += len(chunks)
        logger.info(f"  {file} indexado com sucesso.")

    logger.info(f"\nIngestão concluída. Total de {total_chunks} chunks no ChromaDB.")


if __name__ == "__main__":
    ingest_documents()