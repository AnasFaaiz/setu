import uuid 
from sqlalchemy import Column, String, Text, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID 
from datetime import datetime 
from tasks.db import Base 

class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_reference_id = Column(String, nullable=True)
    raw_input = Column(Text, nullable=False)
    language = Column(String)
    district = Column(String)
    topic = Column(String)
    urgency = Column(String)
    source_channel = Column(String)
    status = Column(String, default="received")
    created_at = Column(DateTime, default=datetime.utcnow)
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    error_reason = Column(Text, nullable=True)


class DistrictIndicator(Base):
    __tablename__ = "district_indicators"

    district = Column(String, primary_key=True)
    state = Column(String)
    population = Column(Integer)
    infra_index = Column(Numeric)
    literacy_rate = Column(Numeric)
    last_updated = Column(DateTime, default=datetime.utcnow)


class HotspotScore(Base):
    __tablename__ = "hotspot_scores"

    district = Column(String, ForeignKey("district_indicators.district"), primary_key=True)
    feedback_count = Column(Integer)
    dominant_topic = Column(String)
    priority_score = Column(Numeric)
    computed_at = Column(DateTime, default=datetime.utcnow)
    complaint_rate_per_100k = Column(Numeric)
    infra_gap = Column(Numeric)
    current_population_estimate = Column(Integer)
