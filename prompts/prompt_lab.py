"""
prompts/prompt_lab.py — Phase 6: Prompt Engineering

Runs every prompt in PROMPT_LIBRARY through HealthcareChatbot.generate_response()
and saves a single Markdown transcript of prompts + responses to
prompts/results/run_<timestamp>.md.

This script only produces the raw transcript. The actual Phase 6 write-up
(Notes + Summary in prompt_library.md) still has to be filled in by hand
after reading the transcript.

Usage:
    python -m prompts.prompt_lab
"""

import os
from datetime import datetime

from src.chatbot import HealthcareChatbot


# ---------------------------------------------------------------------------
# 1. Prompt library — hand-copied verbatim from prompts/prompt_library.md
#    (12 topics x weak/better/best = 36 entries, kept in the same order as
#    the markdown file so the transcript reads the same way).
# ---------------------------------------------------------------------------

PROMPT_LIBRARY = [
    # 1. Diabetes
    {"topic": "Diabetes", "quality": "weak",
     "prompt": "Tell me about diabetes."},
    {"topic": "Diabetes", "quality": "better",
     "prompt": "Explain diabetes to a 12-year-old in Urdu."},
    {"topic": "Diabetes", "quality": "best",
     "prompt": "Explain diabetes to a rural patient with no medical background. "
               "Mention symptoms, lifestyle changes, and when they should visit a doctor."},

    # 2. Common Cold / Flu
    {"topic": "Common Cold / Flu", "quality": "weak",
     "prompt": "What is flu?"},
    {"topic": "Common Cold / Flu", "quality": "better",
     "prompt": "Explain the difference between a common cold and the flu in simple terms."},
    {"topic": "Common Cold / Flu", "quality": "best",
     "prompt": "A rural patient has fever, body ache, and sore throat for 2 days. "
               "Explain whether this sounds like a cold or flu, what home care helps, "
               "and what symptoms would mean they should see a doctor immediately."},

    # 3. Fever in a Child
    {"topic": "Fever in a Child", "quality": "weak",
     "prompt": "My child has fever."},
    {"topic": "Fever in a Child", "quality": "better",
     "prompt": "My 3-year-old has a fever of 101°F. What should I do?"},
    {"topic": "Fever in a Child", "quality": "best",
     "prompt": "My 3-year-old has had a fever of 101°F for one day, is eating less but "
               "still playful. As a rural parent with no nearby clinic, what safe home "
               "care can I give, and what warning signs mean I must seek emergency care "
               "right away?"},

    # 4. Pregnancy Nutrition
    {"topic": "Pregnancy Nutrition", "quality": "weak",
     "prompt": "Pregnancy diet?"},
    {"topic": "Pregnancy Nutrition", "quality": "better",
     "prompt": "What should a pregnant woman eat for good nutrition?"},
    {"topic": "Pregnancy Nutrition", "quality": "best",
     "prompt": "Explain simple, locally affordable nutrition guidance for a pregnant "
               "woman in rural Sindh in her second trimester, including foods to avoid "
               "and danger signs that need urgent medical attention."},

    # 5. High Blood Pressure (Hypertension)
    {"topic": "High Blood Pressure (Hypertension)", "quality": "weak",
     "prompt": "What is high BP?"},
    {"topic": "High Blood Pressure (Hypertension)", "quality": "better",
     "prompt": "Explain high blood pressure and why it's dangerous."},
    {"topic": "High Blood Pressure (Hypertension)", "quality": "best",
     "prompt": "Explain high blood pressure to someone who just got diagnosed and has "
               "no medical background — what it means, everyday lifestyle changes that "
               "help, and which symptoms mean they need to see a doctor urgently."},

    # 6. Diarrhea & Dehydration
    {"topic": "Diarrhea & Dehydration", "quality": "weak",
     "prompt": "Diarrhea treatment?"},
    {"topic": "Diarrhea & Dehydration", "quality": "better",
     "prompt": "How do I treat diarrhea at home?"},
    {"topic": "Diarrhea & Dehydration", "quality": "best",
     "prompt": "An adult has had watery diarrhea for one day with no blood. Explain safe "
               "home rehydration steps using things available in a rural household, and "
               "the warning signs that mean they should go to a clinic immediately."},

    # 7. Vaccination Schedule
    {"topic": "Vaccination Schedule", "quality": "weak",
     "prompt": "Vaccines for babies?"},
    {"topic": "Vaccination Schedule", "quality": "better",
     "prompt": "What vaccines does a baby need in the first year?"},
    {"topic": "Vaccination Schedule", "quality": "best",
     "prompt": "Explain, in simple language for a first-time rural mother, the general "
               "purpose of routine childhood vaccination and why keeping to the schedule "
               "matters — without giving exact dosing, since that should come from a "
               "health worker."},

    # 8. Medicine / Side Effects (Paracetamol)
    {"topic": "Medicine / Side Effects (Paracetamol)", "quality": "weak",
     "prompt": "Paracetamol side effects?"},
    {"topic": "Medicine / Side Effects (Paracetamol)", "quality": "better",
     "prompt": "What are the side effects of paracetamol?"},
    {"topic": "Medicine / Side Effects (Paracetamol)", "quality": "best",
     "prompt": "A rural patient wants to know what paracetamol is commonly used for and "
               "general side effects to watch for — explain clearly, and remind them not "
               "to exceed the dose on the package or a doctor's/pharmacist's instructions."},

    # 9. Stress / Mental Health
    {"topic": "Stress / Mental Health", "quality": "weak",
     "prompt": "I feel stressed."},
    {"topic": "Stress / Mental Health", "quality": "better",
     "prompt": "What can I do about ongoing stress and poor sleep?"},
    {"topic": "Stress / Mental Health", "quality": "best",
     "prompt": "Explain, with empathy and without judgement, some everyday coping "
               "strategies for someone in a rural area dealing with chronic stress and "
               "poor sleep, and gently note when it's worth talking to a health worker "
               "about how they're feeling."},

    # 10. Snake Bite (Emergency / Red-Flag Test)
    {"topic": "Snake Bite (Emergency / Red-Flag Test)", "quality": "weak",
     "prompt": "Snake bite help?"},
    {"topic": "Snake Bite (Emergency / Red-Flag Test)", "quality": "better",
     "prompt": "What should I do if someone gets bitten by a snake?"},
    {"topic": "Snake Bite (Emergency / Red-Flag Test)", "quality": "best",
     "prompt": "Someone in a rural village was just bitten by a snake. Give clear, "
               "immediate first-aid guidance and be explicit that this is a medical "
               "emergency requiring the nearest hospital as fast as possible."},

    # 11. Malaria Symptoms
    {"topic": "Malaria Symptoms", "quality": "weak",
     "prompt": "Malaria symptoms?"},
    {"topic": "Malaria Symptoms", "quality": "better",
     "prompt": "What are the common symptoms of malaria?"},
    {"topic": "Malaria Symptoms", "quality": "best",
     "prompt": "A rural patient has recurring fever with chills and sweating over the "
               "past few days. Explain that this could suggest several possible "
               "illnesses including malaria, why lab testing matters for a proper "
               "diagnosis, and when to seek care urgently."},

    # 12. Chest Pain (Emergency / Red-Flag Test)
    {"topic": "Chest Pain (Emergency / Red-Flag Test)", "quality": "weak",
     "prompt": "Chest pain, what is it?"},
    {"topic": "Chest Pain (Emergency / Red-Flag Test)", "quality": "better",
     "prompt": "What could cause chest pain?"},
    {"topic": "Chest Pain (Emergency / Red-Flag Test)", "quality": "best",
     "prompt": "A 50-year-old is having sudden chest pain with shortness of breath. "
               "Explain briefly that this needs immediate emergency care and why, "
               "without trying to diagnose the cause."},
]


# ---------------------------------------------------------------------------
# 2. Helpers
# ---------------------------------------------------------------------------

def reset_history(bot: HealthcareChatbot) -> None:
    """Reset conversation_history back to just the system message.

    This keeps every prompt independent so earlier prompts in the run don't
    bias later responses (each entry gets a fresh, single-turn conversation).
    """
    system_message = bot.conversation_history[0]
    bot.conversation_history = [system_message]


def build_transcript(results: list[dict]) -> str:
    """Build the full Markdown transcript string, grouped by topic in the
    same order as PROMPT_LIBRARY, with weak/better/best under each topic.
    """
    lines = []
    lines.append(f"# SehatAI Prompt Lab — Run {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("Auto-generated transcript. Read alongside `prompt_library.md` to fill in Notes/Summary.")
    lines.append("")

    # Group results by topic while preserving first-seen order.
    topics_in_order = []
    by_topic = {}
    for entry in results:
        topic = entry["topic"]
        if topic not in by_topic:
            by_topic[topic] = []
            topics_in_order.append(topic)
        by_topic[topic].append(entry)

    for topic in topics_in_order:
        lines.append(f"## {topic}")
        lines.append("")
        for entry in by_topic[topic]:
            lines.append(f"### {entry['quality'].capitalize()}")
            lines.append("")
            lines.append(f"**Prompt:** {entry['prompt']}")
            lines.append("")
            if entry.get("error"):
                lines.append(f"**Response:** _ERROR: {entry['error']}_")
            else:
                lines.append(f"**Response:**\n\n{entry['response']}")
            lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3. Main run
# ---------------------------------------------------------------------------

def main() -> None:
    # Model loading is slow, so we instantiate the chatbot exactly once and
    # reuse it for every prompt in the library.
    bot = HealthcareChatbot()

    results = []
    total = len(PROMPT_LIBRARY)

    for i, entry in enumerate(PROMPT_LIBRARY, start=1):
        topic = entry["topic"]
        quality = entry["quality"]
        prompt_text = entry["prompt"]

        print(f"[{i}/{total}] Running: {topic} ({quality})")

        # Fresh single-turn conversation for every prompt.
        reset_history(bot)

        result_entry = {"topic": topic, "quality": quality, "prompt": prompt_text}
        try:
            response_text = bot.generate_response(prompt_text)
            result_entry["response"] = response_text
        except Exception as e:
            # One bad prompt shouldn't kill the whole run — log it and move on.
            result_entry["error"] = str(e)
            print(f"    [ERROR] {e}")

        results.append(result_entry)

    # Write the transcript.
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(results_dir, f"run_{timestamp}.md")

    transcript = build_transcript(results)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(transcript)

    print(f"\n[DONE] Transcript written to {out_path}")


if __name__ == "__main__":
    main()
