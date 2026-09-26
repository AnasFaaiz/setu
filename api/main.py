import uuid 
from fastapi import FastAPI 
from pydantic import BaseModel
import redis
from rq import Queue, Retry
from tasks.jobs import process_feedback
from tasks.db import SessionLocal 
from tasks.schema import Feedback 
from typing import Optional

app = FastAPI()
redis_conn = redis.Redis(host="localhost", port="6379")
queue = Queue(connection=redis_conn)

class FeedbackInput(BaseModel):
    raw_input: str 
    language: Optional[str]= None 
    source_channel: str 
    client_reference_id: Optional[str] = None 

@app.post("/submit-feedback")
def submit_feedback(payload: FeedbackInput):
    feedback_id = str(uuid.uuid4())

    session = SessionLocal()
    try:
        entry = Feedback(
            id=feedback_id,
            raw_input=payload.raw_input,
            language=payload.language,
            source_channel=payload.source_channel,
            client_reference_id=payload.client_reference_id,
            status="received"
        )
        session.add(entry)
        session.commit()
    finally:
        session.close()

    queue.enqueue(process_feedback, feedback_id, retry=Retry(max=3, interval=[10,30,60]))

    return {"id": feedback_id, "status": "received"}

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

