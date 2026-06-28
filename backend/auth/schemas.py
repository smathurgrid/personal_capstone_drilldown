"""Pydantic schemas for auth endpoints."""

from pydantic import BaseModel, EmailStr, Field


class UserRead(BaseModel):
    id: str
    email: EmailStr
    name: str
    avatar_url: str | None = None


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ProfileUpdateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AuthResponse(BaseModel):
    user: UserRead


class SessionResponse(BaseModel):
    user: UserRead | None
