import uuid
from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from tasks.db import SessionLocal
from tasks.schema import Feedback, HotspotScore, DistrictIndicator
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

class FeedbackInput(BaseModel):
    raw_input: str
    language: Optional[str] = None
    source_channel: str
    client_reference_id: Optional[str] = None


@app.post("/submit-feedback")
@limiter.limit("20/minute")
def submit_feedback(request: Request, payload: FeedbackInput):
    feedback_id = str(uuid.uuid4())

    session = SessionLocal()
    try:
        entry = Feedback(
            id=feedback_id,
            raw_input=payload.raw_input,
            language=payload.language,
            source_channel=payload.source_channel,
            client_reference_id=payload.client_reference_id,
            status="received",
        )
        session.add(entry)
        session.commit()
    finally:
        session.close()

    return {"id": feedback_id, "status": "received", "message": "Complaint logged. Awaiting AI triage."}


@app.get("/status/{feedback_id}")
def status(feedback_id: str):
    session = SessionLocal()
    try:
        entry = session.get(Feedback, feedback_id)
        if entry is None:
            return {"error": "not found"}
        return {
            "id": str(entry.id),
            "status": entry.status,
            "topic": entry.topic,
            "district": entry.district,
            "urgency": entry.urgency,
        }
    finally:
        session.close()


@app.get("/hotspots")
def list_hotspots(limit: int = 20):
    session = SessionLocal()
    try:
        rows = session.execute(
            select(HotspotScore)
            .order_by(HotspotScore.priority_score.desc())
            .limit(limit)
        ).scalars().all()

        return [
            {
                "district": r.district,
                "priority_score": float(r.priority_score),
                "feedback_count": r.feedback_count,
                "dominant_topic": r.dominant_topic,
                "complaint_rate_per_100k": float(r.complaint_rate_per_100k),
                "infra_gap": float(r.infra_gap),
                "current_population_estimate": r.current_population_estimate,
                "computed_at": r.computed_at.isoformat() if r.computed_at else None,
            }
            for r in rows
        ]
    finally:
        session.close()


@app.get("/hotspots/{district}")
def hotspot_detail(district: str):
    session = SessionLocal()
    try:
        district = district.lower().strip()
        score = session.get(HotspotScore, district)
        if score is None:
            return {"error": "no score found for this district"}

        indicator = session.get(DistrictIndicator, district)

        complaints = session.execute(
            select(Feedback.raw_input, Feedback.topic, Feedback.urgency, Feedback.created_at)
            .where(Feedback.district == district)
            .where(Feedback.status == "processed")
            .order_by(Feedback.created_at.desc())
        ).all()

        return {
            "district": district,
            "priority_score": float(score.priority_score),
            "feedback_count": score.feedback_count,
            "dominant_topic": score.dominant_topic,
            "complaint_rate_per_100k": float(score.complaint_rate_per_100k),
            "infra_gap": float(score.infra_gap),
            "current_population_estimate": score.current_population_estimate,
            "state": indicator.state if indicator else None,
            "literacy_rate": float(indicator.literacy_rate) if indicator else None,
            "complaints": [
                {
                    "text": c.raw_input,
                    "topic": c.topic,
                    "urgency": c.urgency,
                    "submitted_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in complaints
            ],
        }
    finally:
        session.close()
