"""
backend/schemas.py — single-workflow rebuild
(Register -> Login -> Home -> Patient History / Chatbot).

Pydantic models for every request/response body the API accepts or
returns. Kept separate from routes/ so the request/response "shape" of
the API is readable in one place, and separate from db/models.py because
these are deliberately NOT the same as the ORM models -- e.g.
RegisterRequest never has an id or password_hash field, and no schema
here ever exposes password_hash to a client, by construction (it's simply
not a field on any response schema).

Only the schemas the single workflow actually needs are defined here.
Everything from the abandoned wizard/dashboard/medication-tracker/
visit-summary redesign has been removed.
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Patient History (Patient Profile)
# ---------------------------------------------------------------------------

class ProfileFields(BaseModel):
    """Shared field set for editing the Patient History record via
    PUT /profile. Every field is optional, matching the nullable columns
    on PatientProfile -- a patient can send only the fields they actually
    filled in.
    """
    age: int | None = Field(default=None, ge=0, le=120)
    gender: str | None = None
    blood_group: str | None = None
    height_cm: float | None = Field(default=None, ge=0)
    weight_kg: float | None = Field(default=None, ge=0)
    pregnancy_status: str | None = None
    smoking_status: str | None = None
    alcohol_status: str | None = None
    allergies: str | None = None
    medications: str | None = None
    surgeries: str | None = None
    family_history: str | None = None
    medical_history: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None


class ProfileUpdateRequest(ProfileFields):
    # The Patient History page edits the patient's name alongside the
    # rest of the record in one save -- sent here (and written to
    # User.name, not PatientProfile) only when the caller actually
    # included it.
    full_name: str | None = None


class ProfileResponse(ProfileFields):
    full_name: str | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Auth -- registration collects name + email + password in one step, no
# separate wizard.
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)
    confirm_password: str = Field(min_length=8)

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, confirm_password: str, info) -> str:
        password = info.data.get("password")
        if password is not None and confirm_password != password:
            raise ValueError("Passwords do not match")
        return confirm_password


class RegisterResponse(BaseModel):
    id: int
    name: str
    email: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------

class ConditionCreateRequest(BaseModel):
    condition_name: str = Field(min_length=1)


class ConditionResponse(BaseModel):
    id: int
    condition_name: str
    added_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatSource(BaseModel):
    """One retrieved knowledge-base topic behind a RAG-backed reply --
    powers the chat page's collapsible "Sources" row. Distance is passed
    through as-is (lower = closer match); the frontend renders it as a
    qualitative confidence label rather than a raw number, since a bare
    float means nothing to a patient."""
    topic: str
    distance: float


class ChatResponse(BaseModel):
    reply: str
    # True only when src/emergency_detector.py's fixed, templated
    # response was returned -- lets the frontend render the full-width
    # emergency banner instead of a normal bubble, without the frontend
    # having to pattern-match the reply text itself to guess.
    is_emergency: bool = False
    sources: list[ChatSource] = Field(default_factory=list)


class ChatHistoryEntry(BaseModel):
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}