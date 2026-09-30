"""
Fusion job: joins processed feedback with district_indicators to compute
a priority_score per district. Run manually or on a schedule. Overwrites
hotspot_scores each run.
"""
import os
from collections import Counter
from sqlalchemy import select, func

from tasks.db import SessionLocal
from tasks.schema import Feedback, DistrictIndicator, HotspotScore
import math
from difflib import SequenceMatcher 

MIN_COMPLAINTS = int(os.getenv("FUSION_MIN_COMPLAINTS", "5"))
POPULATION_GROWTH_MULTIPLIER = float(os.getenv("POPULATION_GROWTH_MULTIPLIER", "1.2195"))
DUPLICATE_SIMILARITY_THRESHOLD = float(os.getenv("DUPLICATE_SIMILARITY_THRESHOLD", "0.75"))

def load_processed_feedback(session):
    rows = session.execute(
        select(Feedback.district, Feedback.topic, Feedback.raw_input)
        .where(Feedback.status == "processed")
        .where(Feedback.district.isnot(None))
    ).all()
    return rows


def load_district_indicators(session):
    rows = session.execute(select(DistrictIndicator)).scalars().all()
    return {r.district: r for r in rows}


def compute_scores(feedback_rows, indicators):
    by_district = {}
    for district, topic, raw_input in feedback_rows:
        entry = by_district.setdefault(district, {"topics": [], "texts": []})
        entry["topics"].append(topic)
        entry["texts"].append(raw_input)

    results = []
    for district, data in by_district.items():
        topics = data["topics"]
        texts = data["texts"]
        indicator = indicators.get(district)
        if indicator is None:
            continue  # district in feedback but not in census data, skip rather than guess

        complaint_count = len(topics)
        if complaint_count < MIN_COMPLAINTS:
            continue  # too few complaints to be a reliable signal

        distinct_issue_count = count_distinct_issues(texts)

        current_population = int(indicator.population * POPULATION_GROWTH_MULTIPLIER)
        # Use distinct issues, not raw complaint count, for the rate: many
        # reports of the same problem shouldn'''t score N times higher than
        # one report of it.
        complaint_rate = (distinct_issue_count / current_population) * 100000
        infra_gap = 1 - float(indicator.infra_index)

        # Under-reporting correction: districts with low internet access and
        # low literacy are structurally less able to submit digital complaints,
        # so raw complaint volume likely understates their real need. This
        # scales the score upward proportional to that access gap. A district
        # with full access gets no adjustment (multiplier = 1); a district with
        # zero access gets roughly double weight (multiplier approaches 2).
        internet_rate = float(indicator.internet_access_rate) if indicator.internet_access_rate is not None else 0.5
        literacy_rate = float(indicator.literacy_rate) if indicator.literacy_rate is not None else 0.5
        access_gap = 1 - ((internet_rate + literacy_rate) / 2)
        underreporting_multiplier = round(1 + access_gap, 4)

        priority_score = round(
            math.log(complaint_rate + 1) * infra_gap * math.log(distinct_issue_count + 1) * underreporting_multiplier,
            4
        )

        dominant_topic = Counter(topics).most_common(1)[0][0]

        results.append({
            "district": district,
            "complaint_count": complaint_count,
            "distinct_issue_count": distinct_issue_count,
            "dominant_topic": dominant_topic,
            "priority_score": priority_score,
            # breakdown, so the score is explainable, not a black box
            "complaint_rate_per_100k": round(complaint_rate, 4),
            "infra_gap": round(infra_gap, 4),
            "current_population_estimate": current_population,
            "underreporting_multiplier": underreporting_multiplier,
        })

    results.sort(key=lambda r: r["priority_score"], reverse=True)
    return results


def save_scores(session, results):
    session.query(HotspotScore).delete()
    for r in results:
        session.add(HotspotScore(
            district=r["district"],
            feedback_count=r["complaint_count"],
            dominant_topic=r["dominant_topic"],
            priority_score=r["priority_score"],
            complaint_rate_per_100k=r["complaint_rate_per_100k"],
            infra_gap=r["infra_gap"],
            current_population_estimate=r["current_population_estimate"],
            underreporting_multiplier=r["underreporting_multiplier"],
            distinct_issue_count=r["distinct_issue_count"],
        ))
    session.commit()

def count_distinct_issues(complaint_texts: list[str]) -> int:
    """
    Groups near-duplicate complaints (same underlying issue reported multiple
    times) so raw volume doesn't overstate distinct problems. Simple pairwise
    similarity, fine at this scale; would need a proper clustering approach
    (embeddings + a vector index) at real volume.
    """
    groups = []
    for text in complaint_texts:
        matched = False
        for group in groups:
            if SequenceMatcher(None, text.lower(), group[0].lower()).ratio() >= DUPLICATE_SIMILARITY_THRESHOLD:
                group.append(text)
                matched = True
                break
        if not matched:
            groups.append([text])
    return len(groups)

def run():
    session = SessionLocal()
    try:
        feedback_rows = load_processed_feedback(session)
        indicators = load_district_indicators(session)
        results = compute_scores(feedback_rows, indicators)
        save_scores(session, results)
    finally:
        session.close()

    print(f"Scored {len(results)} districts (minimum {MIN_COMPLAINTS} complaints each).")
    print("Top 5:")
    for r in results[:5]:
        print(f"  {r['district']}: score={r['priority_score']} "
              f"(complaints={r['complaint_count']}, rate/100k={r['complaint_rate_per_100k']}, "
              f"infra_gap={r['infra_gap']}, distinct_issues={r['distinct_issue_count']}, underreporting_x={r['underreporting_multiplier']})")
    return results


if __name__ == "__main__":
    run()
