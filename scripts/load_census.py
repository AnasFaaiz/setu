import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd
from tasks.db import SessionLocal
from tasks.schema import DistrictIndicator

df = pd.read_csv("dataset/census_district_data.csv")

df = df[[
    "District name",
    "State name",
    "Population",
    "Literate",
    "Households",
    "Housholds_with_Electric_Lighting",
    "LPG_or_PNG_Households",
    "Having_latrine_facility_within_the_premises_Total_Households",
    "Main_source_of_drinking_water_Tapwater_Households",
    "Households_with_Internet",
]]

df["literacy_rate"] = df["Literate"] / df["Population"]

df["infra_index"] = (
    (df["Housholds_with_Electric_Lighting"] / df["Households"]) +
    (df["LPG_or_PNG_Households"] / df["Households"]) +
    (df["Having_latrine_facility_within_the_premises_Total_Households"] / df["Households"]) +
    (df["Main_source_of_drinking_water_Tapwater_Households"] / df["Households"])
) / 4

df["internet_access_rate"] = df["Households_with_Internet"] / df["Households"]

df["district"] = df["District name"].str.lower().str.strip()
df["state"] = df["State name"].str.lower().str.strip()

session = SessionLocal()

for _, row in df.iterrows():
    entry = DistrictIndicator(
        district=row["district"],
        state=row["state"],
        population=int(row["Population"]),
        infra_index=round(row["infra_index"], 4),
        literacy_rate=round(row["literacy_rate"], 4),
        internet_access_rate=round(row["internet_access_rate"], 4),
    )
    session.merge(entry)

session.commit()
session.close()
print(f"Loaded {len(df)} districts into district_indicators.")
