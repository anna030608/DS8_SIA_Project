"""
이 버전은 원래 주아님이 100km로 기준을 잡아둔 것을
각 센서별 고도, FOV, Swath 반영 로직을 통해
센서별로 기준이 바뀌도록 수정한 버전임

추후에, 센서 정보 연결이 가능하다면 연결하여
정확한 센서 swath 반영이 가능하도록..
"""



import jso
import math
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from skyfield.api import EarthSatellite, load, wgs84
from geopy.distance import geodesic

# ── 데이터 로드 ────────────────────────────────────────────
# 위성 후보군 + TLE + 메타데이터 통합 JSON으로 변경
with open("project/01_data/raw/commercial_eo_sar_20260522.json") as f:
    tle_data = json.load(f)

df_events = pd.read_csv("project/01_data/processed/final_priority_geo.csv")
df_events['SQLDATE'] = pd.to_datetime(df_events['SQLDATE'])

print(f"대상 이벤트 수: {len(df_events)}개")
print(f"대상 위성 수:   {len(tle_data)}개")


# ── obs_radius 계산 함수 ───────────────────────────────────
# sensor 컬럼(OPT_HR / OPT_SM / OPT_MR / SAR)을 우선 기준으로 삼고
# detailed_purpose로 세분화. FOV는 센서 분류별 경험값.
# swath = 2 * altitude * tan(FOV/2) → obs_radius = swath / 2

FALLBACK_OBS_RADIUS_KM = 50   # sensor 정보 없는 위성 기본값

def estimate_swath(sensor, detailed_purpose, altitude):
    try:
        altitude = float(altitude) if altitude else 500
    except Exception:
        altitude = 500

    purpose = str(detailed_purpose).upper() if pd.notna(detailed_purpose) and detailed_purpose else ''

    if sensor == 'SAR':
        if 'SCANSAR' in purpose:
            fov = 30        # 광역 SAR (ScanSAR 모드)
        elif 'SYNTHETIC APERTURE' in purpose:
            fov = 5         # 고해상도 SAR
        else:
            fov = 4         # 일반 레이더 (Radar Imaging)

    elif sensor == 'OPT_SM':
        # 소형 광학 위성 (Planet FLOCK 등)
        # detailed_purpose NaN이 대부분 → sensor만으로 판정
        fov = 1.0

    elif sensor == 'OPT_MR':
        # 중해상도 광학 (Multispectral 계열)
        fov = 10.0

    elif sensor == 'OPT_HR':
        # 고해상도 광학 — purpose와 고도로 세분
        if 'VIDEO' in purpose:
            fov = 5
        elif 'HYPERSPECTRAL' in purpose:
            fov = 8
        elif 'INFRARED' in purpose:
            fov = 15
        else:
            # Optical Imaging 기본: 고도가 낮을수록 고해상도 → 좁은 FOV
            if altitude < 500:
                fov = 1.5
            elif altitude < 600:
                fov = 2.0
            elif altitude < 700:
                fov = 8.0
            else:
                fov = 12.0

    else:
        fov = 8.0   # 분류 불명 fallback

    return round(2 * altitude * math.tan(math.radians(fov / 2)), 1)


# ── 위성 객체 생성 + obs_radius 계산 ──────────────────────
# altitude_km이 JSON에 포함되어 있어 satellite_info.csv 불필요
ts = load.timescale()

satellites = []
for sat_data in tle_data:
    try:
        sat = EarthSatellite(
            sat_data['TLE_LINE1'],
            sat_data['TLE_LINE2'],
            sat_data['OBJECT_NAME'],
            ts
        )

        swath_km = estimate_swath(
            sat_data.get('sensor'),
            sat_data.get('detailed_purpose'),
            sat_data.get('altitude_km')
        )
        obs_radius = swath_km / 2 if swath_km else FALLBACK_OBS_RADIUS_KM

        satellites.append({
            'name':          sat_data['OBJECT_NAME'],
            'norad_id':      sat_data['NORAD_CAT_ID'],
            'sensor':        sat_data.get('sensor'),
            'satellite':     sat,
            'obs_radius_km': round(obs_radius, 1)
        })
    except Exception:
        continue

print(f"위성 객체 생성: {len(satellites)}개")


# ── Pass 판정 (위성별 obs_radius 적용) ────────────────────
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
        sat           = sat_info['satellite']
        obs_radius_km = sat_info['obs_radius_km']

        try:
            geocentric = sat.at(times)
            subpoint   = wgs84.subpoint_of(geocentric)
            lats       = subpoint.latitude.degrees
            lons       = subpoint.longitude.degrees

            distances = [
                geodesic((event_lat, event_lon), (lat, lon)).km
                for lat, lon in zip(lats, lons)
            ]
            min_dist = min(distances)

            if min_dist <= obs_radius_km:
                track_lats = [round(float(lat), 4) for lat in lats]
                track_lons = [round(float(lon), 4) for lon in lons]

                results.append({
                    'SQLDATE':        event['SQLDATE'],
                    'event_lat':      event_lat,
                    'event_lon':      event_lon,
                    'priority_score': event['priority_score'],
                    'satellite_name': sat_info['name'],
                    'norad_id':       sat_info['norad_id'],
                    'sensor':         sat_info['sensor'],
                    'obs_radius_km':  obs_radius_km,
                    'min_dist_km':    round(min_dist, 1),
                    'track_lats':     str(track_lats),
                    'track_lons':     str(track_lons)
                })
        except Exception:
            continue

    if (idx + 1) % 50 == 0:
        print(f"진행: {idx+1}/{len(df_events)} 이벤트 처리 완료")

print(f"\n근접 궤도 탐지: {len(results)}건")

df_results = pd.DataFrame(results)
df_results.to_csv("project/01_data/processed/satellite_passes.csv", index=False)
print("저장 완료: satellite_passes.csv")