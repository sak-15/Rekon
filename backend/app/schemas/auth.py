from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.models.organisation import UserRole


class RegisterRequest(BaseModel):
    """
    Payload required to register a new tenant Organisation and its initial Admin user.
    """
    org_name: str = Field(..., min_length=2, max_length=255, description="Legal or display name of SaaS business")
    org_slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$", description="Unique tenant slug (lowercase letters, numbers, hyphens)")
    email: EmailStr = Field(..., description="Admin email address for login")
    password: str = Field(..., min_length=8, max_length=72, description="Password (at least 8 characters, max 72 bytes for bcrypt)")
    full_name: Optional[str] = Field(None, max_length=255, description="Full name of the user")
    currency: Optional[str] = Field("INR", min_length=3, max_length=3, description="Default base operating currency")


class LoginRequest(BaseModel):
    """
    Payload for user authentication.
    """
    email: EmailStr = Field(..., description="Registered user email")
    password: str = Field(..., description="User password")


class OrganisationResponse(BaseModel):
    """
    Public representation of an Organisation tenant.
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    currency: str
    created_at: datetime


class UserResponse(BaseModel):
    """
    Public representation of a User profile.
    """
    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    email: str
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    """
    JWT Access Token response on successful login or registration.
    """
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserResponse
    organisation: OrganisationResponse


class AuthMeResponse(BaseModel):
    """
    Response returned by GET /api/auth/me for checking session context.
    """
    user: UserResponse
    organisation: OrganisationResponse
