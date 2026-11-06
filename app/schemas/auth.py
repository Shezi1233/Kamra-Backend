from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=190)
    password: str = Field(min_length=1, max_length=200)


class UserOut(ORMModel):
    id: int
    full_name: str
    email: EmailStr
    phone: str | None = None
    is_active: int
    created_at: datetime | None = None


class AdminOut(ORMModel):
    id: int
    full_name: str
    email: str
    is_active: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut | None = None
    admin: AdminOut | None = None


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=40)


class PasswordChange(BaseModel):
    current_password: str
    password: str = Field(min_length=8, max_length=200)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    success: str
    reset_link: str | None = None


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=200)


class AdminProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    password: str | None = Field(default=None, min_length=8, max_length=200)
