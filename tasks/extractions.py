import os
import json 
from google import genai
from google.genai import types 

client = genai.Client(api_key=os.getenv("GEMINI_API_key"))

EXTRACTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "topic": {
            "type": "STRING",
            "enum": ["roads", "water", "electricity", "health", "sanitation", "other"],
        },
        "district": {
            "type": "STRING",
            "nullable": True,
            "description": "The district name if clearly stated in the text, otherwise null. Do not guess.",
        },
        "urgency": {
            "type": "STRING",
            "enum": ["low", "medium", "high"],
        },
        "language_detected": {
            "type": "STRING",
            "description": "ISO 639-1 code of the language the input was written in, e.g. 'hi','en', 'te'.",
        },
    },
    "required": ["topic", "district", "urgency", "language_detected"],
}

PROMPT_TEMPLATE = """ You are extracting structured data from a citizen's infrasture complaint submitted in India. The text may be in any Indian language or English, and may mix languages.
Extract only what is clearly present. If the district/location is not explicitly mentioned or cannot be confidently identified, return null for district - do not guess a plausible-sounding district.

Citizen input: 
\"\"\"{raw_text}\"\"\"
"""

def extract_feedback_fields(raw_text: str) -> dict:
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=PROMPT_TEMPLATE.format(raw_text=raw_text),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=EXTRACTION_SCHEMA,
        ),
    )
    return json.loads(response.text)

