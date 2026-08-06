"""
backend/routes/auth_routes.py — Phase 16: FastAPI Wiring

POST /register and POST /login. Neither depends on get_current_user — you
can't be logged in yet when you're hitting either of these, that's the
whole point of them.

These routes are thin on purpose: all the actual logic (hashing,
uniqueness checks, password verification, token creation) already lives
in backend/auth/security.py from Phase 15. This file's job is only to
translate between HTTP (request bodies, status codes) and those plain
Python functions.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.security import (
    EmailAlreadyRegisteredError,
    authenticate_user,
    create_access_token,
    register_user,
)
from backend.deps import get_db
from backend.schemas import LoginRequest, LoginResponse, RegisterRequest, RegisterResponse

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = register_user(db, name=request.name, email=request.email, password=request.password)
    except EmailAlreadyRegisteredError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    return user


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Single-workflow rebuild: login always goes straight to Home on
    success -- there is no wizard/profile-completed branching for the
    frontend to make, so the response is just a plain access token."""
    user = authenticate_user(db, email=request.email, password=request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    token = create_access_token(user)
    return LoginResponse(access_token=token)