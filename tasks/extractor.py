import os 

def extract_batch(complaints: list[dict]) -> list[dict]:
    """complaints: [{"id": ..., "text": ...}]. Returns raw, unvalidated results."""

    if os.getenv("EXTRACTOR", "gemini") == "fake":
        from tasks.fake_extraction import fake_extract_batch
        return fake_extract_batch(complaints)

    from tasks.batch_extraction import call_gemini_batch
    return call_gemini_batch(complaints)
