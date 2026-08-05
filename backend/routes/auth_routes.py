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
from backend.db.models import PatientProfile, UserCondition
from backend.deps import get_db
from backend.schemas import LoginRequest, LoginResponse, RegisterRequest, RegisterResponse

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = register_user(db, name=request.name, email=request.email, password=request.password)
    except EmailAlreadyRegisteredError:
        # 409 Conflict — the request is well-formed, but the resource
        # (this email) already exists, which is exactly what 409 means.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    # Phase 17: save whatever conditions the patient selected on the
    # registration checklist (plus any free-text "Other" value, already
    # folded into this same list by the frontend). Blank/whitespace-only
    # entries are skipped so an empty "Other" text box that got submitted
    # anyway doesn't create a junk UserCondition row.
    for condition_name in request.conditions:
        cleaned_name = condition_name.strip()
        if cleaned_name:
            db.add(UserCondition(user_id=user.id, condition_name=cleaned_name))
    if request.conditions:
        db.commit()

    # Phase 20: only create a PatientProfile row if the patient actually
    # filled in the (optional) profile section on the registration form.
    # Skipping it entirely is valid — GET/PUT /profile creates the row
    # lazily later, same as for pre-Phase-20 accounts. model_dump() here
    # rather than exclude_unset, since at registration every field the
    # form didn't collect is genuinely None, not "not yet decided".
    if request.profile is not None:
        db.add(PatientProfile(user_id=user.id, **request.profile.model_dump()))
        db.commit()

    return user


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, email=request.email, password=request.password)
    if user is None:
        # Same generic message regardless of whether the email doesn't
        # exist or the password was wrong — see authenticate_user()'s
        # docstring in security.py for why that's deliberate.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    token = create_access_token(user)
    return LoginResponse(access_token=token)