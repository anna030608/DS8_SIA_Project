import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from skyfield.api import EarthSatellite, load, wgs84
from geopy.distance import geodesic
import os

# ── 데이터 로드 ───────────────────────────────────────────
with open("project/01_data/raw/tle_eo_sar.json") as f:
    tle_data = json.load(f)

df_events = pd.read_csv("project/01_data/processed/final_priority_geo.csv")
df_events['SQLDATE'] = pd.to_datetime(df_events['SQLDATE'])

# 1년 이내 이벤트만 필터링
one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
df_events = df_events[
    df_events['SQLDATE'] >= one_year_ago.strftime('%Y-%m-%d')
].copy()

print(f"대상 이벤트 수: {len(df_events)}개")
print(f"대상 위성 수: {len(tle_data)}개")

# ── Skyfield 설정 ─────────────────────────────────────────
ts = load.timescale()

# ── 위성 객체 생성 ────────────────────────────────────────
satellites = []
for sat_data in tle_data:
    try:
        sat = EarthSatellite.from_omm(ts, sat_data)
        satellites.append({
            'name': sat_data.get('OBJECT_NAME', 'UNKNOWN'),
            'norad_id': sat_data.get('NORAD_CAT_ID'),
            'satellite': sat
        })
    except Exception as e:
        continue

print(f"위성 객체 생성: {len(satellites)}개")

# ── 근접 궤도 필터링 ──────────────────────────────────────
# 이벤트 좌표에서 swath 절반(약 500km) 이내를 지나는 궤도 탐색
# (실제 촬영 가능 여부는 swath width로 별도 판단)
PROXIMITY_KM = 500

results = []

for _, event in df_events.iterrows():
    event_lat = event['ActionGeo_Lat']
    event_lon = event['ActionGeo_Long']
    event_date = event['SQLDATE']

    # 해당 이벤트 날짜 기준 ±12시간 탐색
    t_start = ts.from_datetime(
        event_date.to_pydatetime().replace(tzinfo=timezone.utc) - timedelta(hours=12)
    )
    t_end = ts.from_datetime(
        event_date.to_pydatetime().replace(tzinfo=timezone.utc) + timedelta(hours=12)
    )

    # 10분 간격으로 궤도 계산
    times = ts.linspace(t_start, t_end, 144)

    for sat_info in satellites:
        sat = sat_info['satellite']
        try:
            geocentric = sat.at(times)
            subpoint = wgs84.subpoint_of(geocentric)
            lats = subpoint.latitude.degrees
            lons = subpoint.longitude.degrees

            # 최근접 거리 계산
            min_dist = min(
                geodesic((event_lat, event_lon), (lat, lon)).km
                for lat, lon in zip(lats, lons)
            )

            if min_dist <= PROXIMITY_KM:
                results.append({
                    'SQLDATE': event['SQLDATE'],
                    'event_lat': event_lat,
                    'event_lon': event_lon,
                    'priority_score': event['priority_score'],
                    'satellite_name': sat_info['name'],
                    'norad_id': sat_info['norad_id'],
                    'min_dist_km': round(min_dist, 1)
                })
        except:
            continue

print(f"\n근접 궤도 탐지: {len(results)}건")

# ── 저장 ──────────────────────────────────────────────────
df_results = pd.DataFrame(results)
df_results.to_csv("project/01_data/processed/satellite_passes.csv", index=False)
print("저장 완료: satellite_passes.csv")