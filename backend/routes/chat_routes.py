"""
backend/routes/chat_routes.py — Phase 16: FastAPI Wiring

POST /chat and GET /chat/history — both require a valid logged-in user.

This is the one place Phase 16 changes behavior versus main.py's CLI
loop: main.py keeps conversation_history in a local Python variable that
disappears the moment the process exits. Here, every turn is written to
the chat_messages table (Phase 14), so a user's conversation survives
across logins, restarts, and devices — GET /chat/history is what reads
it back.

The chatbot instance itself is NOT created in this file. It's created
once in main.py at startup (loading the model is expensive) and reached
here via request.app.state.bot — see main.py's lifespan function for why.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.db.models import ChatMessage, PatientProfile, User, UserCondition
from backend.deps import get_current_user, get_db
from backend.schemas import ChatHistoryEntry, ChatRequest, ChatResponse, ChatSource

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def send_message(
    chat_request: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bot = request.app.state.bot

    # Informal step toward Phase 21 (structured memory), using data that
    # already exists from Phase 17 registration rather than waiting for
    # the full profile/memory phases: give the model the patient's name
    # and the condition(s) they registered with, so it can address them
    # by name and factor in known conditions without yet building full
    # symptom/medication fact-tracking. Queried fresh every request (not
    # cached on the user object) so an edited condition list is picked up
    # immediately, not just at login.
    condition_rows = (
        db.query(UserCondition.condition_name)
        .filter(UserCondition.user_id == current_user.id)
        .all()
    )
    condition_names = [row[0] for row in condition_rows]

    # Single-workflow rebuild: the chatbot should act like a doctor who
    # already has the patient's chart open, not just their name. Pull the
    # full Patient History record (if one exists) and fold every filled-in
    # field into the system context, not just age -- see chat_routes.py
    # module docstring. Queried fresh every request (not cached on the
    # user object) so an edited Patient History page is picked up
    # immediately, not just at login.
    profile = (
        db.query(PatientProfile)
        .filter(PatientProfile.user_id == current_user.id)
        .first()
    )

    patient_context = f"\n\nThe patient you're speaking with is named {current_user.name}."
    if condition_names:
        patient_context += (
            " They have the following condition(s) on file: "
            + ", ".join(condition_names)
            + "."
        )
    if profile is not None:
        history_bits = []
        if profile.gender:
            history_bits.append(f"gender: {profile.gender}")
        if profile.blood_group:
            history_bits.append(f"blood group: {profile.blood_group}")
        if profile.height_cm:
            history_bits.append(f"height: {profile.height_cm} cm")
        if profile.weight_kg:
            history_bits.append(f"weight: {profile.weight_kg} kg")
        if profile.pregnancy_status:
            history_bits.append(f"pregnancy status: {profile.pregnancy_status}")
        if profile.smoking_status:
            history_bits.append(f"smoking status: {profile.smoking_status}")
        if profile.alcohol_status:
            history_bits.append(f"alcohol use: {profile.alcohol_status}")
        if profile.allergies:
            history_bits.append(f"known allergies: {profile.allergies}")
        if profile.medications:
            history_bits.append(f"current medicines: {profile.medications}")
        if profile.surgeries:
            history_bits.append(f"past surgeries: {profile.surgeries}")
        if profile.family_history:
            history_bits.append(f"family history: {profile.family_history}")
        if profile.medical_history:
            history_bits.append(f"other medical history: {profile.medical_history}")
        if history_bits:
            patient_context += (
                " Their Patient History record on file also shows -- "
                + "; ".join(history_bits)
                + "."
            )
        if profile.emergency_contact_name or profile.emergency_contact_phone:
            history_bits_emergency = " and ".join(
                filter(None, [profile.emergency_contact_name, profile.emergency_contact_phone])
            )
            patient_context += f" Their listed emergency contact is: {history_bits_emergency}."
    patient_context += (
        " Use this history as context where it's relevant to the question, "
        "the way a doctor would glance at a chart -- don't recite it back "
        "or force it into every reply."
    )
    system_message = bot.system_prompt + patient_context

    # Reconstruct conversation_history in the exact shape generate_response()
    # expects: [{"role": "system", ...}, {"role": "user"/"assistant", ...}, ...].
    # This mirrors main.py's own history initialization (system prompt
    # first), just rebuilt from the DB each request instead of kept in a
    # variable across a whole CLI session.
    past_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at)
        .all()
    )
    history = [{"role": "system", "content": system_message}] + [
        {"role": msg.role, "content": msg.content} for msg in past_messages
    ]

    # generate_response() never mutates the list it's given and returns a
    # NEW list (see chatbot.py's Phase 13 docstring) — updated_history is
    # discarded here on purpose, since this route persists the two new
    # turns to the database directly rather than keeping any history in
    # memory between requests. The next request rebuilds history fresh
    # from the DB the same way, from scratch, above.
    #
    # Phase 19: pass the patient's first name so an emergency response,
    # if one is triggered, can address them by name. Splitting on the
    # first space keeps this to a first name even if current_user.name is
    # stored as a full name — matches how the response templates read.
    first_name = current_user.name.split()[0] if current_user.name else None

    # age comes from the PatientProfile fetched above (a simple
    # None-if-missing lookup, not _get_or_create_profile from
    # profile_routes.py -- a chat request shouldn't have the side effect
    # of creating a profile row just because one doesn't exist yet).
    patient_age = profile.age if profile else None

    # UI redesign: include_meta=True asks generate_response() for a third
    # return value (is_emergency, sources) so the chat page can render the
    # full-width emergency banner and the "Sources" row without guessing
    # from the reply text — see src/chatbot.py's generate_response docstring.
    reply_text, _updated_history, meta = bot.generate_response(
        chat_request.message,
        history,
        patient_name=first_name,
        patient_age=patient_age,
        include_meta=True,
    )

    db.add_all([
        ChatMessage(user_id=current_user.id, role="user", content=chat_request.message),
        ChatMessage(user_id=current_user.id, role="assistant", content=reply_text),
    ])
    db.commit()

    return ChatResponse(
        reply=reply_text,
        is_emergency=meta["is_emergency"],
        sources=[ChatSource(**source) for source in meta["sources"]],
    )


@router.get("/history", response_model=list[ChatHistoryEntry])
def get_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at)
        .all()
    )