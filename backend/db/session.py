"""
backend/db/session.py — Phase 14: Database Layer

Sets up the actual database connection: the SQLite engine, a session
factory, and a get_session() helper for handing out short-lived sessions.

Same path-resolution pattern as knowledge_base/retriever.py's
VECTOR_STORE_DIR — resolved relative to this file (not the current working
directory), so it works the same way no matter where a script that
imports it happens to be run from.
"""

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "sehatai.db")

# check_same_thread=False is the standard SQLite + SQLAlchemy setting for
# anything other than a single-threaded script — FastAPI (Phase 16) will
# hand requests to worker threads, and without this flag SQLite refuses to
# let a session be used from a thread other than the one that created it.
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

# One SessionLocal() call = one new session. autoflush/autocommit are left
# at SQLAlchemy 2.0's defaults (autoflush on, no implicit autocommit) —
# callers are expected to call session.commit() themselves, same as
# test_db.py does below.
SessionLocal = sessionmaker(bind=engine, autoflush=True, expire_on_commit=False)


@contextmanager
def get_session():
    """
    Yield a Session and guarantee it's closed afterward, regardless of
    whether the caller's code raises.

    Usage:
        with get_session() as session:
            session.add(some_row)
            session.commit()

    This is written as a plain context manager for now so it works
    standalone (as used by test_db.py) with no web framework involved.
    In Phase 16, FastAPI route handlers will get a session the same
    yield-then-close way via `Depends(...)` — either by depending on a
    thin wrapper around this function, or a near-identical plain generator
    version, depending on what FastAPI's version in use expects at the
    time.
    """
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()