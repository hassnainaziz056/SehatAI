"""
backend/routes/conditions_routes.py — Phase 16: FastAPI Wiring

GET /conditions and POST /conditions — both require a valid logged-in
user (get_current_user), since a patient's health conditions are
sensitive and only theirs to read or add to. There is no endpoint here to
list or edit anyone else's conditions, and no user_id is ever taken from
the request body — it always comes from the authenticated token, so
there's no way to add a condition to a different account by editing a
request.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.conditions_catalog import AVAILABLE_CONDITIONS
from backend.db.models import User, UserCondition
from backend.deps import get_current_user, get_db
from backend.schemas import ConditionCreateRequest, ConditionResponse

router = APIRouter(prefix="/conditions", tags=["conditions"])


@router.get("/available", response_model=list[str])
def list_available_conditions():
    """
    Phase 17: the FIXED checklist shown on the registration form —
    deliberately public (no get_current_user dependency), since a patient
    hasn't registered yet when they need this list. Not to be confused
    with GET /conditions below, which returns a specific logged-in
    patient's OWN selected conditions and does require auth. Two
    different things that happen to share a URL prefix; see
    conditions_catalog.py for why this one is a plain constant, not a
    database table.
    """
    return AVAILABLE_CONDITIONS


@router.get("", response_model=list[ConditionResponse])
def list_conditions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # FastAPI caches each dependency's result per request, so this `db`
    # and the one get_current_user used internally are actually the same
    # Session instance here — current_user.conditions would work too, but
    # querying UserCondition directly keeps this route explicit about
    # exactly what it reads, without relying on relationship lazy-loading
    # behavior.
    return (
        db.query(UserCondition)
        .filter(UserCondition.user_id == current_user.id)
        .order_by(UserCondition.added_at)
        .all()
    )


@router.post("", response_model=ConditionResponse, status_code=201)
def add_condition(
    request: ConditionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    condition = UserCondition(user_id=current_user.id, condition_name=request.condition_name)
    db.add(condition)
    db.commit()
    db.refresh(condition)
    return condition