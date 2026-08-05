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

# Chunks with a raw distance above this are treated as "not actually
# relevant" and dropped, so an off-topic or badly-matched query doesn't get
# handed irrelevant reference text. This is a rough starting estimate based
# on early manual testing (good matches clustered around 12-20, weak/wrong
# matches around 25+) — recalibrate this once evaluation/scoring_template.md
# has real average distances for clean vs. typo/offtopic queries filled in.
MAX_DISTANCE = 25.0

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
        {"topic": ..., "text": ..., "distance": ...}. Returns an empty
        list if retrieval is unavailable, if the query fails for any
        reason, or if the best matches aren't actually close enough to
        trust (see MAX_DISTANCE) — callers should treat an empty list as
        "no reference material available" and carry on.

        UI redesign: `distance` was added to each returned dict (it was
        previously only available via debug_top_k) so chat_routes.py can
        surface it to the frontend as a plain-language confidence
        indicator next to the chat page's source references, without a
        second retrieval call. Existing callers that only read
        chunk["topic"]/chunk["text"] are unaffected — this is purely an
        additional key, not a shape change to anything already read.
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
            distances = results["distances"][0]

            return [
                {"topic": metadata["topic"], "text": document_text, "distance": distance}
                for document_text, metadata, distance in zip(documents, metadatas, distances)
                if distance <= MAX_DISTANCE
            ]
        except Exception as e:
            print(f"[WARN] Retrieval failed ({e}). Continuing without reference material.")
            return []

    def debug_top_k(self, query: str, top_k: int = 3) -> list[dict]:
        """
        TEMPORARY diagnostic method — returns raw top_k matches WITHOUT the
        MAX_DISTANCE filter, including the actual distance number for each.
        Used to see real retrieval behavior when debugging a mismatch,
        instead of guessing. Not used by chatbot.py's normal answer path —
        only called from debug print statements. Safe to remove once the
        current follow-up retrieval issue is diagnosed.
        """
        if not self.available:
            return []
        try:
            query_embedding = self.embedder.encode([query]).tolist()
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=top_k,
            )
            metadatas = results["metadatas"][0]
            distances = results["distances"][0]
            return [
                {"topic": metadata["topic"], "distance": distance}
                for metadata, distance in zip(metadatas, distances)
            ]
        except Exception as e:
            print(f"[WARN] debug_top_k failed: {e}")
            return []