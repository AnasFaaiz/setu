from tasks.db import SessionLocal
from tasks.schema import Feedback
from tasks.extractions import extract_feedback_fields

def process_feedback(feedback_id: str) -> str:
    print(f"[worker] processing feedback {feedback_id}")

    session = SessionLocal()
    try:
        entry = session.get(Feedback, feedback_id)
        if entry is None:
            return f"No feedback found for id {feedback_id}"
        
        entry.status = "processing"
        session.commit()

        extracted = extract_feedback_fields(entry.raw_input)

        entry.topic = extracted.get("topic")
        entry.district = extracted.get("district")
        entry.urgency = extracted.get("urgency")
        if not entry.language:
            entry.language = extracted.get("language_detected")
        entry.status = "processed"
        session.commit()

        result = f"Processed feedback id={feedback_id}: {extracted}"
        print(f"[worker] done: {result}")
        return result

    except Exception as e:
        session.rollback()
        print(f"[worker] error processing {feedback_id}, will retry if attempts remain: {e}")
        raise # re-raise so RQ's Retry mechanism triggers
    finally:
        session.close()

    print(f"[worker] done: {result}")

    return result
