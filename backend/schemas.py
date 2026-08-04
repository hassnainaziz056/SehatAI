"""
backend/schemas.py — Phase 16: FastAPI Wiring

Pydantic models for every request/response body the API accepts or
returns. Kept separate from routes/ so the request/response "shape" of
the API is readable in one place, and separate from db/models.py because
these are deliberately NOT the same as the ORM models — e.g.
RegisterRequest never has an id or password_hash field, and no schema
here ever exposes password_hash to a client, by construction (it's simply
not a field on any response schema).
"""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)


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

    # Lets these be built straight from a UserCondition ORM object
    # (response_model=ConditionResponse) instead of hand-converting every
    # field to a dict first.
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str


class ChatHistoryEntry(BaseModel):
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}