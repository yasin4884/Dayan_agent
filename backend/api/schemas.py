from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.text_utils import normalize_digits, normalize_identifier, normalize_text

# نام: حروف فارسی/لاتین + فاصله
NameStr = Annotated[str, Field(min_length=2, max_length=80, pattern=r"^[\u0600-\u06FFa-zA-Z\s'\-]+$")]
UsernameStr = Annotated[str, Field(min_length=3, max_length=30, pattern=r"^[a-z0-9._]+$")]
CodeStr = Annotated[str, Field(min_length=3, max_length=20, pattern=r"^\d+$")]
PasswordStr = Annotated[str, Field(min_length=8, max_length=128)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RegisterUserRequest(StrictModel):
    first_name: NameStr
    last_name: NameStr
    username: UsernameStr
    student_code: CodeStr
    password: PasswordStr
    password_confirm: PasswordStr
    group_id: str = Field(min_length=1, max_length=32)

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def _clean_name(cls, v: Any) -> Any:
        return normalize_text(v) if isinstance(v, str) else v

    @field_validator("username", mode="before")
    @classmethod
    def _clean_username(cls, v: Any) -> Any:
        return normalize_identifier(v) if isinstance(v, str) else v

    @field_validator("student_code", mode="before")
    @classmethod
    def _clean_code(cls, v: Any) -> Any:
        if not isinstance(v, str):
            return v
        return normalize_identifier(normalize_digits(v))


class LoginRequest(StrictModel):
    """ورود با نام کاربری یا کد دانشجویی."""

    identifier: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("identifier", mode="before")
    @classmethod
    def _clean(cls, v: Any) -> Any:
        return normalize_identifier(v) if isinstance(v, str) else v


class AdminRegisterRequest(StrictModel):
    full_name: Annotated[
        str, Field(min_length=3, max_length=160, pattern=r"^[\u0600-\u06FFa-zA-Z\s'\-]+$")
    ]
    personnel_code: CodeStr
    password: PasswordStr
    password_confirm: PasswordStr

    @field_validator("full_name", mode="before")
    @classmethod
    def _clean_name(cls, v: Any) -> Any:
        return normalize_text(v) if isinstance(v, str) else v

    @field_validator("personnel_code", mode="before")
    @classmethod
    def _clean_code(cls, v: Any) -> Any:
        return normalize_identifier(v) if isinstance(v, str) else v


class AdminLoginRequest(StrictModel):
    personnel_code: CodeStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("personnel_code", mode="before")
    @classmethod
    def _clean_code(cls, v: Any) -> Any:
        return normalize_identifier(v) if isinstance(v, str) else v


class RefreshRequest(StrictModel):
    refresh_token: str = Field(min_length=10, max_length=400)


class ChangePasswordRequest(StrictModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: PasswordStr
    new_password_confirm: PasswordStr


class GroupCreateRequest(StrictModel):
    name: Annotated[str, Field(min_length=2, max_length=120)]
    description: str = Field(default="", max_length=400)
    sort_order: int = Field(default=0, ge=0, le=9999)
    is_active: bool = True

    @field_validator("name", "description", mode="before")
    @classmethod
    def _clean(cls, v: Any) -> Any:
        return normalize_text(v) if isinstance(v, str) else v


class GroupUpdateRequest(StrictModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=400)
    sort_order: int | None = Field(default=None, ge=0, le=9999)
    is_active: bool | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict[str, Any] | None = None


__all__ = [
    "AdminLoginRequest",
    "AdminRegisterRequest",
    "ChangePasswordRequest",
    "GroupCreateRequest",
    "GroupUpdateRequest",
    "LoginRequest",
    "RefreshRequest",
    "RegisterUserRequest",
    "StrictModel",
    "TokenResponse",
    "normalize_digits",
]
