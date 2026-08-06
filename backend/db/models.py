"""
backend/db/models.py — Phase 14: Database Layer (+ Phase 15: password_hash)

Refactored for the single-workflow rebuild (Register -> Login -> Home ->
Patient History / Chatbot). Only the tables that workflow actually needs
are defined here:
  User            — one row per registered patient. password_hash is a
                    bcrypt hash, never a raw password — see
                    backend/auth/security.py. `name` is collected at
                    registration now (no wizard), so it's required, not
                    nullable.
  PatientProfile  — the single Patient History record (age, gender,
                    vitals, allergies, current medicines as free text,
                    smoking/alcohol, family history, emergency contact).
                    One row per user, created lazily on first read/write.
  UserCondition   — one row per disease/condition a patient has on file
                    (the Patient History page's "Diseases" checklist). A
                    separate table rather than a comma-separated column,
                    so it stays queryable.
  ChatMessage     — one row per turn in a patient's conversation history.
                    role/content mirror the shape chatbot.py's
                    conversation_history already uses ({"role": ...,
                    "content": ...}), so reconstructing a
                    conversation_history list from the database is a
                    straight read, no translation.

This file only defines the schema (table shape + relationships). It does
not open a connection or create anything on disk — that's session.py and
init_db.py's job. Nothing in here touches src/chatbot.py, knowledge_base/,
or main.py; this is independent storage machinery sitting next to the
existing chatbot, not a replacement for any of it.

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

    password_hash is a bcrypt hash, never the raw password (see
    backend/auth/security.py for hashing/verification).

    Single-workflow rebuild: registration (POST /register) collects
    name + email + password in one step — there is no separate wizard,
    so `name` is required (not nullable) and set at registration time.
    Login always goes straight to Home; there is no profile-completed
    gate to branch on.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
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
    # has exactly one Patient History record.
    profile: Mapped["PatientProfile | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
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
    """The single Patient History record — one row per user, created
    lazily (see profile_routes.py's _get_or_create_profile) the first time
    a patient's history is read or saved.

    Every field is nullable. A patient filling in "just age and
    allergies" and leaving the rest blank is the normal case, not an
    error — same "skip if none apply" spirit as the conditions checklist,
    just for free-form/numeric fields instead of a fixed list.

    Deliberately one wide table rather than several normalized ones:
    none of these fields are naturally many-per-patient the way
    conditions are. `medications` is intentionally free text ("what a
    patient tells a doctor at intake" — current medicines, as typed),
    not a structured, many-rows-per-patient table — this app has no
    medication tracker/reminder feature.
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
    # Alcohol use alongside smoking status; its own nullable column rather
    # than folded into medical_history free text, so it stays a
    # structured, queryable field the same way smoking_status is.
    alcohol_status: Mapped[str | None] = mapped_column(String, nullable=True)
    family_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Free text, not structured lists — intake-style notes a doctor would
    # read once, not something the app parses.
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