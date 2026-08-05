"""
backend/db/models.py — Phase 14: Database Layer (+ Phase 15: password_hash)

Defines the three tables the future multi-user web platform is built on:
  User            — one row per registered patient. Phase 15 added
                    password_hash (bcrypt hash, never a raw password —
                    see backend/auth/security.py).
  UserCondition   — one row per health condition a patient selected at
                    registration (e.g. "diabetes", "hypertension"). A
                    separate table rather than a single comma-separated
                    column, so it stays queryable — "how many patients
                    have hypertension" is a plain COUNT, not string
                    parsing.
  ChatMessage     — one row per turn in a patient's conversation history.
                    role/content deliberately mirror the exact shape
                    already used throughout chatbot.py's
                    conversation_history ({"role": ..., "content": ...}),
                    so reconstructing a conversation_history list from the
                    database later is a straight read, no translation.

This file only defines the schema (table shape + relationships). It does
not open a connection or create anything on disk — that's session.py and
init_db.py's job. Nothing in here touches src/chatbot.py, knowledge_base/,
or main.py; this is new, independent storage machinery sitting next to
the existing chatbot, not a replacement for any of it.

Uses the modern (SQLAlchemy 2.0) declarative style: a DeclarativeBase
subclass as the shared base, and Mapped[...] / mapped_column(...)
type-annotated columns instead of the older Column(...) style.
"""

from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    """Current UTC time, used as the default for every created_at/added_at
    column below. A small wrapper (rather than passing datetime.utcnow
    directly) because that method is deprecated as of Python 3.12+ in
    favor of timezone-aware datetimes — this keeps that fix in one place.
    """
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Shared declarative base — every model below inherits from this.

    Base.metadata is what init_db.py hands to create_all() to actually
    build the tables on disk, and it's what test_db.py imports models
    through, so all three tables get registered on it just by importing
    this module.
    """
    pass


class User(Base):
    """One row per registered patient/account.

    Phase 15 adds password_hash — a bcrypt hash, never the raw password
    (see backend/auth/security.py for hashing/verification).

    UI redesign (registration/wizard split): `name` is now nullable.
    Registration (POST /register) only ever collects email + password —
    it deliberately asks for nothing medical or identifying beyond that.
    `name` is filled in during Step 1 of the mandatory post-login Patient
    Profile Wizard instead (see profile_routes.py's /profile/wizard
    endpoint), the same moment `profile_completed` flips to True. A user
    row can therefore legitimately have name=None for the short window
    between registering and finishing the wizard.

    `profile_completed` is the single source of truth login.js/dashboard
    access checks use to decide "does this user need the wizard, or can
    they go straight to the dashboard" — deliberately its own boolean
    rather than inferring completion from "does a PatientProfile row
    exist," since a lazily-created empty PatientProfile row (Phase 20's
    existing _get_or_create_profile pattern) would otherwise look
    indistinguishable from "wizard finished."
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    profile_completed: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    # user.conditions -> list[UserCondition], user.messages -> list[ChatMessage].
    # cascade="all, delete-orphan" means deleting a User also cleans up their
    # rows in both child tables instead of leaving orphaned rows behind.
    # order_by on messages means user.messages always comes back in chat
    # order (oldest first) without every caller having to remember to sort
    # it themselves.
    conditions: Mapped[list["UserCondition"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="user", cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )
    # One-to-one: uselist=False means user.profile is a single
    # PatientProfile object (or None), not a list — matches how a patient
    # has exactly one profile, unlike conditions/messages which are
    # naturally many-per-user.
    profile: Mapped["PatientProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    medications: Mapped[list["Medication"]] = relationship(
        back_populates="user", cascade="all, delete-orphan",
        order_by="Medication.created_at",
    )
    dose_logs: Mapped[list["MedicationDoseLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, name={self.name!r}, email={self.email!r})"


class UserCondition(Base):
    """One row per health condition a patient has on file.

    e.g. a patient with diabetes AND hypertension gets two rows here, not
    one row with a "diabetes,hypertension" string — see module docstring.
    """

    __tablename__ = "user_conditions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    condition_name: Mapped[str] = mapped_column(String, nullable=False)
    added_at: Mapped[datetime] = mapped_column(default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="conditions")

    def __repr__(self) -> str:
        return f"UserCondition(user_id={self.user_id!r}, condition_name={self.condition_name!r})"


class ChatMessage(Base):
    """One row per turn (user or assistant) in a patient's conversation.

    role/content match conversation_history's existing {"role", "content"}
    shape exactly — see module docstring. created_at is what lets a
    conversation be reconstructed in the right order later:
        SELECT role, content FROM chat_messages
        WHERE user_id = ? ORDER BY created_at
    """

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"ChatMessage(user_id={self.user_id!r}, role={self.role!r})"


class PatientProfile(Base):
    """Phase 20: the expanded health profile — one row per user, created
    lazily (see profile_routes.py's _get_or_create_profile) the first time
    a patient's profile is read or written, so accounts registered before
    this phase existed don't need a migration script to get a row.

    Every field is nullable. A patient filling in "just age and
    allergies" and leaving the rest blank is the normal case, not an
    error — this mirrors the conditions checklist's "skip if none apply"
    pattern from Phase 17, just for free-form/numeric fields instead of a
    fixed list.

    Deliberately one wide table rather than several normalized ones
    (e.g. a separate `medications` table): none of these fields are
    naturally many-per-patient the way conditions are, and Phase 24's
    medication *tracker* (a real many-rows-per-patient list with
    allergy cross-checks) is intentionally still its own future table,
    not this free-text `medications` field, which is closer to "what a
    patient tells a doctor at intake" than structured data.
    """

    __tablename__ = "patient_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # unique=True enforces the one-to-one relationship with User at the
    # database level, not just in the ORM's relationship() config above.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)

    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String, nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String, nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    pregnancy_status: Mapped[str | None] = mapped_column(String, nullable=True)
    smoking_status: Mapped[str | None] = mapped_column(String, nullable=True)
    # UI redesign — Wizard Step 2 (Medical History) asks for alcohol use
    # alongside smoking status; added as its own nullable column rather
    # than folded into medical_history free text, so it stays a
    # structured, queryable field the same way smoking_status is.
    alcohol_status: Mapped[str | None] = mapped_column(String, nullable=True)
    family_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Free text, not structured lists — Phase 21 (structured memory) and
    # Phase 24 (medication tracker) are where these become queryable,
    # per-item data; here they're intake-style notes a doctor would read
    # once, not something the app parses.
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    medications: Mapped[str | None] = mapped_column(Text, nullable=True)
    surgeries: Mapped[str | None] = mapped_column(Text, nullable=True)
    medical_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String, nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    user: Mapped["User"] = relationship(back_populates="profile")

    def __repr__(self) -> str:
        return f"PatientProfile(user_id={self.user_id!r}, age={self.age!r})"


class Medication(Base):
    """UI redesign — Wizard Step 3 / Medicines page: a real, structured,
    many-per-patient medicine list — the thing PatientProfile.medications
    (free text) was explicitly NOT meant to become, per that field's own
    docstring above. This is that "intentionally still its own future
    table" now existing.

    `morning` / `afternoon` / `night` are independent booleans rather than
    a single "time of day" string, since a medicine is very often taken
    at more than one of the three (e.g. a course taken morning AND
    night) — three booleans model that directly instead of needing a
    comma-separated string or a second junction table.

    `active` lets the Medicines page distinguish current vs. past
    medicines without deleting history — a stopped medicine is still
    part of the patient's medical record and should still show up in the
    Health Timeline as "started"/"stopped" events, so it's soft-deactivated,
    not removed.
    """

    __tablename__ = "medications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    name: Mapped[str] = mapped_column(String, nullable=False)
    dosage: Mapped[str | None] = mapped_column(String, nullable=True)
    frequency: Mapped[str | None] = mapped_column(String, nullable=True)
    morning: Mapped[bool] = mapped_column(default=False, nullable=False)
    afternoon: Mapped[bool] = mapped_column(default=False, nullable=False)
    night: Mapped[bool] = mapped_column(default=False, nullable=False)
    start_date: Mapped[str | None] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="medications")
    dose_logs: Mapped[list["MedicationDoseLog"]] = relationship(
        back_populates="medication", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"Medication(user_id={self.user_id!r}, name={self.name!r})"


class MedicationDoseLog(Base):
    """One row per "this dose was marked taken" tap on the Dashboard's
    Medicine Timeline widget or the Medicines page. Deliberately a log of
    taken doses, not a log of every scheduled slot — a slot with no row
    for today is simply "Pending"/"Upcoming" by default (computed at
    request time in dashboard_routes.py from the medication's
    morning/afternoon/night flags), so this table only ever grows when a
    patient actually confirms something, not on a fixed daily schedule
    job. Keeps this table small and avoids needing a scheduler (that's
    still Phase 30's job, for reminder nudges, not this).

    One row per (medication, date, slot) — enforced at the query/insert
    level in medication_routes.py rather than a DB constraint, since
    SQLite's partial-unique-index syntax adds complexity this table's
    scale doesn't need yet.
    """

    __tablename__ = "medication_dose_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    medication_id: Mapped[int] = mapped_column(ForeignKey("medications.id"), nullable=False)
    # ISO date string (YYYY-MM-DD), not a datetime — a dose is "for" a
    # calendar day, not a specific instant, and comparing plain date
    # strings for "is this today" is simpler than timezone-aware datetime
    # arithmetic for a feature this size.
    dose_date: Mapped[str] = mapped_column(String, nullable=False)
    slot: Mapped[str] = mapped_column(String, nullable=False)  # "morning" | "afternoon" | "night"
    taken_at: Mapped[datetime] = mapped_column(default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="dose_logs")
    medication: Mapped["Medication"] = relationship(back_populates="dose_logs")

    def __repr__(self) -> str:
        return f"MedicationDoseLog(medication_id={self.medication_id!r}, dose_date={self.dose_date!r}, slot={self.slot!r})"