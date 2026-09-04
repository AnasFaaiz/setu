import time 
from tasks.db import SessionLocal, Feedback

def dummy_job(name: str) -> str:
    print(f"[worker] starting job for {name}.. ")
    time.sleep(3)

    session = SessionLocal()
    try:
        entry = Feedback(
            raw_input=f"Test feedback from {name}",
            language="en",
            district="TestDistrict",
            topic="roads",
            urgency="medium",
            source_channel="text",
            status="processed",
        )
        session.add(entry)
        session.commit()
        result=f"Saved feedback id={entry.id} for {name}.."
    finally:
        session.close()

    print(f"[worker] done: {result}")
    return result
