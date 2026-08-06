"""
backend/routes/profile_routes.py — Patient History (single-workflow rebuild)

GET /profile and PUT /profile — both require a valid logged-in user, same
pattern as conditions_routes.py: user_id always comes from the
authenticated token, never from the request body, so there's no way to
read or edit a different account's profile by editing a request.

There is no wizard and no profile-completed gate. A PatientProfile row
isn't guaranteed to exist for every user (it's created lazily on first
read/write), so _get_or_create_profile() below handles that uniformly:
both routes always end up with a real row to read or write.
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


def _to_response(profile: PatientProfile, user: User) -> ProfileResponse:
    response = ProfileResponse.model_validate(profile)
    response.full_name = user.name
    return response


@router.get("", response_model=ProfileResponse)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_or_create_profile(db, current_user.id)
    return _to_response(profile, current_user)


@router.put("", response_model=ProfileResponse)
def update_profile(
    request: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = _get_or_create_profile(db, current_user.id)

    data = request.model_dump(exclude_unset=True)
    full_name = data.pop("full_name", None)
    if full_name:
        current_user.name = full_name

    for field_name, value in data.items():
        setattr(profile, field_name, value)

    db.commit()
    db.refresh(profile)
    return _to_response(profile, current_user)