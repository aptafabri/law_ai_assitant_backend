from sqlalchemy import Column, Integer, String, Float, DateTime
from database.session import Base
import datetime


class ChatHistory(Base):
    __tablename__='chat_history' 
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    session_id = Column(String(100), nullable=False)
    content = Column(String, nullable=False)
    role = Column(String(100), nullable= False)
    created_date = Column(DateTime, default=datetime.datetime.now)