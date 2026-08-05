"""
backend/routes/medication_routes.py -- UI/UX redesign: the Medicines page
and the Dashboard's Medicine Timeline widget both read/write through
here. Brings forward (in reduced form) what the original roadmap called
out as Phase 24's medication tracker table.

Routes:
  GET    /medications             -- full list (active + past)
  POST   /medications              -- add a medicine
  PUT    /medications/{id}         -- edit a medicine
  DELETE /medications/{id}         -- remove a medicine
  POST   /medications/{id}/taken   -- mark today's dose (a slot) as taken

user_id always comes from the authenticated token; every route below
also re-checks medication.user_id == current_user.id before touching a
row, so there is no way to read or modify a different patient's
medicine by guessing an id.
"""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.db.models import Medication, MedicationDoseLog, User
from backend.deps import get_current_user, get_db
from backend.schemas import (
    DoseLogRequest,
    MedicationCreateRequest,
    MedicationResponse,
    MedicationUpdateRequest,
)

router = APIRouter(prefix="/medications", tags=["medications"])


def _get_owned_medication(db: Session, medication_id: int, user_id: int) -> Medication:
    medication = db.query(Medication).filter(Medication.id == medication_id).first()
    if medication is None or medication.user_id != user_id:
        # 404, not 403 -- doesn't reveal whether a medicine with that id
        # exists at all for someone else's account, same reasoning as
        # get_current_user's single generic 401 message in deps.py.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine not found")
    return medication


@router.get("", response_model=list[MedicationResponse])
def list_medications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Medication)
        .filter(Medication.user_id == current_user.id)
        .order_by(Medication.active.desc(), Medication.created_at.desc())
        .all()
    )


@router.post("", response_model=MedicationResponse, status_code=201)
def add_medication(
    request: MedicationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    medication = Medication(user_id=current_user.id, **request.model_dump())
    db.add(medication)
    db.commit()
    db.refresh(medication)
    return medication


@router.put("/{medication_id}", response_model=MedicationResponse)
def update_medication(
    medication_id: int,
    request: MedicationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    medication = _get_owned_medication(db, medication_id, current_user.id)
    for field_name, value in request.model_dump(exclude_unset=True).items():
        setattr(medication, field_name, value)
    db.commit()
    db.refresh(medication)
    return medication


@router.delete("/{medication_id}", status_code=204)
def delete_medication(
    medication_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    medication = _get_owned_medication(db, medication_id, current_user.id)
    db.delete(medication)
    db.commit()
    return None


@router.post("/{medication_id}/taken", status_code=201)
def mark_dose_taken(
    medication_id: int,
    request: DoseLogRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Marks one slot (morning/afternoon/night) of one medicine as taken
    for today. Idempotent: re-marking an already-taken slot the same day
    is a harmless no-op rather than a duplicate row, so a double-tap on
    the dashboard can't corrupt the day's record."""
    medication = _get_owned_medication(db, medication_id, current_user.id)
    today = date.today().isoformat()

    existing = (
        db.query(MedicationDoseLog)
        .filter(
            MedicationDoseLog.medication_id == medication.id,
            MedicationDoseLog.dose_date == today,
            MedicationDoseLog.slot == request.slot,
        )
        .first()
    )
    if existing is not None:
        return {"status": "already_taken", "taken_at": existing.taken_at}

    log_entry = MedicationDoseLog(
        user_id=current_user.id,
        medication_id=medication.id,
        dose_date=today,
        slot=request.slot,
    )
    db.add(log_entry)
    db.commit()
    return {"status": "taken", "taken_at": datetime.now(timezone.utc)}