import time 
from tasks.db import SessionLocal
from tasks.schema import Feedback

def process_feedback(feedback_id: str) -> str:
    print(f"[worker] processing feedback {feedback_id}")

    session = SessionLocal()
    try:
        entry = session.get(Feedback, feedback_id)
        if entry is None:
            return f"No feedback found for id {feedback_id}"
        
        entry.status = "processing"
        session.commit()

        time.sleep(3)

        # dummy extraction for now.
        entry.topic = "roads"
        entry.district = "testdistrict"
        entry.urgency = "medium"
        entry.status = "processed"
        session.commit()

        result = f"Processed feedback id={feedback_id}"
    except Exception as e:
        session.rollback()
        entry = session.get(Feedback, feedback_id)
        if entry:
            entry.status = "failed"
            session.commit()
        result = f"failed feedback for id={feedback_id}: {e}"
    finally:
        session.close()

    print(f"[worker] done: {result}")

    return result
