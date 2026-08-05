"""
backend/auth/security.py — Phase 15: Authentication

Everything password- and session-related lives here:
  - hash_password / verify_password — bcrypt via passlib. Raw passwords
    are NEVER written to the database; only the hash is stored, in
    User.password_hash (see backend/db/models.py).
  - create_access_token / decode_access_token — JWT session tokens (via
    python-jose), signed with SECRET_KEY. This is deliberately simple:
    a signed token carrying the user's id and an expiry, no separate
    session table, no external identity provider — appropriate for a
    single-server student/demo project (see the pivot plan's Section 7
    tradeoffs table).
  - register_user / authenticate_user — the actual register/login logic,
    talking to the users table via a SQLAlchemy Session. Kept here rather
    than split into a separate service file since, at this size, it's
    still fundamentally "the security-sensitive path" — anyone touching
    passwords or tokens only has one file to read.

This file does NOT define any HTTP routes. Wiring these functions up to
POST /register and POST /login is Phase 16 (FastAPI). Everything here is
plain Python + SQLAlchemy so it can be exercised directly — see
test_auth.py — with no web server involved at all, same approach used for
the DB layer in Phase 14.
"""

import os
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.db.models import User

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

# bcrypt via passlib — see requirements.txt for why bcrypt is pinned to
# 4.0.1 (passlib 1.7.4's bcrypt backend is broken on bcrypt>=4.1).
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password for storage. Never store the return value
    of anything OTHER than this function in User.password_hash."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored hash. Returns False
    (never raises) for a malformed/corrupt hash, so a bad row in the DB
    can't turn into an unhandled exception on a login attempt."""
    try:
        return pwd_context.verify(plain_password, password_hash)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT session tokens
# ---------------------------------------------------------------------------

# SECRET_KEY should come from an environment variable in any real
# deployment — the hardcoded fallback below exists purely so this runs
# out of the box for local dev/testing (test_auth.py, curl/Postman
# testing in Phase 16) without requiring extra setup first. Before this
# app is ever exposed beyond localhost, set SEHATAI_SECRET_KEY in the
# environment to a long random value and do NOT commit that value
# anywhere.
SECRET_KEY = os.environ.get(
    "SEHATAI_SECRET_KEY",
    "dev-only-insecure-secret-change-before-deploying-sehatai",
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours — revisit in Phase 20 (hardening)


def create_access_token(user: User, expires_delta: timedelta | None = None) -> str:
    """Build a signed JWT for a logged-in user.

    "sub" (subject) holds the user's id as a string — JWT's "sub" claim
    is conventionally a string, and str(user.id) is all a request handler
    later needs to look the user back up.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": str(user.id), "email": user.email, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Verify and decode a JWT. Returns the payload dict if the token is
    valid and unexpired, or None if it's malformed, expired, or signed
    with a different key — callers should treat None as "not logged in",
    not raise on it."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Register / login
# ---------------------------------------------------------------------------

class EmailAlreadyRegisteredError(Exception):
    """Raised by register_user() when the email is already taken."""
    pass


def register_user(session: Session, email: str, password: str) -> User:
    """Create a new User row with a hashed password.

    UI redesign: no longer takes `name` -- registration is credentials-only
    now (see schemas.RegisterRequest's docstring). The new user's `name`
    starts as None and `profile_completed` starts False (both column
    defaults on the User model); `name` gets filled in, and
    profile_completed flips to True, only once the patient finishes the
    post-login Patient Profile Wizard (see profile_routes.py's POST
    /profile/wizard).

    Raises EmailAlreadyRegisteredError instead of letting the database's
    UNIQUE constraint surface as a raw IntegrityError, so callers (Phase
    16's /register route, or test_auth.py) get a clear, specific error to
    handle rather than a generic SQLAlchemy exception.
    """
    existing = session.query(User).filter(User.email == email).first()
    if existing is not None:
        raise EmailAlreadyRegisteredError(f"Email already registered: {email}")

    user = User(email=email, password_hash=hash_password(password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    """Look up a user by email and verify their password.

    Returns the User on success, or None on ANY failure (no such email,
    or wrong password) — deliberately not distinguishing between the two
    in the return value, so a caller can't accidentally build a "this
    email exists" oracle for attackers out of the error path.
    """
    user = session.query(User).filter(User.email == email).first()
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user