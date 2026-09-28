"""DEV STUB ONLY: keyword-based stand-in for Gemini. Not for real results."""

KEYWORDS = {
    "roads": ["road", "sadak", "gaddha", "pothole", "streetlight", "street light"],
    "water": ["water", "paani", "pani", "tap", "pipeline"],
    "electricity": ["bijli", "electricity", "power cut", "transformer"],
    "health": ["hospital", "doctor", "health centre", "clinic", "medicine"],
    "sanitation": ["garbage", "drain", "sewage", "toilet", "kachra"],
}


def fake_extract_batch(complaints: list[dict]) -> list[dict]:
    results = []
    for c in complaints:
        text = c["text"].lower()
        topic = "other"
        for name, words in KEYWORDS.items():
            if any(w in text for w in words):
                topic = name
                break
        results.append({
            "id": c["id"],
            "topic": topic,
            "district": None,
            "urgency": "high" if any(w in text for w in ["days", "weeks", "months", "suffering"]) else "medium",
            "language_detected": "en",
        })
    return results
