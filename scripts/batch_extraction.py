import os 
import json 
import difflib
from dotenv import load_dotenv
from google import genai
from google.genai import types 

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

TOPICS = ["roads", "water", "electricity", "healthcare", "sanitation", "other"]
URGENCIES = ["low", "medium", "high"]

BATCH_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "types": "OBJECT",
        "properties": {
            "id": {"type": "STRING"},
            "topic": {"type": "STRING", "enum": TOPICS},
            "district": {"type": "STRING", "nullable": True},
            "urgency": {"type": "STRING", "enum": URGENCIES},
            "language_detected": {"type": "STRING"},
        },
        "required": ["id", "topic", "district", "urgency", "language_detected"],
    },
}

PROMPT = """You are extracting structured data from citizen infrastructure complaints in India. 
Complaints may be in any Indian language, English, or a mix.

RULES:
    - Return extractly one result per complain, using the same id you were given.
    - topic must be one of: roads, water, electricity, health, sanitation, other.
    - Streetlights and road lighting count as "roads". Power cuts and electricity supply count as "electricity".
    - district: only if a district or city is clearly stated in the text. Otherwise null. Never guess.
    - urgency: low, medium or high, based on how serious the complaint sounds. 

Complaints (JSON):
{complaints_json}
"""

def call_gemini_batch(complaints: list[dict]) -> list[dict]:
    """complaints: [{"id": "...", "text": "..."}]. Returns Gemini's raw parsed list."""
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=PROMPT.format(complaints_json=json.dumps(complaints, ensure_ascii=False)),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=BATCH_SCHEMA
        ),
    )
    return json.loads(response.text)

def match_district(name, valid_districts: list[str]):
    if not name:
        return None 
    cleaned = name.lower().strip()
    if cleaned in valid_districts:
        return cleaned 
    close = difflib.get_close_matches(cleaned, valid_districts, n=1, cutoff=0.85)
    return close[0] if close else None 

def validate_batch(sent_ids: list[str], raw_items: list[dict], valid_districts: list[str]):
    """Returns (good, bad). good: {id: fields}. bad: {id: reason}."""

    good, bad = {}, {}
    seen = set()

    for item in raw_items:
        item_id = item.get("id")
        if item_id not in sent_ids:
            continue
        if item_id in seen:
            bad[item_id] = "duplicate id in response"
            good.pop(item_id, None)
            continue
        seen.add(item_id)

        if item.get("topic") not in TOPICS or item.get("urgency") not in URGENCIES:
            bad[item_id] = "invalid topic or urgency"
            continue 

        good[item_id] = {
            "topic": item["topic"],
            "urgency": item["urgency"],
            "district": match_district(item.get("district"), valid_districts),
            "language_detected": item.get("language_detected"),
        }

    for missing in set(sent_ids) - seen:
        bad[missing] = "missing from response"

    return good, bad
