"""
Generates synthetic citizen complaints for demo purposes. Not real citizen data.
Writes directly to the feedback table as 'received' rows so the collector
picks them up through the normal pipeline (batching + harness validation
still apply, same as real submissions). District names are woven into the
complaint text itself, so Gemini extracts them the same way it would for
a real citizen's submission, no shortcuts around the pipeline.
"""
import random
import uuid
from datetime import datetime, timedelta

from tasks.db import SessionLocal
from tasks.schema import Feedback, DistrictIndicator

TEMPLATES = {
    "roads": [
        "Sadak bahut kharab hai, {n} mahine se gaddha hai",
        "Big pothole near the main market, causing accidents",
        "No streetlight on our road, very dark at night",
        "Road construction has been stopped midway for {n} weeks",
    ],
    "water": [
        "Paani ki supply {n} dino se band hai",
        "Water supply has been irregular for {n} days now",
        "Pipeline leak wasting water for over a week",
        "No clean drinking water in our area for {n} days",
    ],
    "electricity": [
        "Humare mohalle mein bijli roz {n}-{n2} ghante cut rehta hai",
        "Transformer burnt, no power since {n} days",
        "Frequent power cuts disrupting daily life",
        "Voltage fluctuation damaging home appliances",
    ],
    "health": [
        "Primary health centre has no doctor available",
        "Clinic has no medicine stock for over a month",
        "Hospital overcrowded, patients waiting for hours",
        "No ambulance service reachable in emergencies",
    ],
    "sanitation": [
        "Garbage not collected for {n} weeks now",
        "Open drain overflowing near residential area",
        "No public toilets in the market area",
        "Sewage water entering homes during rain",
    ],
}

URGENCY_HINTS = ["", "", " Please help urgently.", " This is a serious problem.", " Been suffering for a long time."]

PLACEMENTS = [
    "{text} ({district})",
    "{text} in {district}",
    "{district}: {text}",
    "{text} — {district} area",
]


def pick_complaint(district_name):
    topic = random.choice(list(TEMPLATES.keys()))
    template = random.choice(TEMPLATES[topic])
    text = template.format(n=random.randint(2, 6), n2=random.randint(6, 9))
    text += random.choice(URGENCY_HINTS)
    placement = random.choice(PLACEMENTS)
    return placement.format(text=text, district=district_name.title())


def load_all_districts():
    session = SessionLocal()
    try:
        return [r.district for r in session.query(DistrictIndicator).all()]
    finally:
        session.close()


def generate(hotspot_count=6, hotspot_range=(8, 15), scatter_count=18, scatter_range=(1, 4)):
    all_districts = load_all_districts()
    random.shuffle(all_districts)

    hotspots = all_districts[:hotspot_count]
    scattered = all_districts[hotspot_count:hotspot_count + scatter_count]

    rows = []
    for district in hotspots:
        count = random.randint(*hotspot_range)
        for _ in range(count):
            rows.append((district, pick_complaint(district)))

    for district in scattered:
        count = random.randint(*scatter_range)
        for _ in range(count):
            rows.append((district, pick_complaint(district)))

    random.shuffle(rows)
    return rows, hotspots


def insert(rows):
    session = SessionLocal()
    try:
        base_time = datetime.utcnow() - timedelta(days=10)
        for i, (_district, text) in enumerate(rows):
            entry = Feedback(
                id=str(uuid.uuid4()),
                raw_input=text,
                source_channel=random.choice(["text", "voice", "whatsapp"]),
                status="received",
                created_at=base_time + timedelta(hours=i * 2),
            )
            session.add(entry)
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    rows, hotspots = generate()
    insert(rows)
    print(f"Inserted {len(rows)} synthetic complaints.")
    print(f"Intended hotspot districts: {hotspots}")
    print("Note: actual district in each row will be whatever Gemini/stand-in extracts from the text, not assigned directly.")
