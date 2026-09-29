import os
from dotenv import load_dotenv

load_dotenv()


def extract_batch(complaints: list[dict]) -> list[dict]:
    """complaints: [{"id": ..., "text": ...}]. Returns raw, unvalidated results."""

    if os.getenv("EXTRACTOR", "gemini") == "fake":
        from tasks.fake_extraction import fake_extract_batch
        from tasks.db import SessionLocal
        from tasks.schema import DistrictIndicator
        from sqlalchemy import select

        session = SessionLocal()
        try:
            valid_districts = [r[0] for r in session.execute(select(DistrictIndicator.district)).all()]
        finally:
            session.close()

        return fake_extract_batch(complaints, valid_districts)

    from tasks.batch_extraction import call_gemini_batch
    return call_gemini_batch(complaints)
