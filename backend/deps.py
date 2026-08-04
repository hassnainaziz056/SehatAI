"""
backend/deps.py — Phase 16: FastAPI Wiring

Two dependencies every protected route uses:
  get_db()           — hands a route a SQLAlchemy Session, closes it after.
  get_current_user()  — the auth gate: reads the bearer token, decodes it,
                         loads the matching User. Any failure -> 401.

Written as plain generator functions (not the @contextmanager-wrapped
get_session() in backend/db/session.py) because that's the exact shape
FastAPI's Depends() expects for a "yield" dependency — FastAPI calls the
generator, runs the route with whatever it yields, then resumes the
generator (running the code after yield) once the route finishes. Wrapping
get_session() with @contextmanager makes it awkward to use directly as a
FastAPI dependency, so this is a thin, FastAPI-native version instead.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.auth.security import decode_access_token
from backend.db.models import User
from backend.db.session import SessionLocal

# tokenUrl points FastAPI's auto-generated /docs page at /login so the
# "Authorize" button there knows where a token comes from. It does NOT
# mean /login has to accept OAuth2's form-encoded body — our /login route
# takes a plain JSON LoginRequest instead; this is purely for /docs.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def get_db():
    """Yield a Session for the lifetime of one request, close it after —
    including when the route raises, since `finally` always runs."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    The auth gate. Every route that depends on this only runs if a valid,
    unexpired token for a real user was supplied — otherwise FastAPI never
    reaches the route body at all, it short-circuits straight to the 401
    raised here.

    A single generic "Could not validate credentials" message is used for
    every failure case (missing token, malformed token, expired token,
    token for a user id that no longer exists) rather than distinguishing
    between them in the response, for the same reason authenticate_user()
    in security.py doesn't distinguish "wrong password" from "no such
    user" — a more specific error message here would let an attacker
    learn things (e.g. "that user id doesn't exist") from a failed auth
    attempt that a generic message doesn't leak.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_error

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        raise credentials_error

    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        raise credentials_error

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_error

    return user