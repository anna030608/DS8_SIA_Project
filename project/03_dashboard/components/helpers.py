import math
import requests
import pandas as pd
from datetime import datetime

# ── CAMEO 코드 매핑 ───────────────────────────────────────
CAMEO_DESC = {
    '150': ('군사 태세 과시', '특정되지 않은 군사 태세 과시'),
    '151': ('경계 수준 강화', '경계 수준 강화 및 대비 태세'),
    '152': ('군사 훈련 실시', '군사 훈련 및 기동 실시'),
    '153': ('군사 순찰 강화', '군사 순찰 및 감시 강화'),
    '154': ('군대 동원 및 증강', '군대 동원 및 전력 증강'),
    '155': ('사이버 부대 강화', '사이버 부대 강화 및 작전'),
    '190': ('정규군 사용', '특정되지 않은 정규군 사용'),
    '191': ('봉쇄령 발동', '봉쇄령 발동 및 이동 제한'),
    '192': ('영토 점령', '영토 점령 및 군사 통제'),
    '193': ('소형 화기 교전', '소형 화기 및 경화기 교전'),
    '194': ('중형 화기 교전', '중형 화기 및 전차 교전'),
    '195': ('공중 무기 동원', '공중 무기 및 항공 전력 동원'),
    '196': ('휴전 합의 위반', '휴전 합의 위반 및 적대 행위'),
    '200': ('대규모 폭력 사용', '특정되지 않은 대규모 폭력'),
    '201': ('대규모 강제 추방', '대규모 강제 추방 및 이주'),
    '202': ('대규모 살상', '대규모 살상 및 인명 피해'),
    '203': ('인종 청소', '인종 청소 및 집단 박해'),
    '204': ('대량살상무기 사용', '대량살상무기 사용 및 위협'),
}


def get_alert_level(score):
    if score >= 0.7:
        return 'HIGH', '#ff2d2d'
    elif score >= 0.5:
        return 'MED', '#ff8c00'
    else:
        return 'LOW', '#ffd700'


def sensor_label(sensor_type):
    return {
        'OPT_HR': 'EO 고해상도',
        'OPT_MR': 'EO 중해상도',
        'OPT_SM': 'EO 소형',
        'SAR': 'SAR'
    }.get(sensor_type, sensor_type)


def estimate_swath(sensor_type, detailed_purpose, altitude):
    try:
        altitude = float(altitude) if altitude and str(altitude) != 'nan' else 500
    except:
        altitude = 500

    purpose = str(detailed_purpose).upper() if detailed_purpose else ''

    if sensor_type == 'SAR':
        fov = 30 if 'SCANSAR' in purpose else 4
    elif sensor_type == 'OPT_HR':
        fov = 1.5
    elif sensor_type == 'OPT_MR':
        fov = 8.0
    elif sensor_type == 'OPT_SM':
        if 'HYPERSPECTRAL' in purpose:   fov = 8
        elif 'MULTISPECTRAL' in purpose: fov = 12
        elif 'VIDEO' in purpose:         fov = 5
        else:                            fov = 15
    else:
        fov = 5

    return round(2 * altitude * math.tan(math.radians(fov / 2)), 1)


def get_cloud_cover(lat, lon, date_str):
    try:
        today = datetime.now().date()
        event_date = pd.to_datetime(date_str).date()

        if event_date < today:
            url = "https://archive-api.open-meteo.com/v1/archive"
            params = {
                "latitude": round(lat, 2),
                "longitude": round(lon, 2),
                "start_date": date_str,
                "end_date": date_str,
                "daily": ["cloud_cover_mean"],
                "timezone": "Asia/Tokyo"
            }
        else:
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": round(lat, 2),
                "longitude": round(lon, 2),
                "current": ["cloud_cover"],
                "timezone": "Asia/Tokyo"
            }

        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        cloud = (data['daily']['cloud_cover_mean'][0]
                 if event_date < today
                 else data['current']['cloud_cover'])

        return int(cloud) if cloud is not None else None

    except Exception:
        return None


def get_sensor_recommendation(cloud_cover, sensor_type):
    if cloud_cover is None:
        return None, '#888'
    if cloud_cover <= 30:
        return "EO 촬영 가능", '#00ff88'
    elif cloud_cover <= 70:
        if 'SAR' in sensor_type:
            return "SAR 촬영 권고", '#ff8c00'
        else:
            return "EO 촬영 어려움 · SAR 고려", '#ff8c00'
    else:
        return "SAR 촬영 권고", '#ff2d2d'
