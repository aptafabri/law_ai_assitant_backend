from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from database.session import Base
import datetime


class LegalSessionSummary(Base):
    __tablename__ = "legal_session_summary"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    session_id = Column(String(100), nullable=False)
    summary = Column(String, nullable=False)
    created_date = Column(DateTime, default=datetime.datetime.now)
    is_favourite = Column(Boolean, default=False)
    favourite_date = Column(DateTime, default=datetime.datetime.now)
