from pydantic import BaseModel, EmailStr
import datetime
from typing import Optional


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class ChangePassword(BaseModel):
    email: EmailStr
    old_pasword: str
    new_password: str


class ResetPasswordRequest(BaseModel):
    new_password: str


class UserInfo(BaseModel):
    email: EmailStr
    user_name: str


class ForgotPasswordRequest(BaseModel):
    email: str


class VerificationCodeRequest(BaseModel):
    verify_code: str


class ResendVerificationRequest(BaseModel):
    token: str


class SubscriptionInfo(BaseModel):
    subscription_plan: Optional[str] = None
    subscription_expiry: Optional[datetime.datetime] = None
    is_active: bool = False
    message: str
