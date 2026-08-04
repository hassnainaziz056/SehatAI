"""
src/scope_guard.py — keeps SehatAI on-topic (Layer 2 of 3)

A lightweight keyword-based classifier that decides whether a user's
message is health/medical-related before any retrieval or generation
happens.

This is Layer 2 of a three-layer scope-restriction pipeline:
  Layer 1 — the system prompt in chatbot.py asks the model to refuse
            non-medical questions on its own (not always reliable for a
            small model).
  Layer 2 — this file: a hard keyword gate in front of retrieval/generation,
            so obviously off-topic questions (weather, sports, tech support)
            never reach the model at all.
  Layer 3 — knowledge_base/retriever.py's MAX_DISTANCE threshold, which
            drops retrieved chunks that aren't actually a confident match.

Two known limitations, and how this file addresses them:

1. Plain substring matching (e.g. "ache" in query) can false-positive on
   unrelated words that happen to contain a keyword — "cache", "orchestra".
   Fixed here with word-boundary regex matching instead of raw substring
   checks, so "ache" only matches the actual word "ache", not "cache".

2. Real patients — especially describing symptoms in plain, non-clinical
   language rather than textbook terms — often won't use words like
   "symptom" or "diagnosis" at all. A question like "I feel so tired and
   thirsty all the time" is a textbook diabetes description but contains no
   clinical vocabulary whatsoever. The keyword list below has been expanded
   with everyday symptom words for this reason.

This is still a simple heuristic and won't catch every possible phrasing —
a smarter but slower option would be asking the LLM itself to classify the
query first. It's fast, has no extra model call, and errs on the side of
asking the user to rephrase rather than silently answering something
off-topic. Layer 3 (retriever.py's confidence check) acts as a backstop for
anything that slips past this layer without a real matching document.
"""

import re

MEDICAL_KEYWORDS = [
    # General
    "health", "medical", "medicine", "doctor", "clinic", "hospital",
    "symptom", "symptoms", "disease", "illness", "infection", "treatment",
    "diagnosis", "emergency", "first aid", "vaccine", "vaccination",
    # Body / conditions (clinical terms)
    "fever", "pain", "ache", "blood", "heart", "chest", "breath",
    "breathing", "cough", "cold", "flu", "diarrhea", "dehydration",
    "vomit", "vomiting", "nausea", "headache", "rash", "wound", "bite",
    "snake", "sting", "burn", "injury", "swelling", "swollen",
    "dizzy", "dizziness",
    # Body / conditions (everyday, non-clinical language) — added because
    # real patients describe symptoms this way far more often than with
    # clinical vocabulary. See module docstring, point 2.
    "tired", "fatigue", "weak", "weakness", "thirsty", "thirst",
    "sick", "unwell", "ill", "hurts", "hurting", "sore", "cramps", "cramp",
    "faint", "fainting", "giddy", "shivering", "chills", "itchy", "itching",
    "numb", "numbness", "wheeze", "wheezing", "bleeding", "bleed",
    "allergic", "allergy", "appetite", "urinate", "urination",
    "weight loss", "losing weight", "can't sleep", "cannot sleep",
    "not feeling well", "feel sick", "throwing up",
    # Conditions covered by the knowledge base
    "diabetes", "diabetic", "sugar level", "hypertension", "blood pressure",
    "bp", "malaria", "pregnant", "pregnancy", "nutrition", "diet",
    "paracetamol", "dosage", "stress", "anxiety", "depression",
    "mental health", "sleep", "std", "sti", "sexually transmitted",
    # People / care contexts
    "child", "baby", "infant", "mother", "patient",
]

# Pre-compiled word-boundary patterns, built once at import time rather than
# on every call. \b matches a word boundary, so "ache" matches the standalone
# word "ache" but not the "ache" inside "cache" — this is what actually fixes
# the false-positive problem described above.
_KEYWORD_PATTERNS = [
    re.compile(r"\b" + re.escape(keyword) + r"\b")
    for keyword in MEDICAL_KEYWORDS
]


def is_medical_question(query: str) -> bool:
    """
    Return True if `query` contains at least one medical/health keyword as
    a whole word (or whole phrase, for multi-word entries like "first aid").
    Case-insensitive, word-boundary matching — deliberately simple so it's
    fast and doesn't depend on an extra model call.
    """
    query_lower = query.lower()
    return any(pattern.search(query_lower) for pattern in _KEYWORD_PATTERNS)