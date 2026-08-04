"""
evaluation/eval_set.py — Phase 11: Evaluation

Hardcoded list of test queries used by eval_runner.py to exercise the RAG
pipeline across a range of realistic and edge-case inputs.

Each entry is a dict with:
    "id"             — short unique identifier, in run order
    "category"       — one of "clean", "followup", "typo", "offtopic", "emergency"
    "query"          — the text sent to the chatbot
    "expected_topic" — the filename (without .txt) in knowledge_base/documents/
                        that retrieval SHOULD match, or None where that
                        doesn't apply (offtopic queries, and followups whose
                        own wording carries no topic signal on its own)
    "follows_previous" — only present on followup entries. True means this
                        entry continues the SAME conversation as the entry
                        directly above it (conversation_history is NOT reset
                        before it runs). Absent/False means it starts a fresh,
                        independent conversation.
"""

EVAL_SET = [
    # ------------------------------------------------------------------
    # 12 clean questions — one per document topic in knowledge_base/documents/
    # ------------------------------------------------------------------
    {"id": "clean_diabetes", "category": "clean",
     "query": "What are the symptoms of diabetes?",
     "expected_topic": "diabetes"},

    {"id": "clean_cold_flu", "category": "clean",
     "query": "What's the difference between a cold and the flu?",
     "expected_topic": "common_cold_flu"},

    {"id": "clean_fever_child", "category": "clean",
     "query": "My child has a fever, what should I do?",
     "expected_topic": "fever_in_a_child"},

    {"id": "clean_pregnancy", "category": "clean",
     "query": "What should I eat if I'm pregnant?",
     "expected_topic": "pregnancy_nutrition"},
    # Followup #1 — only makes sense right after the pregnancy question above.
    {"id": "followup_pregnancy_short", "category": "followup",
     "query": "short it",
     "expected_topic": None,
     "follows_previous": True},

    {"id": "clean_hypertension", "category": "clean",
     "query": "What is high blood pressure and why is it dangerous?",
     "expected_topic": "hypertension"},

    {"id": "clean_diarrhea", "category": "clean",
     "query": "How do I treat diarrhea at home?",
     "expected_topic": "diarrhea_dehydration"},

    {"id": "clean_vaccination", "category": "clean",
     "query": "What vaccines does a baby need in the first year?",
     "expected_topic": "vaccination_schedule"},
    # Followup #2 — only makes sense right after the vaccination question above.
    {"id": "followup_vaccination_adults", "category": "followup",
     "query": "what about adults, do they need any of these too",
     "expected_topic": None,
     "follows_previous": True},

    {"id": "clean_paracetamol", "category": "clean",
     "query": "What are the side effects of paracetamol?",
     "expected_topic": "paracetamol"},
    # Followup #3 — only makes sense right after the paracetamol question above.
    {"id": "followup_paracetamol_children", "category": "followup",
     "query": "is it safe for children too",
     "expected_topic": None,
     "follows_previous": True},

    {"id": "clean_stress", "category": "clean",
     "query": "I feel stressed and can't sleep, what can I do?",
     "expected_topic": "stress_mental_health"},

    {"id": "clean_snake_bite", "category": "clean",
     "query": "What should I do if someone gets bitten by a snake?",
     "expected_topic": "snake_bite"},

    {"id": "clean_malaria", "category": "clean",
     "query": "What are the common symptoms of malaria?",
     "expected_topic": "malaria"},

    {"id": "clean_chest_pain", "category": "clean",
     "query": "What could cause chest pain?",
     "expected_topic": "chest_pain"},
    # Followup #4 — only makes sense right after the chest pain question above.
    {"id": "followup_chest_pain_woman", "category": "followup",
     "query": "does it look different for a woman having it",
     "expected_topic": None,
     "follows_previous": True},

    # ------------------------------------------------------------------
    # 4 typo / misspelled queries — real medical questions, deliberately
    # misspelled, to see whether retrieval still finds the right topic.
    # ------------------------------------------------------------------
    {"id": "typo_diabetes", "category": "typo",
     "query": "what are the symtoms of diabetis",
     "expected_topic": "diabetes"},

    {"id": "typo_pregnancy", "category": "typo",
     "query": "what should i eat if i get pregent",
     "expected_topic": "pregnancy_nutrition"},

    {"id": "typo_malaria", "category": "typo",
     "query": "sings of malayria fever",
     "expected_topic": "malaria"},

    {"id": "typo_hypertension", "category": "typo",
     "query": "wat is hi blud presure",
     "expected_topic": "hypertension"},

    # ------------------------------------------------------------------
    # 3 offtopic queries — clearly non-medical, should not be forced into
    # any of the 12 topics.
    # ------------------------------------------------------------------
    {"id": "offtopic_weather", "category": "offtopic",
     "query": "what's the weather like today",
     "expected_topic": None},

    {"id": "offtopic_cricket", "category": "offtopic",
     "query": "who won the cricket match yesterday",
     "expected_topic": None},

    {"id": "offtopic_wifi", "category": "offtopic",
     "query": "how do I fix my wifi router",
     "expected_topic": None},

    # ------------------------------------------------------------------
    # 2 emergency / red-flag queries — response must escalate to urgent
    # care, not attempt to resolve the situation itself.
    # ------------------------------------------------------------------
    {"id": "emergency_snake_bite", "category": "emergency",
     "query": "someone just got bitten by a snake, what do I do right now",
     "expected_topic": "snake_bite"},

    {"id": "emergency_chest_pain", "category": "emergency",
     "query": "sudden chest pain and can't breathe, what should I do",
     "expected_topic": "chest_pain"},
]
