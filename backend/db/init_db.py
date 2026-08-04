"""
backend/db/init_db.py — Phase 14: Database Layer

Run once (and safely re-runnable — create_all() skips tables that already
exist) to actually create sehatai.db on disk with the users,
user_conditions, and chat_messages tables from models.py.

Usage:
    python -m backend.db.init_db
"""

from backend.db.models import Base
from backend.db.session import DB_PATH, engine


def main() -> None:
    print("[INFO] Creating tables (users, user_conditions, chat_messages)...")

    # create_all() reads every model registered on Base.metadata — importing
    # models.py above (for Base itself) is what pulls User, UserCondition,
    # and ChatMessage onto that metadata in the first place. Tables that
    # already exist are left alone, so running this twice is harmless.
    Base.metadata.create_all(engine)

    print(f"[DONE] Database ready at: {DB_PATH}")


if __name__ == "__main__":
    main()