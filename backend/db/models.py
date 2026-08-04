"""
backend/db/models.py — Phase 14: Database Layer

Defines the three tables the future multi-user web platform is built on:
  User            — one row per registered patient.
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

from sqlalchemy import ForeignKey, String, Text
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

    Deliberately minimal for Phase 14 — no password_hash yet, since
    authentication (Phase 15) isn't built yet. name/email are enough to
    prove the storage layer itself works end-to-end.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
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