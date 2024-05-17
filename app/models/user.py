from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from database.session import Base
import datetime


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(100), nullable=False)
    reset_verified = Column(Boolean, default=False)
    verify_code = Column(String(50), nullable=True)
    verify_code_expiry = Column(DateTime, default=datetime.datetime.now)
