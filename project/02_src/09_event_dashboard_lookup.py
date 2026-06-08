"""
09_event_dashboard_lookup.py   (Block 2)
----------------------------------------------------------------------
Dashboard data lookup for ONE event — pure CSV, no embeddings.

Given an event (date + coordinates), return:
  - priority : final priority_score and its components (why it scored that)
  - sats     : satellites passing near the coordinate, closest first
               (name, NORAD id, min distance km)

Join key (also the bridge to Block 1 later): SQLDATE + coordinate.

Read-only on the CSVs. Run locally.
"""

import pandas as pd

BASE = r"C:/Users/Jua/Desktop/DS/AIFFEL/00_AIFFELTHON/SIA_Project_Dash/project"
PRIORITY_CSV = BASE + "/01_data/processed/final_priority_geo.csv"
SAT_CSV = BASE + "/01_data/processed/satellite_passes.csv"

# coordinate match tolerance (both files use 1-decimal rounding like 24.0/119.0).
# Start exact-ish; widen if matches come back empty.
COORD_TOL = 0.05


def lookup_event(date: str, lat: float, lon: float,
                 priority_df: pd.DataFrame, sat_df: pd.DataFrame) -> dict:
    d = str(date)[:10]

    # --- priority: match date + coordinate ---
    p = priority_df[
        (priority_df["SQLDATE"].astype(str).str[:10] == d) &
        (priority_df["ActionGeo_Lat"].sub(lat).abs() <= COORD_TOL) &
        (priority_df["ActionGeo_Long"].sub(lon).abs() <= COORD_TOL)
    ]
    priority = None
    if not p.empty:
        row = p.iloc[0]
        priority = {
            "priority_score": round(float(row["priority_score"]), 3),
            "geo_level": row.get("geo_level"),
            "components": {
                "mentions": round(float(row["score_mentions"]), 3),
                "goldstein": round(float(row["score_goldstein"]), 3),
                "tone": round(float(row["score_tone"]), 3),
                "geo": round(float(row["score_geo"]), 3),
            },
        }

    # --- satellites: match date + coordinate, closest first ---
    s = sat_df[
        (sat_df["SQLDATE"].astype(str).str[:10] == d) &
        (sat_df["event_lat"].sub(lat).abs() <= COORD_TOL) &
        (sat_df["event_lon"].sub(lon).abs() <= COORD_TOL)
    ].sort_values("min_dist_km")
    sats = [
        {
            "satellite": r["satellite_name"],
            "norad_id": int(r["norad_id"]),
            "min_dist_km": round(float(r["min_dist_km"]), 1),
        }
        for _, r in s.iterrows()
    ]

    return {"date": d, "lat": lat, "lon": lon, "priority": priority, "sats": sats}


def describe(result: dict) -> None:
    print(f"event {result['date']}  ({result['lat']}, {result['lon']})")

    p = result["priority"]
    if p:
        c = p["components"]
        print(f"  우선순위 점수: {p['priority_score']}  (geo_level={p['geo_level']})")
        print(f"     구성  → mentions {c['mentions']}, goldstein {c['goldstein']}, "
              f"tone {c['tone']}, geo {c['geo']}")
    else:
        print("  우선순위 점수: (해당 사건을 priority 파일에서 찾지 못함)")

    if result["sats"]:
        print(f"  근처 위성 통과: {len(result['sats'])}건 (가까운 순)")
        for s in result["sats"][:5]:
            print(f"     - {s['satellite']}  (NORAD {s['norad_id']}, {s['min_dist_km']}km)")
    else:
        print("  근처 위성 통과: 없음")


if __name__ == "__main__":
    priority_df = pd.read_csv(PRIORITY_CSV)
    sat_df = pd.read_csv(SAT_CSV)

    # test with events that exist in the satellite file
    tests = [
        ("2021-01-19", 24.0, 119.0),
        ("2022-08-04", 24.0, 119.0),
    ]
    for date, lat, lon in tests:
        print("=" * 70)
        describe(lookup_event(date, lat, lon, priority_df, sat_df))
        print()