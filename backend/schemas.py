"""
backend/schemas.py — Phase 16 (FastAPI Wiring), extended by the UI/UX
redesign for the new registration -> wizard -> dashboard flow.

Pydantic models for every request/response body the API accepts or
returns. Kept separate from routes/ so the request/response "shape" of
the API is readable in one place, and separate from db/models.py because
these are deliberately NOT the same as the ORM models -- e.g.
RegisterRequest never has an id or password_hash field, and no schema
here ever exposes password_hash to a client, by construction (it's simply
not a field on any response schema).
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Profile (Phase 20, fields extended by the wizard redesign)
# ---------------------------------------------------------------------------

class ProfileFields(BaseModel):
    """Shared field set for editing the health profile via PUT /profile.
    Every field is optional, matching the nullable columns on
    PatientProfile -- a patient can send only the fields they actually
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
    pass


class ProfileResponse(ProfileFields):
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Auth -- registration is now credentials-only (UI redesign)
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    """UI redesign: registration collects ONLY authentication information.
    No name, no conditions, no medical fields -- those all moved to the
    mandatory post-login Patient Profile Wizard (see WizardCompleteRequest
    below and profile_routes.py's POST /profile/wizard).
    """
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
    email: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # UI redesign: returned inline with the token so login.js can decide
    # where to redirect (wizard vs. dashboard) without a second round
    # trip to GET /profile/status before the first page paints.
    profile_completed: bool


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
# Patient Profile Wizard (UI redesign)
# ---------------------------------------------------------------------------

class WizardMedicineInput(BaseModel):
    """One medicine entry from Wizard Step 3. Mirrors Medication's
    columns directly -- see backend/db/models.py's Medication docstring
    for why morning/afternoon/night are three independent booleans."""
    name: str = Field(min_length=1)
    dosage: str | None = None
    frequency: str | None = None
    morning: bool = False
    afternoon: bool = False
    night: bool = False
    start_date: str | None = None


class WizardCompleteRequest(BaseModel):
    """The full payload submitted once, from the wizard's Step 5 (Review)
    "Complete Profile" button. Deliberately one request for the whole
    wizard rather than one request per step -- the wizard is a single
    logical unit of work (a patient record isn't "half-created"), and a
    patient can freely go Back and forth between steps client-side
    without any partial server state to reconcile.

    conditions/medicines default to empty lists (a patient may have
    neither), every profile field is optional (Step 2's fields, same
    nullable pattern as ProfileFields), full_name is the only field the
    wizard actually requires, since it's the one piece of information
    every other part of the product (emergency responses, dashboard
    header, chat context) depends on having.
    """
    full_name: str = Field(min_length=1)

    # Step 1 -- Personal Information
    age: int | None = Field(default=None, ge=0, le=120)
    gender: str | None = None
    height_cm: float | None = Field(default=None, ge=0)
    weight_kg: float | None = Field(default=None, ge=0)
    blood_group: str | None = None

    # Step 2 -- Medical History
    conditions: list[str] = Field(default_factory=list)
    allergies: str | None = None
    surgeries: str | None = None
    family_history: str | None = None
    smoking_status: str | None = None
    alcohol_status: str | None = None
    pregnancy_status: str | None = None

    # Step 3 -- Current Medicines
    medicines: list[WizardMedicineInput] = Field(default_factory=list)

    # Step 4 -- Emergency Contact
    emergency_contact_name: str | None = None
    emergency_contact_relationship: str | None = None
    emergency_contact_phone: str | None = None


class WizardStatusResponse(BaseModel):
    profile_completed: bool


# ---------------------------------------------------------------------------
# Medications (Phase 24-style tracker, brought forward by the redesign)
# ---------------------------------------------------------------------------

class MedicationCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    dosage: str | None = None
    frequency: str | None = None
    morning: bool = False
    afternoon: bool = False
    night: bool = False
    start_date: str | None = None


class MedicationUpdateRequest(BaseModel):
    """All fields optional -- PUT /medications/{id} only changes what's
    sent, same exclude_unset pattern as ProfileUpdateRequest's PUT
    /profile handling."""
    name: str | None = None
    dosage: str | None = None
    frequency: str | None = None
    morning: bool | None = None
    afternoon: bool | None = None
    night: bool | None = None
    start_date: str | None = None
    active: bool | None = None


class MedicationResponse(BaseModel):
    id: int
    name: str
    dosage: str | None
    frequency: str | None
    morning: bool
    afternoon: bool
    night: bool
    start_date: str | None
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DoseLogRequest(BaseModel):
    slot: str = Field(pattern="^(morning|afternoon|night)$")


class ScheduleSlot(BaseModel):
    """One row on the Dashboard's Medicine Timeline widget: a single
    medicine's single time-of-day slot, plus its status for *today*."""
    medication_id: int
    medication_name: str
    dosage: str | None
    slot: str  # "morning" | "afternoon" | "night"
    slot_time_label: str  # e.g. "8:00 AM" -- display-only, not stored
    status: str  # "taken" | "pending" | "upcoming"


# ---------------------------------------------------------------------------
# Dashboard (UI redesign -- new landing page)
# ---------------------------------------------------------------------------

class HealthSummary(BaseModel):
    name: str | None
    age: int | None
    gender: str | None
    blood_group: str | None
    conditions: list[str]
    allergies: str | None


class TimelineEvent(BaseModel):
    """One row in the Health Timeline widget/page. event_type drives the
    icon on the frontend (condition | medication | chat)."""
    event_type: str
    title: str
    detail: str | None
    occurred_at: datetime


class ConversationSummary(BaseModel):
    """One row in the Dashboard's "Recent Conversations" widget -- the
    first patient message in a rough session grouping, used as a title,
    plus when it last had activity."""
    first_message: str
    last_message_at: datetime
    message_count: int


class DashboardResponse(BaseModel):
    health_summary: HealthSummary
    medicine_schedule_today: list[ScheduleSlot]
    health_timeline: list[TimelineEvent]
    recent_conversations: list[ConversationSummary]
    profile_completed: bool


# ---------------------------------------------------------------------------
# Chat (Phase 16, extended for source references / emergency banner)
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
    # emergency banner (see frontend/js/chat.js) instead of a normal
    # bubble, without the frontend having to pattern-match the reply
    # text itself to guess.
    is_emergency: bool = False
    sources: list[ChatSource] = Field(default_factory=list)


class ChatHistoryEntry(BaseModel):
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}