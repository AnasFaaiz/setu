import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime 
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime 

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True)
    raw_input = Column(Text, nullable=False)
    language = Column(String)
    district = Column(String)
    topic = Column(String)
    urgency = Column(String)
    source_channel = Column(String)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

# Create the table if doesn't exist
Base.metadata.create_all(engine)
