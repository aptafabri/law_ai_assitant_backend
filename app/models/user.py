from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum
from database.session import Base
import datetime
from schemas.payment import SubscriptionPlan

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(100), nullable=False)
    llm_token = Column(Float, default=100)
    reset_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=False)
    verify_code = Column(String(50), nullable=True)
    verify_code_expiry = Column(DateTime, default=datetime.datetime.now)
    created_date = Column(DateTime, default=datetime.datetime.now)
    activated_by_admin = Column(Boolean, default=False)
    subscription_plan =  Column(Enum(SubscriptionPlan), nullable=True)
    subscription_expiry = Column(DateTime, nullable=True)  # Subscription expiry
    paid_price = Column(Float, nullable=True)  # Store payment amount
