"""
knowledge_base/retriever.py — Phase 9: RAG retrieval

Thin wrapper around the persistent ChromaDB collection built by
build_index.py. HealthcareChatbot uses this to pull relevant reference
chunks before generating a response.

If the vector store hasn't been built yet (or can't be opened for any
reason), the Retriever disables itself instead of raising, so the chatbot
can still run without RAG — it just falls back to answering from the
model's own knowledge.
"""

import os

import chromadb
from sentence_transformers import SentenceTransformer

# Same embedding model and collection name used by build_index.py — the
# collection can only be searched with the model that created its vectors.
EMBEDDING_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
COLLECTION_NAME = "sehatai_docs"

BASE_DIR = os.path.dirname(__file__)
VECTOR_STORE_DIR = os.path.join(BASE_DIR, "vector_store")


class Retriever:
    """
    Looks up the most relevant document chunks for a given query from the
    "sehatai_docs" ChromaDB collection.
    """

    def __init__(self, vector_store_dir: str = None):
        store_path = vector_store_dir or VECTOR_STORE_DIR
        self.available = False
        self.embedder = None
        self.collection = None

        if not os.path.isdir(store_path):
            print(
                f"[WARN] No vector store found at {store_path}. "
                "RAG is disabled until you run 'python -m knowledge_base.build_index'."
            )
            return

        try:
            print(f"[INFO] Loading embedding model '{EMBEDDING_MODEL_NAME}'... Please wait.")
            self.embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)

            client = chromadb.PersistentClient(path=store_path)
            self.collection = client.get_collection(COLLECTION_NAME)
            self.available = True
        except Exception as e:
            print(
                f"[WARN] Could not load the vector store ({e}). "
                "RAG is disabled until you run 'python -m knowledge_base.build_index'."
            )
            self.available = False

    def retrieve(self, query: str, top_k: int = 2) -> list[dict]:
        """
        Return up to top_k chunks relevant to `query`, each as
        {"topic": ..., "text": ...}. Returns an empty list if retrieval is
        unavailable or the query fails for any reason — callers should
        treat that as "no reference material available" and carry on.
        """
        if not self.available:
            return []

        try:
            query_embedding = self.embedder.encode([query]).tolist()
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=top_k,
            )

            documents = results["documents"][0]
            metadatas = results["metadatas"][0]

            return [
                {"topic": metadata["topic"], "text": document_text}
                for document_text, metadata in zip(documents, metadatas)
            ]
        except Exception as e:
            print(f"[WARN] Retrieval failed ({e}). Continuing without reference material.")
            return []
