from pydantic import BaseModel


class LoginRequest(BaseModel):
    identifier: str  # accepts email address or institutional_id
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterResponse(BaseModel):
    message: str


class ResendVerificationRequest(BaseModel):
    email: str
