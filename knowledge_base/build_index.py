"""
knowledge_base/build_index.py — Phases 7 + 8: Embeddings + Vector Database

Reads every .txt file in knowledge_base/documents/, splits each one into
~200-300 word chunks (paragraph-based), embeds the chunks with a
multilingual sentence-transformer, and stores everything in a persistent
ChromaDB collection at knowledge_base/vector_store/.

Re-running this script wipes and rebuilds the collection from scratch, so
it's always safe to re-run after editing a document — it never duplicates
chunks.

Usage:
    python -m knowledge_base.build_index
"""

import os

import chromadb
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "sehatai_docs"

BASE_DIR = os.path.dirname(__file__)
DOCUMENTS_DIR = os.path.join(BASE_DIR, "documents")
VECTOR_STORE_DIR = os.path.join(BASE_DIR, "vector_store")

# Target chunk size in words. We aim for the low end of this range and only
# go higher rather than cut a paragraph in half.
CHUNK_MIN_WORDS = 200
CHUNK_MAX_WORDS = 300


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_document(text: str) -> list[str]:
    """Split a document into ~200-300 word chunks.

    Documents are already written in paragraphs separated by blank lines,
    so we split on blank lines and then greedily group consecutive
    paragraphs together until adding the next one would push the chunk
    past CHUNK_MAX_WORDS. This keeps whole paragraphs intact instead of
    cutting sentences mid-thought.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current_paragraphs: list[str] = []
    current_word_count = 0

    for paragraph in paragraphs:
        paragraph_word_count = len(paragraph.split())

        # If adding this paragraph would blow past the max, and we already
        # have at least the minimum, close out the current chunk first.
        if (
            current_paragraphs
            and current_word_count + paragraph_word_count > CHUNK_MAX_WORDS
            and current_word_count >= CHUNK_MIN_WORDS
        ):
            chunks.append("\n\n".join(current_paragraphs))
            current_paragraphs = []
            current_word_count = 0

        current_paragraphs.append(paragraph)
        current_word_count += paragraph_word_count

    # Flush whatever's left as the final chunk.
    if current_paragraphs:
        chunks.append("\n\n".join(current_paragraphs))

    return chunks


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"[INFO] Loading embedding model '{EMBEDDING_MODEL_NAME}'... Please wait.")
    embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)

    # Connect to the persistent store on disk. This creates vector_store/
    # if it doesn't exist yet.
    os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=VECTOR_STORE_DIR)

    # Wipe any existing collection so re-running this script never
    # duplicates chunks.
    existing_collections = [c.name for c in client.list_collections()]
    if COLLECTION_NAME in existing_collections:
        client.delete_collection(COLLECTION_NAME)
    collection = client.create_collection(COLLECTION_NAME)

    document_filenames = sorted(
        f for f in os.listdir(DOCUMENTS_DIR) if f.endswith(".txt")
    )

    chunks_per_document: dict[str, int] = {}
    all_chunk_texts: list[str] = []
    all_chunk_ids: list[str] = []
    all_chunk_metadata: list[dict] = []

    for filename in document_filenames:
        topic = os.path.splitext(filename)[0]
        file_path = os.path.join(DOCUMENTS_DIR, filename)

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        doc_chunks = chunk_document(text)
        chunks_per_document[topic] = len(doc_chunks)

        for chunk_index, chunk_text in enumerate(doc_chunks):
            all_chunk_texts.append(chunk_text)
            all_chunk_ids.append(f"{topic}_{chunk_index}")
            all_chunk_metadata.append({"topic": topic, "chunk_index": chunk_index})

    print(f"[INFO] Embedding {len(all_chunk_texts)} chunks from {len(document_filenames)} documents...")
    embeddings = embedder.encode(all_chunk_texts, show_progress_bar=True).tolist()

    # Store everything in one batch call.
    collection.add(
        ids=all_chunk_ids,
        embeddings=embeddings,
        documents=all_chunk_texts,
        metadatas=all_chunk_metadata,
    )

    # ---------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------
    print("\n[DONE] Index built successfully.")
    print(f"Documents processed: {len(document_filenames)}")
    print("Chunks per document:")
    for topic, count in chunks_per_document.items():
        print(f"  - {topic}: {count} chunk(s)")
    print(f"Total chunks: {len(all_chunk_texts)}")
    print(f"Collection '{COLLECTION_NAME}' stored at: {VECTOR_STORE_DIR}")


if __name__ == "__main__":
    main()
