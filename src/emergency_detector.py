"""
src/emergency_detector.py — Phase 19: Emergency / Red-Flag Detection

A safety layer that runs BEFORE scope_guard.py, before retrieval, and
before the LLM ever sees the message. If a patient describes a genuine
emergency, this returns a fixed, deterministic response instead of a
generated one — a false negative here is far more costly than a false
negative in the ordinary scope gate, and a small model can hedge or
soften language in ways that are dangerous in this specific context, so
none of this is left to generation.

Design choice — templated, not model-generated:
    A single hard-coded sentence, repeated verbatim for every match, reads
    as an obvious canned bot response and can undermine trust at exactly
    the moment trust matters most. So each category (except suicidal
    crisis) has a few natural-language variants, one picked per message,
    with an optional {name} slot for light personalization. What never
    varies is the core instruction (call 1122 / go to the ER now) and,
    for suicidal crisis, the exact helpline number — those are fixed
    strings, not model output, so they can't be hedged, reworded, or
    dropped by generation.

Kept as its own keyword list, separate from src/scope_guard.py's
MEDICAL_KEYWORDS — that list is about "is this medical at all," this one
is about "is this an emergency," and conflating them would make both
harder to tune independently.
"""

import random
import re

# ---------------------------------------------------------------------------
# Sources for the fixed numbers below (do not change without re-verifying):
#   - 1122: Pakistan's national emergency number (police/fire/medical).
#   - Umang: Pakistan's 24/7 mental health helpline, run by clinical
#     psychologists, confirmed via umang.com.pk's own contact/FAQ pages.
# These are the one piece of content in this whole file that must never be
# left to random variation or model generation — the number itself has to
# be exactly right, every time.
# ---------------------------------------------------------------------------
NATIONAL_EMERGENCY_NUMBER = "1122"
SUICIDE_HELPLINE_NAME = "Umang"
SUICIDE_HELPLINE_NUMBER = "0311-7786264"


def _name_clause(patient_name: str | None, patient_age: int | None = None) -> str:
    """Builds the natural-language address clause every template slots in
    via {name_clause}: name, age, both, or neither — each reading as a
    normal sentence continuation, no dangling comma, no awkward gap.

    Age is deliberately folded into the same clause as the name (rather
    than added as a separate bolted-on sentence) so it reads like a doctor
    speaking directly to a specific young or old patient, not like a
    templated system inserting a data field. Kept out of suicidal_crisis
    entirely — callers should not pass age for that category, since age
    framing has no place in a supportive crisis message.
    """
    if patient_name and patient_age:
        return f", {patient_name} — especially at {patient_age}"
    if patient_name:
        return f", {patient_name}"
    if patient_age:
        return f", especially at {patient_age}"
    return ""


# Each category: keywords (substring match on the lowercased message) +
# a symptom phrase used to fill {symptom} in the templates + a list of
# natural-language response variants. Order in EMERGENCY_CATEGORIES below
# matters: suicidal_crisis is checked first, since it's the one category
# where a missed match is most costly and where phrasing can be indirect.
EMERGENCY_CATEGORIES = {
    "suicidal_crisis": {
        "keywords": [
            "kill myself", "end my life", "end it all", "suicidal",
            "suicide", "don't want to live", "dont want to live",
            "want to die", "no reason to live", "better off dead",
            "planning to kill myself", "thinking of suicide",
        ],
        "symptom": None,  # not used — this category has one fixed response
        # No variation here on purpose — accuracy of the number matters
        # more than variety in wording for this category.
        "responses": [
            "I'm really glad you told me this{name_clause}, and I want you "
            "to know you don't have to go through this alone. Please reach "
            f"out right now to {SUICIDE_HELPLINE_NAME}, Pakistan's 24/7 "
            f"mental health helpline, at {SUICIDE_HELPLINE_NUMBER} — "
            "they're there to listen, no judgment. If you're in immediate "
            f"danger, please call {NATIONAL_EMERGENCY_NUMBER} or go to "
            "your nearest emergency room.",
        ],
    },
    "chest_pain": {
        "keywords": [
            "chest pain", "chest tightness", "pain in my chest",
            "pressure in my chest", "my chest hurts", "chest is hurting",
            "tightness in my chest",
        ],
        "symptom": "chest pain like this",
        "responses": [
            "That's not something to wait on{name_clause} — {symptom} can "
            "be a sign of a heart problem, and every minute matters here. "
            f"Please call {NATIONAL_EMERGENCY_NUMBER} or get to the "
            "nearest emergency room right now, don't try to push through it.",

            "I want you to stop and take this seriously{name_clause}. "
            "{symptom_cap} needs to be checked by a doctor immediately, "
            f"not later today — call {NATIONAL_EMERGENCY_NUMBER} or have "
            "someone take you to the ER now.",

            "This could be serious{name_clause}, and I'd rather you be "
            "safe than sorry. Please get emergency help right away — call "
            f"{NATIONAL_EMERGENCY_NUMBER} or head to the nearest hospital "
            "now — rather than waiting to see if it passes.",
        ],
    },
    "breathing": {
        "keywords": [
            "can't breathe", "cant breathe", "difficulty breathing",
            "trouble breathing", "shortness of breath",
            "struggling to breathe", "can't catch my breath",
            "cant catch my breath", "gasping for air",
        ],
        "symptom": "difficulty breathing like this",
        "responses": [
            "Not being able to breathe properly is an emergency{name_clause}"
            " — please don't wait this out. Call "
            f"{NATIONAL_EMERGENCY_NUMBER} right now or get to the nearest "
            "emergency room immediately.",

            "This needs urgent attention{name_clause}. {symptom_cap} can "
            "get worse quickly, so please call "
            f"{NATIONAL_EMERGENCY_NUMBER} or have someone get you to an "
            "ER right now, not after resting a bit.",

            "I don't want you to wait on this{name_clause} — please seek "
            f"emergency care immediately, call {NATIONAL_EMERGENCY_NUMBER}"
            " or go straight to the nearest hospital.",
        ],
    },
    "unconscious_stroke": {
        "keywords": [
            "lost consciousness", "passed out", "fainted and won't wake",
            "fainted and wont wake", "unresponsive", "can't wake him up",
            "cant wake him up", "can't wake her up", "cant wake her up",
            "slurred speech", "face drooping", "drooping face",
            "one side of my body is numb", "sudden numbness",
            "sudden confusion", "can't speak properly",
            "cant speak properly", "face is drooping",
        ],
        "symptom": "symptoms like these",
        "responses": [
            "{symptom_cap} can be signs of a stroke or another serious "
            "emergency{name_clause}, and time matters a lot here. Please "
            f"call {NATIONAL_EMERGENCY_NUMBER} right now or get to the "
            "nearest emergency room immediately — don't wait to see if "
            "it improves.",

            "This sounds urgent{name_clause}. Loss of consciousness, "
            "sudden numbness, or trouble speaking need emergency "
            f"evaluation right away — please call {NATIONAL_EMERGENCY_NUMBER}"
            " or head to the ER now.",

            "Please treat this as an emergency{name_clause} — "
            "{symptom} can point to something serious happening right "
            f"now. Call {NATIONAL_EMERGENCY_NUMBER} or get to a hospital "
            "immediately.",
        ],
    },
    "bleeding": {
        "keywords": [
            "severe bleeding", "won't stop bleeding", "wont stop bleeding",
            "bleeding a lot", "heavy bleeding", "blood won't stop",
            "blood wont stop", "deep cut bleeding", "bleeding heavily",
        ],
        "symptom": "bleeding like this",
        "responses": [
            "{symptom_cap} needs emergency care right now{name_clause} — "
            "please apply firm pressure to the area and call "
            f"{NATIONAL_EMERGENCY_NUMBER} or get to the nearest emergency "
            "room immediately.",

            "This is urgent{name_clause} — please don't wait. Apply "
            "steady pressure to slow the bleeding and call "
            f"{NATIONAL_EMERGENCY_NUMBER} or head to the ER right away.",

            "I want you to get help immediately{name_clause}. Keep "
            "pressure on the area and call "
            f"{NATIONAL_EMERGENCY_NUMBER} or get to a hospital right now.",
        ],
    },
    "seizure": {
        "keywords": [
            "having a seizure", "is having a seizure", "seizure right now",
            "convulsions", "convulsing", "fit and shaking uncontrollably",
            "shaking uncontrollably and unresponsive",
        ],
        "symptom": "a seizure like this",
        "responses": [
            "{symptom_cap} is a medical emergency{name_clause} — please "
            "keep the area around them clear and safe, don't hold them "
            f"down, and call {NATIONAL_EMERGENCY_NUMBER} right now.",

            "Please get emergency help immediately{name_clause}. Keep "
            "them safe from nearby objects and call "
            f"{NATIONAL_EMERGENCY_NUMBER} — this needs medical attention "
            "right now, not after it ends.",

            "This needs urgent care{name_clause} — call "
            f"{NATIONAL_EMERGENCY_NUMBER} immediately and stay with them "
            "until help arrives.",
        ],
    },
    "allergic_reaction": {
        "keywords": [
            "severe allergic reaction", "throat closing",
            "swelling of my throat", "anaphylaxis",
            "face is swelling and i can't breathe",
            "face is swelling and i cant breathe",
            "hives and difficulty breathing", "throat is closing up",
            "swelling and can't breathe", "swelling and cant breathe",
        ],
        "symptom": "a reaction like this",
        "responses": [
            "{symptom_cap} can be life-threatening{name_clause} — please "
            f"call {NATIONAL_EMERGENCY_NUMBER} right now or get to the "
            "nearest emergency room immediately. If you have an epinephrine "
            "auto-injector, use it now.",

            "This is an emergency{name_clause} — swelling with difficulty "
            f"breathing needs urgent treatment. Call "
            f"{NATIONAL_EMERGENCY_NUMBER} immediately, don't wait to see "
            "if it settles on its own.",

            "Please get emergency help right away{name_clause} — "
            "{symptom} needs immediate medical attention. Call "
            f"{NATIONAL_EMERGENCY_NUMBER} or head straight to the ER.",
        ],
    },
}


def detect_emergency(user_input: str) -> str | None:
    """Returns the matched category key (e.g. "chest_pain") if user_input
    contains an emergency phrase, or None if it doesn't. Substring match on
    the lowercased message, deliberately simple and fast — this runs on
    every single message, before anything else, so it needs to be cheap
    and predictable, not a model call.

    Category order matters: suicidal_crisis is checked first, since it's
    the category where an indirect phrasing is most likely and a miss is
    most costly. All other categories are independent of each other, so
    their relative order doesn't matter — a message rarely matches two.
    """
    lowered = user_input.lower()

    for category, data in EMERGENCY_CATEGORIES.items():
        for phrase in data["keywords"]:
            # Word-boundary-ish check via regex escape, so "seizure" inside
            # a longer unrelated word doesn't false-positive — still a
            # plain substring match on multi-word phrases, since those are
            # already specific enough not to need boundaries.
            if re.search(re.escape(phrase), lowered):
                return category

    return None


def get_emergency_response(
    category: str,
    patient_name: str | None = None,
    patient_age: int | None = None,
) -> str:
    """Builds the actual response text for a detected category: picks one
    variant at random (always the same single response for
    suicidal_crisis, which has only one), fills in {name_clause} and
    {symptom}/{symptom_cap} where present.

    patient_age is ignored for suicidal_crisis on purpose (see
    _name_clause) — every other category uses it to sharpen urgency,
    e.g. "especially at 19", since age is exactly the kind of detail
    that makes a canned safety message land as a real, specific warning
    instead of a generic one.

    Raises KeyError if category isn't a real key — that's intentional,
    it means detect_emergency() and this got out of sync, which should
    fail loudly during testing rather than silently return nothing.
    """
    data = EMERGENCY_CATEGORIES[category]
    template = random.choice(data["responses"])

    age_for_clause = None if category == "suicidal_crisis" else patient_age
    symptom = data["symptom"] or ""
    return template.format(
        name_clause=_name_clause(patient_name, age_for_clause),
        symptom=symptom,
        symptom_cap=symptom[:1].upper() + symptom[1:] if symptom else "",
    )