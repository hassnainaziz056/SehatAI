"""
backend/routes/dashboard_routes.py -- UI/UX redesign: the Dashboard is
now the app's landing page after login/wizard, replacing chat.html in
that role. This single GET /dashboard aggregates everything the
Dashboard's cards need in one request, rather than the frontend making
four or five separate calls on load -- deliberately a read-only,
aggregate-only endpoint; nothing here writes anything (medicine "taken"
toggles go through medication_routes.py instead).

No new business logic lives here -- every number/row below is a plain
query or a small derived computation over tables that already exist
(UserCondition, PatientProfile, Medication, MedicationDoseLog,
ChatMessage). The chatbot, RAG pipeline, and safety layers are
completely untouched by this file.
"""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.db.models import (
    ChatMessage,
    Medication,
    MedicationDoseLog,
    PatientProfile,
    User,
    UserCondition,
)
from backend.deps import get_current_user, get_db
from backend.schemas import (
    ConversationSummary,
    DashboardResponse,
    HealthSummary,
    ScheduleSlot,
    TimelineEvent,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Display-only labels for each slot -- matches the example schedule times
# used throughout the product brief (8:00 AM / 2:00 PM / 9:00 PM). Not
# configurable per-patient yet; a future "customize my schedule" setting
# would live here.
_SLOT_LABELS = {"morning": "8:00 AM", "afternoon": "2:00 PM", "night": "9:00 PM"}
# Slots are considered "due" once the local hour reaches this threshold --
# used only to distinguish "pending" (due today, not yet taken) from
# "upcoming" (later today) for slots that haven't been marked taken.
_SLOT_DUE_HOUR = {"morning": 8, "afternoon": 14, "night": 21}


def _build_health_summary(user: User, profile: PatientProfile | None, conditions: list[str]) -> HealthSummary:
    return HealthSummary(
        name=user.name,
        age=profile.age if profile else None,
        gender=profile.gender if profile else None,
        blood_group=profile.blood_group if profile else None,
        conditions=conditions,
        allergies=profile.allergies if profile else None,
    )


def _build_medicine_schedule(db: Session, user_id: int) -> list[ScheduleSlot]:
    today = date.today().isoformat()
    current_hour = datetime.now(timezone.utc).hour

    active_meds = (
        db.query(Medication)
        .filter(Medication.user_id == user_id, Medication.active.is_(True))
        .all()
    )

    taken_today = {
        (log.medication_id, log.slot)
        for log in db.query(MedicationDoseLog).filter(
            MedicationDoseLog.user_id == user_id,
            MedicationDoseLog.dose_date == today,
        )
    }

    schedule: list[ScheduleSlot] = []
    for medication in active_meds:
        for slot in ("morning", "afternoon", "night"):
            if not getattr(medication, slot):
                continue
            if (medication.id, slot) in taken_today:
                status = "taken"
            elif current_hour >= _SLOT_DUE_HOUR[slot]:
                status = "pending"
            else:
                status = "upcoming"
            schedule.append(ScheduleSlot(
                medication_id=medication.id,
                medication_name=medication.name,
                dosage=medication.dosage,
                slot=slot,
                slot_time_label=_SLOT_LABELS[slot],
                status=status,
            ))

    # Chronological through the day: morning, afternoon, night.
    slot_order = {"morning": 0, "afternoon": 1, "night": 2}
    schedule.sort(key=lambda s: slot_order[s.slot])
    return schedule


def _build_health_timeline(db: Session, user_id: int, limit: int = 10) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []

    for condition in db.query(UserCondition).filter(UserCondition.user_id == user_id):
        events.append(TimelineEvent(
            event_type="condition",
            title=f"{condition.condition_name} added to your record",
            detail=None,
            occurred_at=condition.added_at,
        ))

    for medication in db.query(Medication).filter(Medication.user_id == user_id):
        events.append(TimelineEvent(
            event_type="medication",
            title=f"{medication.name} started",
            detail=medication.dosage,
            occurred_at=medication.created_at,
        ))

    events.sort(key=lambda e: e.occurred_at, reverse=True)
    return events[:limit]


def _build_recent_conversations(db: Session, user_id: int, limit: int = 3) -> list[ConversationSummary]:
    """Groups chat_messages by calendar date as a simple stand-in for
    "session" -- there's no explicit session/thread id on ChatMessage
    (Phase 14's schema is a flat per-user log), so grouping by day is the
    cheapest reasonable proxy: a patient's conversation on a given day is
    treated as one "conversation" card, titled by their first message
    that day. Good enough for a recency-ordered summary widget; a real
    session boundary (e.g. a gap-based cutoff) is a reasonable follow-up
    if this ever needs to be more precise.
    """
    user_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user_id, ChatMessage.role == "user")
        .order_by(ChatMessage.created_at.desc())
        .all()
    )

    by_day: dict[str, list[ChatMessage]] = {}
    for message in user_messages:
        day_key = message.created_at.date().isoformat()
        by_day.setdefault(day_key, []).append(message)

    summaries: list[ConversationSummary] = []
    for day_key, messages in sorted(by_day.items(), reverse=True)[:limit]:
        messages_chronological = sorted(messages, key=lambda m: m.created_at)
        summaries.append(ConversationSummary(
            first_message=messages_chronological[0].content,
            last_message_at=messages_chronological[-1].created_at,
            message_count=len(messages_chronological),
        ))
    return summaries


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(PatientProfile).filter(PatientProfile.user_id == current_user.id).first()
    condition_names = [
        row[0] for row in
        db.query(UserCondition.condition_name).filter(UserCondition.user_id == current_user.id).all()
    ]

    return DashboardResponse(
        health_summary=_build_health_summary(current_user, profile, condition_names),
        medicine_schedule_today=_build_medicine_schedule(db, current_user.id),
        health_timeline=_build_health_timeline(db, current_user.id),
        recent_conversations=_build_recent_conversations(db, current_user.id),
        profile_completed=current_user.profile_completed,
    )