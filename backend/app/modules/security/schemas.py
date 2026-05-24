from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class Token(BaseModel):
    access: str
    refresh: str


class TokenRefresh(BaseModel):
    refresh: str
