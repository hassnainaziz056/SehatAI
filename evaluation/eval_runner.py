"""
evaluation/eval_runner.py — Phase 11: Evaluation

Runs every entry in EVAL_SET through HealthcareChatbot and logs, for each
one: the raw retrieved topics + distance scores, the RAG-enabled response,
and (for independent/setup questions only) a no-RAG baseline response for
comparison.

This script only produces the raw transcript. Reading the transcript and
filling in scoring_template.md by hand is the actual Phase 11 deliverable.

Usage:
    python -m evaluation.eval_runner
"""

import os
from datetime import datetime

from src.chatbot import HealthcareChatbot
from evaluation.eval_set import EVAL_SET


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fresh_history(bot: HealthcareChatbot) -> list:
    """Build a brand-new, single-message conversation history (system prompt
    only).

    Phase 13 update: HealthcareChatbot no longer keeps conversation_history
    on itself, so this used to reset bot.conversation_history in place —
    now it just returns a new local list. Called before every
    independent/setup question so unrelated earlier entries don't bleed
    into it. Followup entries deliberately skip this (see main()) so they
    continue the same running `history` list as the entry directly above
    them.
    """
    return [{"role": "system", "content": bot.system_prompt}]


def get_retrieval_debug(retriever, query: str, top_k: int = 2) -> list[dict]:
    """
    Run the same search Retriever.retrieve() does, but also keep the raw
    distance scores — Retriever.retrieve() strips those out since the
    chatbot itself doesn't need them. We reuse the retriever's already-loaded
    embedder and collection directly rather than duplicating model-loading
    logic, and without modifying retriever.py.

    Returns a list of {"topic": ..., "distance": ...}, or [] if RAG is
    unavailable or the query fails for any reason.
    """
    if not retriever.available:
        return []

    try:
        query_embedding = retriever.embedder.encode([query]).tolist()
        results = retriever.collection.query(
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
        print(f"    [WARN] Retrieval debug failed: {e}")
        return []


def format_retrieved(retrieved: list[dict]) -> str:
    if not retrieved:
        return "_(none)_"
    return ", ".join(f"{r['topic']} (distance={r['distance']:.4f})" for r in retrieved)


# ---------------------------------------------------------------------------
# Transcript building
# ---------------------------------------------------------------------------

def build_transcript(results: list[dict]) -> str:
    lines = []
    lines.append(f"# SehatAI Evaluation Run — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("Auto-generated transcript. Fill in `scoring_template.md` by hand after reading this.")
    lines.append("")

    # Group by category, preserving first-seen order.
    categories_in_order = []
    by_category = {}
    for entry in results:
        category = entry["category"]
        if category not in by_category:
            by_category[category] = []
            categories_in_order.append(category)
        by_category[category].append(entry)

    for category in categories_in_order:
        lines.append(f"## Category: {category}")
        lines.append("")
        for entry in by_category[category]:
            lines.append(f"### {entry['id']}")
            lines.append("")
            lines.append(f"**Query:** {entry['query']}")
            lines.append(f"**Expected topic:** {entry['expected_topic']}")
            lines.append(f"**Retrieved:** {format_retrieved(entry.get('retrieved', []))}")
            lines.append("")

            if entry.get("rag_error"):
                lines.append(f"**RAG response:** _ERROR: {entry['rag_error']}_")
            else:
                lines.append(f"**RAG response:**\n\n{entry.get('rag_response', '')}")
            lines.append("")

            if entry.get("skipped_no_rag"):
                lines.append("**No-RAG response:** _(skipped — this is a followup; "
                              "comparison only runs on the setup question, see notes above)_")
            elif entry.get("no_rag_error"):
                lines.append(f"**No-RAG response:** _ERROR: {entry['no_rag_error']}_")
            else:
                lines.append(f"**No-RAG response:**\n\n{entry.get('no_rag_response', '')}")
            lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------

def main() -> None:
    # Model loading is slow, so we instantiate the chatbot exactly once and
    # reuse it for every entry in EVAL_SET.
    bot = HealthcareChatbot()

    results = []
    total = len(EVAL_SET)

    # Phase 13 update: history is now an explicit local list threaded
    # through generate_response() calls, not bot.conversation_history.
    # Independent/setup questions get a clean list; followups deliberately
    # keep reusing (and extending) the same running `history` so they
    # continue the conversation from the entry above them.
    history = fresh_history(bot)

    for i, entry in enumerate(EVAL_SET, start=1):
        follows_previous = entry.get("follows_previous", False)
        print(f"[{i}/{total}] Running: {entry['id']} ({entry['category']}) "
              f"{'[followup]' if follows_previous else ''}")

        if not follows_previous:
            history = fresh_history(bot)

        record = dict(entry)  # copy so we can attach results without mutating EVAL_SET

        # Step (a): raw retrieval debug info (topics + distances), logged
        # before generation so it reflects the query alone.
        try:
            record["retrieved"] = get_retrieval_debug(bot.retriever, entry["query"], top_k=2)
        except Exception as e:
            print(f"    [ERROR] retrieval debug failed: {e}")
            record["retrieved"] = []

        # Step (b): no-RAG baseline FIRST — only for independent/setup
        # questions. Running this before the RAG call, on freshly reset
        # history, guarantees it's genuinely clean: nothing RAG-related has
        # happened yet, so there's nothing for it to leak from. Followups
        # skip this entirely — the whole point of a followup is to test
        # behavior WITH prior RAG-grounded context already present, so a
        # standalone no-RAG comparison doesn't apply to them.
        if not follows_previous:
            original_availability = bot.retriever.available
            bot.retriever.available = False
            try:
                # Phase 13 signature: pass history in, get (text, updated_history) back.
                response_text, history = bot.generate_response(entry["query"], history)
                record["no_rag_response"] = response_text
            except Exception as e:
                print(f"    [ERROR] no-RAG generation failed: {e}")
                record["no_rag_error"] = str(e)
            finally:
                bot.retriever.available = original_availability
        else:
            record["skipped_no_rag"] = True

        # Step (c): the real RAG-enabled response, asked second. Because it
        # runs after step (b), it ends up as the LAST turn in
        # conversation_history — which is exactly what we want, since any
        # followup entry right after this one should continue from the
        # RAG-grounded answer, not the no-RAG one. No snapshotting or
        # restoring needed; the natural order handles it.
        try:
            response_text, history = bot.generate_response(entry["query"], history)
            record["rag_response"] = response_text
        except Exception as e:
            print(f"    [ERROR] RAG generation failed: {e}")
            record["rag_error"] = str(e)

        results.append(record)

    # Write the transcript.
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(results_dir, f"eval_run_{timestamp}.md")

    transcript = build_transcript(results)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(transcript)

    print(f"\n[DONE] Transcript written to {out_path}")


if __name__ == "__main__":
    main()