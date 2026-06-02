import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from skyfield.api import EarthSatellite, load, wgs84
from geopy.distance import geodesic
import os

with open("project/01_data/raw/tle_eo_sar.json") as f:
    tle_data = json.load(f)

df_events = pd.read_csv("project/01_data/processed/final_priority_geo.csv")
df_events['SQLDATE'] = pd.to_datetime(df_events['SQLDATE'])

# ── 중복 좌표 제거 (날짜+좌표 기준) ─────────────────────
df_events = df_events.drop_duplicates(subset=['ActionGeo_Lat', 'ActionGeo_Long', 'SQLDATE'])
df_events = df_events.reset_index(drop=True)

print(f"대상 이벤트 수 (중복 제거 후): {len(df_events)}개")
print(f"대상 위성 수: {len(tle_data)}개")

ts = load.timescale()

satellites = []
for sat_data in tle_data:
    try:
        sat = EarthSatellite.from_omm(ts, sat_data)
        satellites.append({
            'name': sat_data.get('OBJECT_NAME', 'UNKNOWN'),
            'norad_id': sat_data.get('NORAD_CAT_ID'),
            'satellite': sat
        })
    except:
        continue

print(f"위성 객체 생성: {len(satellites)}개")

PROXIMITY_KM = 30
results = []

for idx, event in df_events.iterrows():
    event_lat  = event['ActionGeo_Lat']
    event_lon  = event['ActionGeo_Long']
    event_date = event['SQLDATE']

    t_start = ts.from_datetime(
        event_date.to_pydatetime().replace(tzinfo=timezone.utc) - timedelta(hours=12)
    )
    t_end = ts.from_datetime(
        event_date.to_pydatetime().replace(tzinfo=timezone.utc) + timedelta(hours=12)
    )
    times = ts.linspace(t_start, t_end, 144)

    for sat_info in satellites:
        sat = sat_info['satellite']
        try:
            geocentric = sat.at(times)
            subpoint   = wgs84.subpoint_of(geocentric)
            lats = subpoint.latitude.degrees
            lons = subpoint.longitude.degrees

            min_dist = min(
                geodesic((event_lat, event_lon), (lat, lon)).km
                for lat, lon in zip(lats, lons)
            )

            if min_dist <= PROXIMITY_KM:
                track_lats = [round(float(lat), 4) for lat in lats]
                track_lons = [round(float(lon), 4) for lon in lons]

                results.append({
                    'SQLDATE':          event['SQLDATE'],
                    'event_lat':        event_lat,
                    'event_lon':        event_lon,
                    'priority_score':   event['priority_score'],
                    'satellite_name':   sat_info['name'],
                    'norad_id':         sat_info['norad_id'],
                    'min_dist_km':      round(min_dist, 1),
                    'track_lats':       str(track_lats),
                    'track_lons':       str(track_lons)
                })
        except:
            continue

    if (idx + 1) % 50 == 0:
        print(f"진행: {idx+1}/{len(df_events)} 이벤트 처리 완료")

print(f"\n근접 궤도 탐지: {len(results)}건")

df_results = pd.DataFrame(results)
df_results.to_csv("project/01_data/processed/satellite_passes.csv", index=False)
print("저장 완료: satellite_passes.csv")