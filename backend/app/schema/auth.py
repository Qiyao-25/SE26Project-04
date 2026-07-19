from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(RegisterRequest):
    pass


class AuthUser(BaseModel):
    user_id: str
    email: str
    role: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser


class AccountUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=255)
    current_password: str | None = Field(default=None, min_length=1, max_length=128)
    password: str | None = Field(default=None, min_length=6, max_length=128)
