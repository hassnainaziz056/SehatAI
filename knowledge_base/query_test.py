"""
knowledge_base/query_test.py — sanity check for Phases 7 + 8

Loads the same embedding model used to build the index, connects to the
existing persistent ChromaDB collection (does NOT rebuild it — run
build_index.py first if the collection doesn't exist yet), and runs a
handful of hardcoded test queries to confirm retrieval is pulling back the
right chunks for the right topics.

Usage:
    python -m knowledge_base.query_test
"""

import os

import chromadb
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "sehatai_docs"

BASE_DIR = os.path.dirname(__file__)
VECTOR_STORE_DIR = os.path.join(BASE_DIR, "vector_store")

TOP_K = 3
PREVIEW_CHARS = 150

# A handful of queries spanning different topics/documents, phrased the way
# a real user might type them rather than matching document titles exactly.
TEST_QUERIES = [
    "what should I eat if I'm pregnant",
    "what to do if a snake bites someone",
    "my child has a high fever",
    "signs of a heart attack",
    "is it safe to take too much paracetamol",
    "I can't sleep and feel anxious all the time",
]


def main() -> None:
    print(f"[INFO] Loading embedding model '{EMBEDDING_MODEL_NAME}'... Please wait.")
    embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)

    if not os.path.isdir(VECTOR_STORE_DIR):
        raise FileNotFoundError(
            f"No vector store found at {VECTOR_STORE_DIR}. "
            "Run 'python -m knowledge_base.build_index' first."
        )

    client = chromadb.PersistentClient(path=VECTOR_STORE_DIR)
    collection = client.get_collection(COLLECTION_NAME)

    for query in TEST_QUERIES:
        print(f"\nQuery: {query}")

        query_embedding = embedder.encode([query]).tolist()
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=TOP_K,
        )

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for rank, (doc_text, metadata, distance) in enumerate(
            zip(documents, metadatas, distances), start=1
        ):
            preview = doc_text[:PREVIEW_CHARS].replace("\n", " ").strip()
            print(
                f"  {rank}. topic={metadata['topic']} "
                f"distance={distance:.4f} "
                f"preview: {preview}..."
            )


if __name__ == "__main__":
    main()
