"""
backend/routes/profile_routes.py — Phase 20: Expanded Patient Health Profile

GET /profile and PUT /profile — both require a valid logged-in user, same
pattern as conditions_routes.py: user_id always comes from the
authenticated token, never from the request body, so there's no way to
read or edit a different account's profile by editing a request.

Unlike conditions (Phase 17), a PatientProfile row isn't guaranteed to
exist for every user — accounts registered before this phase shipped
have none, and even after Phase 20, a patient who skipped the profile
section at registration has none either. _get_or_create_profile() below
handles that uniformly: both routes always end up with a real row to
read or write, created empty on first touch rather than requiring a
migration script for existing accounts.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.db.models import PatientProfile, User
from backend.deps import get_current_user, get_db
from backend.schemas import ProfileResponse, ProfileUpdateRequest

router = APIRouter(prefix="/profile", tags=["profile"])


def _get_or_create_profile(db: Session, user_id: int) -> PatientProfile:
    profile = db.query(PatientProfile).filter(PatientProfile.user_id == user_id).first()
    if profile is None:
        profile = PatientProfile(user_id=user_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.get("", response_model=ProfileResponse)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_or_create_profile(db, current_user.id)


@router.put("", response_model=ProfileResponse)
def update_profile(
    request: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_or_create_profile(db, current_user.id)

    # exclude_unset means a field the client never sent is left alone —
    # important for a future partial-update client, and harmless for the
    # current profile.html, which always sends every field (a blank
    # field is sent as None/"" explicitly, which IS "set", so it still
    # clears that field correctly).
    for field_name, value in request.model_dump(exclude_unset=True).items():
        setattr(profile, field_name, value)

    db.commit()
    db.refresh(profile)
    return profile