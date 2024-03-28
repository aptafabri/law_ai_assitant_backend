from sqlalchemy import Column, Integer, String, Float, DateTime
from database.session import Base
import datetime



class User(Base):
    __tablename__='users' 
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(100), nullable= False)