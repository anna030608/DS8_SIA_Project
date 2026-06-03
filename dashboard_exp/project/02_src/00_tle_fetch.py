import os
import json
import requests
import pandas as pd
import pandas_gbq
from google.oauth2 import service_account
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GDELT_PATH   = os.path.join(BASE_DIR, 'project/01_data/raw/gdelt_raw.csv')
TLE_PATH     = os.path.join(BASE_DIR, 'project/01_data/raw/tle_eo_sar.json')
UCS_PATH     = os.path.join(BASE_DIR, 'project/01_data/raw/ucs_eo_sar_filtered.csv')
GCP_KEY      = os.path.join(BASE_DIR, 'google_key.json')
ST_KEY       = os.path.join(BASE_DIR, 'spacetrack_key.json')
PROJECT_ID   = 'coral-bucksaw-482803-p2'

CAMEO_CODES = [
    '150','151','152','153','154','155',
    '190','191','192','193','194','195','196',
    '200','201','202','203','204'
]

# ── 1. GDELT 증분 업데이트 ─────────────────────────────────
def fetch_gdelt():
    print("\n[1/2] GDELT 증분 업데이트 시작")

    # 기존 파일에서 마지막 날짜 확인
    if os.path.exists(GDELT_PATH):
        df_existing = pd.read_csv(GDELT_PATH)
        df_existing['SQLDATE'] = pd.to_datetime(df_existing['SQLDATE'])
        last_date = df_existing['SQLDATE'].max()
        last_int  = int(last_date.strftime('%Y%m%d'))
        print(f"기존 데이터 마지막 날짜: {last_date.date()} → 이후 데이터만 가져옵니다")
    else:
        df_existing = None
        last_int    = 20130401
        print("기존 파일 없음 → 2013년 4월부터 전체 가져옵니다")

    formatted_codes = ", ".join([f"'{c}'" for c in CAMEO_CODES])
    query = f"""
    SELECT
        SQLDATE,
        EventCode,
        GoldsteinScale,
        NumMentions,
        AvgTone,
        ActionGeo_Type,
        ActionGeo_Lat,
        ActionGeo_Long,
        SOURCEURL
    FROM `gdelt-bq.full.events`
    WHERE SQLDATE > {last_int}
      AND (
        (Actor1CountryCode = 'CHN' AND Actor2CountryCode = 'TWN') OR
        (Actor1CountryCode = 'TWN' AND Actor2CountryCode = 'CHN')
      )
      AND EventCode IN ({formatted_codes})
      AND IsRootEvent = 1
      AND ActionGeo_Type IN (3, 4, 5)
    """

    credentials = service_account.Credentials.from_service_account_file(GCP_KEY)
    df_new = pandas_gbq.read_gbq(query, project_id=PROJECT_ID, credentials=credentials)

    if len(df_new) == 0:
        print("새로운 데이터 없음 — 업데이트 불필요")
        return

    df_new['SQLDATE'] = pd.to_datetime(df_new['SQLDATE'].astype(str), format='%Y%m%d')

    if df_existing is not None:
        df_merged = pd.concat([df_existing, df_new], ignore_index=True)
        df_merged = df_merged.drop_duplicates()
    else:
        df_merged = df_new

    df_merged.to_csv(GDELT_PATH, index=False)
    print(f"GDELT 업데이트 완료: +{len(df_new)}건 추가 → 총 {len(df_merged)}건")


# ── 2. Space-Track TLE 업데이트 ───────────────────────────
def fetch_tle():
    print("\n[2/2] Space-Track TLE 업데이트 시작")

    with open(ST_KEY, encoding='utf-8') as f:
        st_cred = json.load(f)

    session = requests.Session()

    # 로그인
    login_url  = 'https://www.space-track.org/ajaxauth/login'
    login_data = {'identity': st_cred['username'], 'password': st_cred['password']}
    resp = session.post(login_url, data=login_data)
    if resp.status_code != 200:
        print(f"Space-Track 로그인 실패: {resp.status_code}")
        return
    print("Space-Track 로그인 성공")

    # UCS 파일에서 NORAD ID 목록 가져오기
    if os.path.exists(UCS_PATH):
        df_ucs = pd.read_csv(UCS_PATH)
        norad_col = [c for c in df_ucs.columns if 'norad' in c.lower() or 'cat' in c.lower()]
        if norad_col:
            norad_ids = df_ucs[norad_col[0]].dropna().astype(int).tolist()
            print(f"UCS 기반 위성 {len(norad_ids)}개 대상")
            id_str = ','.join(str(n) for n in norad_ids)
            url = f'https://www.space-track.org/basicspacedata/query/class/gp/NORAD_CAT_ID/{id_str}/format/json'
        else:
            print("NORAD ID 컬럼 없음 → EO/SAR 전체 조회")
            url = 'https://www.space-track.org/basicspacedata/query/class/gp/OBJECT_TYPE/PAYLOAD/format/json'
    else:
        print("UCS 파일 없음 → PAYLOAD 전체 조회")
        url = 'https://www.space-track.org/basicspacedata/query/class/gp/OBJECT_TYPE/PAYLOAD/format/json'

    resp = session.get(url)
    if resp.status_code != 200:
        print(f"TLE 조회 실패: {resp.status_code}")
        return

    tle_data = resp.json()
    with open(TLE_PATH, 'w', encoding='utf-8') as f:
        json.dump(tle_data, f, ensure_ascii=False, indent=2)

    print(f"TLE 업데이트 완료: {len(tle_data)}개 위성 → {TLE_PATH}")
    session.get('https://www.space-track.org/ajaxauth/logout')


# ── 실행 ──────────────────────────────────────────────────
if __name__ == '__main__':
    print(f"=== 데이터 업데이트 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    fetch_gdelt()
    fetch_tle()
    print(f"\n=== 완료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    print("\n이후 파이프라인 실행:")
    print("  python project/02_src/01_filter.py")
    print("  python project/02_src/02_spike_detection.py")
    print("  python project/02_src/03_priority_scoring.py")
    print("  python project/02_src/04_geo_validation.py")
    print("  python project/02_src/05_satellite_scheduling.py")
