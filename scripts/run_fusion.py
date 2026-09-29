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

MIN_COMPLAINTS = int(os.getenv("FUSION_MIN_COMPLAINTS", "5"))
POPULATION_GROWTH_MULTIPLIER = float(os.getenv("POPULATION_GROWTH_MULTIPLIER", "1.2195"))


def load_processed_feedback(session):
    rows = session.execute(
        select(Feedback.district, Feedback.topic)
        .where(Feedback.status == "processed")
        .where(Feedback.district.isnot(None))
    ).all()
    return rows


def load_district_indicators(session):
    rows = session.execute(select(DistrictIndicator)).scalars().all()
    return {r.district: r for r in rows}


def compute_scores(feedback_rows, indicators):
    by_district = {}
    for district, topic in feedback_rows:
        by_district.setdefault(district, []).append(topic)

    results = []
    for district, topics in by_district.items():
        indicator = indicators.get(district)
        if indicator is None:
            continue  # district in feedback but not in census data, skip rather than guess

        complaint_count = len(topics)
        if complaint_count < MIN_COMPLAINTS:
            continue  # too few complaints to be a reliable signal

        current_population = int(indicator.population * POPULATION_GROWTH_MULTIPLIER)
        complaint_rate = (complaint_count / current_population) * 100000
        infra_gap = 1 - float(indicator.infra_index)
        priority_score = round(math.log(complaint_rate + 1) * infra_gap * math.log(complaint_count + 1), 4)

        dominant_topic = Counter(topics).most_common(1)[0][0]

        results.append({
            "district": district,
            "complaint_count": complaint_count,
            "dominant_topic": dominant_topic,
            "priority_score": priority_score,
            # breakdown, so the score is explainable, not a black box
            "complaint_rate_per_100k": round(complaint_rate, 4),
            "infra_gap": round(infra_gap, 4),
            "current_population_estimate": current_population,
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
        ))
    session.commit()


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
              f"infra_gap={r['infra_gap']})")
    return results


if __name__ == "__main__":
    run()
