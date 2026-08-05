import os
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextStreamer

from knowledge_base.retriever import Retriever
from src.scope_guard import is_medical_question
from src.emergency_detector import (
    NATIONAL_EMERGENCY_NUMBER,
    detect_emergency,
    get_emergency_response,
)

# Shown to the user when a query is rejected before ever reaching the model.
# Two distinct messages so it's clear (in logs/console) which gate caught it:
#   - OFF_TOPIC_REFUSAL: the question itself has no medical/health signal (Layer 2)
#   - NO_MATCH_REFUSAL: the question is medical, but nothing in the knowledge
#     base is a confident match for it (Layer 3) — refusing here is safer
#     than letting a small model improvise an ungrounded answer.
OFF_TOPIC_REFUSAL = (
    "I'm here to help with your health — is something bothering you today? "
    "I can only discuss medical and healthcare questions."
)
NO_MATCH_REFUSAL = (
    "I don't have reliable information on that specific condition right now. "
    "Could you tell me a bit more, or it may be best to check with a doctor or health worker directly."
)

# Plain small talk a doctor would naturally exchange with a patient before
# getting into symptoms — these carry no medical keyword and have nothing
# to retrieve, so they bypass both the scope gate and retrieval entirely
# rather than being treated as off-topic. Exact-match only (after stripping
# trailing punctuation): "hi, what's the weather" does NOT match this list,
# so it still goes through the normal scope/retrieval checks below.
GREETING_PHRASES = {
    "hi", "hello", "hey", "hii", "hiya", "yo",
    "good morning", "good afternoon", "good evening",
    "how are you", "how are you doing", "how r u", "how are u", "how're you",
    "what's up", "whats up",
    "assalam o alaikum", "assalamualaikum", "salam", "adaab",
}

# Messages that are medical in scope (they pass Layer 2's keyword gate) but
# carry no actual symptom/condition information to retrieve or reason about
# — "I am sick" is true of a thousand different conditions. Answering these
# immediately means retrieval has to guess, and often latches onto whatever
# generic illness document happens to be nearest in the vector space (e.g.
# a diarrhea/dehydration doc) even though the patient never mentioned those
# symptoms. A real doctor asks a follow-up question here instead of
# guessing — so this bypasses retrieval and generation entirely and asks
# one directly, the same short-circuit shape as a greeting or a refusal.
# Exact-match only (after stripping trailing punctuation), same rule as
# GREETING_PHRASES — "I'm sick and also have chest pain" carries real
# information and should NOT match this list, so it still goes through
# normal scope/retrieval handling below.
VAGUE_COMPLAINT_PHRASES = {
    "i am sick", "i'm sick", "im sick", "i feel sick",
    "i am unwell", "i'm unwell", "im unwell", "i feel unwell",
    "i am ill", "i'm ill", "im ill",
    "i don't feel well", "i dont feel well", "i do not feel well",
    "i am not well", "i'm not well", "im not well",
    "i feel bad", "i feel unwell", "not feeling well", "not well",
    "i am not feeling well", "i'm not feeling well",
    "sick", "unwell", "ill",
}
CLARIFYING_QUESTION = (
    "I'm sorry you're not feeling well. Could you tell me a bit more — "
    "what symptoms are you noticing (like fever, pain, cough, or an upset "
    "stomach), and how long have you had them? That'll help me give you "
    "more useful guidance."
)

# Built here, after all three message constants exist, so this list is used
# to keep boilerplate replies (refusals + the clarifying question) out of
# _build_retrieval_query's search for the last real assistant reply to
# anchor a follow-up query against.
_REFUSAL_MESSAGES = (OFF_TOPIC_REFUSAL, NO_MATCH_REFUSAL, CLARIFYING_QUESTION)

FOLLOWUP_MAX_WORDS = 12
FOLLOWUP_REFERENTIAL_WORDS = (
    "it", "this", "that", "these", "those", "them", "also", "too",
    "about", "again", "another", "more", "same",
    "clarify", "further", "continue", "detail", "details",
)
# Prefix-matched separately from the exact-word set above, because typos on
# these specific words showed up in real testing (e.g. "elabortae" for
# "elaborate") — an exact-word check would miss them. "explai" / "elabor"
# are short enough to be a safe, specific prefix (no unrelated English words
# start with either) while still catching common misspellings.
FOLLOWUP_REFERENTIAL_PREFIXES = ("explai", "elabor")
FOLLOWUP_BARE_WORDS = ("why", "how", "when", "who", "what")

# How much of the previous assistant reply gets used to build a follow-up's
# retrieval query (see _build_retrieval_query). ~120 characters is roughly
# the first sentence or two — enough to anchor the topic without pulling in
# an entire long answer's generic closing boilerplate.
PREVIOUS_REPLY_EXCERPT_CHARS = 120


class HealthcareChatbot:
    """
    A lightweight local LLM chatbot tailored for SehatAI.

    NOTE (Phase 13 refactor): this instance no longer stores conversation
    history on itself. self.model, self.tokenizer, self.retriever, and
    self.system_prompt are shared, loaded once, and safe to reuse across
    many simultaneous conversations (e.g. many web users) — but the actual
    conversation state is now owned entirely by the caller and passed into
    generate_response() explicitly. This instance holds no per-conversation
    state at all, so a single HealthcareChatbot can safely serve many
    independent conversations without them bleeding into each other.
    """

    def __init__(self, model_name: str = "Qwen/Qwen2.5-0.5B-Instruct"):
        print(f"\n[INFO] Loading tokenizer & model '{model_name}'... Please wait.")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        tokenizer = AutoTokenizer.from_pretrained(model_name)
        assert tokenizer is not None, "Failed to load tokenizer."
        self.tokenizer = tokenizer

        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            dtype=torch.float32,
        ).to(self.device)

        self.streamer = TextStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)

        self.system_prompt = (
            "You are SehatAI, speaking with the warmth and manner of a caring family doctor at a rural clinic, "
            "not a generic assistant. Greet the patient the way a doctor would — for example, ask how they are "
            "feeling today — rather than sounding formal or robotic. Refer to the person as a patient, not a user. "
            "Your purpose is ONLY to discuss diseases, symptoms, medicines, nutrition, pregnancy, "
            "first aid, medical tests, mental health, and general healthcare advice. "
            "If asked about anything outside this scope, decline the way a doctor would gently redirect a "
            f"patient back to their health, and say: \"{OFF_TOPIC_REFUSAL}\" "
            "Provide clear, accurate health guidance. "
            "Keep your answers focused and complete — aim for around 120-180 words, and always finish your "
            "last sentence rather than trailing off, even if that means being more concise. "
            "Always make clear you are an AI, not a licensed physician, and that serious or worsening symptoms "
            "need in-person medical care."
        )

        # conversation_history is intentionally NOT stored here anymore
        # (Phase 13). Each caller (main.py, or eventually a web request
        # handler) owns and passes in its own history list, starting with
        # [{"role": "system", "content": self.system_prompt}].

        self.retriever = Retriever()
        if self.retriever.available:
            print("[INFO] RAG is active — responses will use the knowledge base.")
        else:
            print("[INFO] RAG is disabled — responses will use the model's own knowledge only.")

    def _build_retrieval_query(self, user_input: str, conversation_history: list) -> str:
        """
        Build the text actually sent to the retriever for vector search.
        Prepends a short excerpt of the most recent REAL (non-refusal)
        assistant reply to the new message, so short follow-ups keep the
        right topical anchor. Refusal messages are excluded — they contain
        words like "healthcare"/"medical" themselves, which would make the
        very next message look medical regardless of what it actually says.

        Only the first PREVIOUS_REPLY_EXCERPT_CHARS characters of the prior
        reply are used, not the whole thing. Real testing showed that a
        long prior reply — especially one full of generic safety phrasing
        that's common across most documents in this knowledge base ("seek
        medical attention", "consult a healthcare provider") — can dilute
        or outright override the actual topic signal in the embedding
        search, causing retrieval to latch onto shared boilerplate texture
        from an unrelated document instead of the real topic. A short
        excerpt still anchors the follow-up to the right subject without
        letting a long answer's generic tail dominate the query.
        """
        previous_real_replies = [
            msg["content"] for msg in conversation_history
            if msg["role"] == "assistant"
            and msg["content"] not in _REFUSAL_MESSAGES
            # Emergency responses (Phase 19) are templated but vary in
            # exact wording per call, so they can't be caught by the exact
            # membership check above the way the other boilerplate replies
            # are. Every emergency template — variant or not — always
            # contains the national emergency number, so that's used as a
            # reliable, cheap signal that this was boilerplate, not a real
            # topical reply worth anchoring a follow-up query to.
            and NATIONAL_EMERGENCY_NUMBER not in msg["content"]
        ]
        if previous_real_replies:
            excerpt = previous_real_replies[-1][:PREVIOUS_REPLY_EXCERPT_CHARS]
            return f"{excerpt}\n\n{user_input}"
        return user_input

    def _is_in_scope(self, user_input: str, retrieval_query: str) -> bool:
        """
        Layer 2 scope check. Judges the new message on its own first; only
        borrows conversational context for genuinely short, referential
        follow-ups — not for any short-ish new question in general.
        """
        if is_medical_question(user_input):
            return True

        stripped_input = user_input.strip().lower().rstrip("?!.")
        is_bare_question_word = stripped_input in FOLLOWUP_BARE_WORDS

        looks_like_followup = is_bare_question_word or (
            len(user_input.split()) <= FOLLOWUP_MAX_WORDS
            and (
                any(word in user_input.lower().split() for word in FOLLOWUP_REFERENTIAL_WORDS)
                or any(
                    user_word.startswith(prefix)
                    for user_word in user_input.lower().split()
                    for prefix in FOLLOWUP_REFERENTIAL_PREFIXES
                )
            )
        )
        if looks_like_followup:
            return is_medical_question(retrieval_query)

        return False

    def _refuse(self, user_input: str, message: str, conversation_history: list) -> tuple[str, list]:
        """
        Short-circuit path used when a query fails the scope check (Layer 2)
        or the knowledge-base confidence check (Layer 3). No retrieval or
        model generation happens at all. Both turns are appended to the
        given history and the updated list is returned.
        """
        conversation_history.append({"role": "user", "content": user_input})
        conversation_history.append({"role": "assistant", "content": message})
        print(f"\nSehatAI: {message}")
        return message, conversation_history

    def generate_response(
        self,
        user_input: str,
        conversation_history: list,
        patient_name: str | None = None,
        patient_age: int | None = None,
        include_meta: bool = False,
    ) -> tuple[str, list] | tuple[str, list, dict]:
        """
        Generate a response to user_input, given the conversation so far.

        Phase 13: conversation_history is now an explicit argument, not
        self.conversation_history. This method never mutates the list it's
        given — it works on a local copy and returns the updated copy, so
        the caller decides what to do with it (e.g. save it to a database,
        per user). Returns (response_text, updated_history) by default.

        Phase 19: patient_name and patient_age are optional (callers that
        don't have them yet just don't pass them) and are only used to
        personalize an emergency response, if one is triggered — see
        emergency_detector.py. patient_age has no route to a real value
        until Phase 20's profile table exists; until then callers simply
        omit it and responses fall back to name-only or generic phrasing.

        UI redesign: include_meta=True (used by backend/routes/chat_routes.py
        so the frontend can render an emergency banner and source
        references) additionally returns a third element, a dict with:
          - "is_emergency": bool — True only when the emergency detector
            fired and this is its fixed, templated response.
          - "sources": list[{"topic": str, "distance": float}] — whatever
            was retrieved and actually used to ground this reply, empty
            for greetings/refusals/emergency responses/ungrounded replies.
        Default is False so main.py's existing CLI loop (which unpacks a
        plain 2-tuple) keeps working completely unchanged.
        """
        # Work on a local copy — never mutate the caller's list in place.
        history = list(conversation_history)

        def _finish(text: str, updated_history: list, is_emergency: bool = False, sources: list | None = None):
            if not include_meta:
                return text, updated_history
            return text, updated_history, {
                "is_emergency": is_emergency,
                "sources": sources or [],
            }

        # Checked before anything else, including greetings — an emergency
        # phrase should never fall through to scope/retrieval/generation,
        # no matter what else is in the message. See emergency_detector.py
        # for why this is a fixed, templated response rather than a
        # generated one.
        emergency_category = detect_emergency(user_input)
        if emergency_category:
            emergency_response = get_emergency_response(
                emergency_category, patient_name, patient_age
            )
            reply, updated_history = self._refuse(user_input, emergency_response, history)
            return _finish(reply, updated_history, is_emergency=True)

        stripped_input = user_input.strip().lower().rstrip("?!.")
        is_greeting = stripped_input in GREETING_PHRASES

        # Checked before the scope gate: a vague complaint like "I am sick"
        # already passes Layer 2 (it contains "sick"), so without this check
        # it would fall straight through to retrieval and generation, which
        # is exactly the guessing behavior this is meant to prevent.
        if not is_greeting and stripped_input in VAGUE_COMPLAINT_PHRASES:
            reply, updated_history = self._refuse(user_input, CLARIFYING_QUESTION, history)
            return _finish(reply, updated_history)

        retrieval_query = self._build_retrieval_query(user_input, history)

        if not is_greeting and not self._is_in_scope(user_input, retrieval_query):
            reply, updated_history = self._refuse(user_input, OFF_TOPIC_REFUSAL, history)
            return _finish(reply, updated_history)

        retrieved = [] if is_greeting else self.retriever.retrieve(retrieval_query, top_k=2)

        if not is_greeting and self.retriever.available and not retrieved:
            reply, updated_history = self._refuse(user_input, NO_MATCH_REFUSAL, history)
            return _finish(reply, updated_history)

        if retrieved:
            context_block = "\n\n".join(
                f"[{chunk['topic']}]\n{chunk['text']}" for chunk in retrieved
            )
            augmented_input = (
                "Reference information (use only if relevant to the question, "
                "and answer in your own words, not by copying this text):\n\n"
                f"{context_block}\n\n"
                f"Patient question: {user_input}"
            )
        else:
            augmented_input = user_input

        # Append the ORIGINAL, unmodified user message to conversation memory.
        history.append({"role": "user", "content": user_input})

        # Temporary message list for this call only — everything up to (but
        # not including) the clean user turn just appended, plus one
        # augmented version of it. Never written back into `history`.
        messages_for_prompt = history[:-1] + [
            {"role": "user", "content": augmented_input}
        ]

        formatted_prompt = self.tokenizer.apply_chat_template(
            messages_for_prompt,
            tokenize=False,
            add_generation_prompt=True
        )

        inputs = self.tokenizer(str(formatted_prompt), return_tensors="pt").to(self.device)

        print("\nSehatAI: ", end="", flush=True)
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=400,
                temperature=0.7,
                top_p=0.9,
                do_sample=True,
                streamer=self.streamer
            )

        input_length = inputs["input_ids"].shape[1]
        new_tokens = outputs[0][input_length:]
        response_text = self.tokenizer.decode(new_tokens, skip_special_tokens=True)

        history.append({"role": "assistant", "content": response_text})

        sources = [
            {"topic": chunk["topic"], "distance": chunk["distance"]}
            for chunk in retrieved
        ] if retrieved else []
        return _finish(response_text, history, sources=sources)