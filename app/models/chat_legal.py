from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from database.session import Base
import datetime


class LegalChatHistory(Base):
    __tablename__='legal_chat_history' 
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    session_id = Column(String(100), nullable=False)
    content = Column(String, nullable=False)
    role = Column(String(100), nullable= False)
    legal_attached = Column( Boolean, default= False)
    legal_file_name = Column(String, nullable= True)
    legal_s3_key = Column(String, nullable=True)
    created_date = Column(DateTime, default=datetime.datetime.now)