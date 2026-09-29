import os
import time 
import uuid 

from sqlalchemy import select, func 

from tasks.db import SessionLocal
from tasks.schema import Feedback, DistrictIndicator
from tasks.extractor import extract_batch
from tasks.batch_extraction import validate_batch
from datetime import datetime, timedelta

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
MAX_WAIT = int(os.getenv("BATCH_MAX_WAIT", "30"))
POLL = int(os.getenv("COLLECTOR_POLL_SECONDS", "2"))
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "3"))

def load_valid_districts() -> list[str]:
    session = SessionLocal()
    try:
        return [r[0] for r in session.execute(select(DistrictIndicator.district)).all()]
    finally:
        session.close()


def count_received() -> int:
    session = SessionLocal()
    try:
        return session.execute(
            select(func.count()).select_from(Feedback).where(Feedback.status == "received")
        ).scalar_one()
    finally:
        session.close()

def claim_batch() -> list[dict]:
    """Take up to BATCH_SIZE received rows and mark them processing."""
    session = SessionLocal()
    try:
        rows = session.execute(
            select(Feedback)
            .where(Feedback.status == "received")
            .order_by(Feedback.created_at)
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        ).scalars().all()

        batch = []
        for row in rows:
            row.status = "processing"
            row.attempts += 1
            batch.append({"id": str(row.id), "text": row.raw_input, "attempts": row.attempts})
        session.commit()
        return batch 
    finally:
        session.close()

def sweep_stuck_rows(stuck_after_minutes: int = 10) -> int:
    """Reset rows stuck in 'processing' for too long back to 'received'."""
    session = SessionLocal()
    try:
        cutoff=datetime.now(datetime.UTC) - timedelta(minutes=stuck_after_minutes)
        stuck = session.execute(
            select(Feedback)
            .where(Feedback.status == "processing")
            .where(Feedback.created_at < cutoff)
        ).scalars().all()

        for row in stuck:
            row.status = "received"

        session.commit()
        return len(stuck)
    finally:
        session.close()

def save_results(batch: list[dict], good: dict, bad: dict) -> None:
    attempts = {b["id"]: b["attempts"] for b in batch}
    session = SessionLocal()
    try:
        for fid, fields in good.items():
            row = session.get(Feedback, uuid.UUID(fid))
            row.topic = fields["topic"]
            row.district = fields["district"]
            row.urgency = fields["urgency"]
            if not row.language:
                row.language = fields["language_detected"]
            row.status = "processed"
            row.error_reason = None

        for fid, reason in bad.items():
            row = session.get(Feedback, uuid.UUID(fid))
            row.error_reason = reason
            row.status = "needs_review" if attempts[fid] >= MAX_ATTEMPTS else "received"

        session.commit()
    finally:
        session.close()


def run() -> None:
    valid_districts = load_valid_districts()
    print(f"[collector] started. {len(valid_districts)} districts loaded, "
          f"batch size {BATCH_SIZE}, max wait {MAX_WAIT}s, extractor={os.getenv('EXTRACTOR', 'gemini')}")

    last_flush = time.monotonic()
    last_sweep = time.monotonic()

    while True:
        if time.monotonic() - last_sweep >= 60:
            recovered = sweep_stuck_rows()
            if recovered:
                print(f"[collector] recovered {recovered} stuck row(s)")
            last_sweep = time.monotonic()

        waiting = count_received()
        due = waiting >= BATCH_SIZE or (waiting > 0 and time.monotonic() - last_flush >= MAX_WAIT)
        if not due:
            time.sleep(POLL)
            continue

        batch = claim_batch()
        last_flush = time.monotonic()
        if not batch:
            continue

        ids = [b["id"] for b in batch]
        print(f"[collector] processing batch of {len(batch)}")

        try:
            raw = extract_batch([{"id": b["id"], "text": b["text"]} for b in batch])
        except Exception as e:
            message = str(e)
            print(f"[collector] extractor failed: {message[:200]}")
            save_results(batch, {}, {i: f"extractor error: {message[:300]}" for i in ids})
            quota = "429" in message or "RESOURCE_EXHAUSTED" in message
            time.sleep(300 if quota else 30)
            continue

        good, bad = validate_batch(ids, raw, valid_districts)
        save_results(batch, good, bad)
        print(f"[collector] saved {len(good)} processed, {len(bad)} rejected")


if __name__ == "__main__":
    run()
