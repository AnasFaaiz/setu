"""
End-to-end smoke test, run before submission to confirm the whole pipeline
still works after tonight's changes. Not a full test suite, a bounded set
of checks tied to specific bugs/decisions made during development.
"""
import time
import requests

API = "http://localhost:8000"
PASS = "PASS"
FAIL = "FAIL"
results = []


def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((name, status, detail))
    print(f"[{status}] {name}" + (f" — {detail}" if detail and status == FAIL else ""))


def submit(text, channel="text"):
    r = requests.post(f"{API}/submit-feedback", json={"raw_input": text, "source_channel": channel})
    return r


def wait_for_status(feedback_id, timeout=40):
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f"{API}/status/{feedback_id}")
        data = r.json()
        if data.get("status") in ("processed", "needs_review", "failed"):
            return data
        time.sleep(2)
    return {"status": "timeout"}


def test_basic_submission():
    r = submit("Test smoke check: pothole near the market")
    check("submit returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    check("submit returns received status", data.get("status") == "received", str(data))
    return data.get("id")


def test_no_district_returns_null(feedback_id):
    result = wait_for_status(feedback_id)
    check("no-district complaint processed", result.get("status") == "processed", str(result))
    check("district is null when not stated", result.get("district") is None, str(result))


def test_streetlight_disambiguation(feedback_id):
    result = wait_for_status(feedback_id)
    check("streetlight complaint processed", result.get("status") == "processed", str(result))
    check("streetlight classified as roads, not electricity",
          result.get("topic") == "roads", f"got topic={result.get('topic')}")


def test_rate_limit():
    codes = []
    for i in range(25):
        r = requests.post(f"{API}/submit-feedback",
                           json={"raw_input": f"Rate limit smoke test {i}", "source_channel": "text"})
        codes.append(r.status_code)
    check("requests succeed until the rate limit kicks in", 200 in codes and 429 in codes, f"got {codes}")
    check("requests beyond limit get 429", 429 in codes[20:], f"got {codes[20:]}")


def test_hotspots_endpoint():
    r = requests.get(f"{API}/hotspots?limit=5")
    check("hotspots endpoint returns 200", r.status_code == 200, f"got {r.status_code}")
    data = r.json()
    check("hotspots returns a list", isinstance(data, list))
    if data:
        required_fields = {
            "district", "priority_score", "feedback_count", "dominant_topic",
            "complaint_rate_per_100k", "infra_gap", "underreporting_multiplier",
            "distinct_issue_count", "current_population_estimate",
        }
        missing = required_fields - set(data[0].keys())
        check("hotspot rows have all fields the dashboard reads", not missing, f"missing: {missing}")
        scores = [d["priority_score"] for d in data]
        check("hotspots are sorted descending by score", scores == sorted(scores, reverse=True))
        check("no negative scores", all(s >= 0 for s in scores), str(scores))
    else:
        check("hotspots has data to check", False, "empty — run scripts.run_fusion first")


def run():
    print("=== Setu smoke test ===\n")

    print("-- basic submission --")
    basic_id = test_basic_submission()

    print("\n-- no-district edge case --")
    r = submit("There is no streetlight on our road, very dark at night, and no bus stop nearby either")
    no_district_id = r.json().get("id")

    print("\n-- streetlight disambiguation --")
    r = submit("No streetlight on our road in Udaipur, very dark at night")
    streetlight_id = r.json().get("id")

    print("\n-- waiting for batch to process (up to 40s) --")
    if no_district_id:
        test_no_district_returns_null(no_district_id)
    if streetlight_id:
        test_streetlight_disambiguation(streetlight_id)

    print("\n-- hotspots endpoint --")
    test_hotspots_endpoint()

    print("\n-- rate limiting (spends real requests, run last) --")
    test_rate_limit()

    print("\n=== Summary ===")
    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    print(f"{passed} passed, {failed} failed")
    if failed:
        print("\nFailed checks:")
        for name, status, detail in results:
            if status == FAIL:
                print(f"  - {name}: {detail}")


if __name__ == "__main__":
    run()
