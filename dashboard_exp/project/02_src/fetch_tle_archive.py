import requests
import json
import time
import os
import pandas as pd
from datetime import datetime, timedelta

# ── 설정 ─────────────────────────────────────────────────
BASE_DIR    = os.path.join(os.path.dirname(__file__), '..', '..')
ST_KEY_PATH = os.path.join(BASE_DIR, 'spacetrack_key.json')
UCS_PATH    = os.path.join(BASE_DIR, 'project/01_data/raw/ucs_eo_sar_filtered.csv')
SPIKE_PATH  = os.path.join(BASE_DIR, 'project/01_data/processed/spike_events.csv')
ARCHIVE_DIR = os.path.join(BASE_DIR, 'project/01_data/raw/tle_archive')

# 1일차: 2014~2019 / 2일차: 2020~2026
# 실행 시 DAY 변수를 1 또는 2로 설정
DAY = 1  # ← 1일차면 1, 2일차면 2로 변경

YEAR_RANGES = {
    1: ('2014-01', '2019-12'),
    2: ('2020-01', '2026-12'),
}

# ── 준비 ─────────────────────────────────────────────────
os.makedirs(ARCHIVE_DIR, exist_ok=True)

with open(ST_KEY_PATH, encoding='utf-8') as f:
    st_cred = json.load(f)

session = requests.Session()
resp = session.post('https://www.space-track.org/ajaxauth/login',
                    data={'identity': st_cred['username'], 'password': st_cred['password']})
if resp.status_code != 200:
    print(f"로그인 실패: {resp.status_code}")
    exit()
print("Space-Track 로그인 성공")

# UCS NORAD ID
ucs_df   = pd.read_csv(UCS_PATH)
norad_col = [c for c in ucs_df.columns if 'norad' in c.lower() or 'number' in c.lower()][0]
norad_ids = ucs_df[norad_col].dropna().astype(int).tolist()
print(f"대상 위성: {len(norad_ids)}개")

# spike 월 목록
spike_df = pd.read_csv(SPIKE_PATH)
all_months = sorted(spike_df['SQLDATE'].str[:7].unique())

start_ym, end_ym = YEAR_RANGES[DAY]
months = [m for m in all_months if start_ym <= m <= end_ym]
print(f"\n{DAY}일차 수집 대상: {len(months)}개월 ({months[0]} ~ {months[-1]})")

# 이미 수집된 월 제외
months_todo = [m for m in months
               if not os.path.exists(os.path.join(ARCHIVE_DIR, f'tle_{m}.json'))]
print(f"이미 수집된 월 제외 후: {len(months_todo)}개월")

# ── 배치 수집 함수 ────────────────────────────────────────
BATCH_SIZE = 100

def fetch_tle_history_batch(norad_batch, month_str):
    ids        = ','.join(str(n) for n in norad_batch)
    month_dt   = datetime.strptime(month_str + '-15', '%Y-%m-%d')
    date_start = (month_dt - timedelta(days=15)).strftime('%Y-%m-%d')
    date_end   = (month_dt + timedelta(days=15)).strftime('%Y-%m-%d')
    url = (
        f'https://www.space-track.org/basicspacedata/query'
        f'/class/gp_history/NORAD_CAT_ID/{ids}'
        f'/EPOCH/{date_start}--{date_end}'
        f'/orderby/EPOCH%20desc/limit/1/format/json'
    )
    resp = session.get(url)
    if resp.status_code != 200:
        print(f"  API 오류: {resp.status_code}")
        return []
    data = resp.json()
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []

# ── 월별 수집 실행 ────────────────────────────────────────
total_calls = 0
for idx, month in enumerate(months_todo):
    print(f"\n[{idx+1}/{len(months_todo)}] {month} 수집 중...")
    month_tle = []

    for i in range(0, len(norad_ids), BATCH_SIZE):
        batch  = norad_ids[i:i+BATCH_SIZE]
        result = fetch_tle_history_batch(batch, month)
        month_tle.extend(result)
        total_calls += 1
        time.sleep(2)

        # 300호출 근접 시 경고
        if total_calls >= 280:
            print(f"\n⚠ API 호출 {total_calls}회 도달 — 오늘 중단 권장")
            print(f"  내일 DAY={DAY} 그대로 재실행하면 이어서 수집됩니다.")
            with open(os.path.join(ARCHIVE_DIR, f'tle_{month}.json'), 'w') as f:
                json.dump(month_tle, f)
            session.get('https://www.space-track.org/ajaxauth/logout')
            exit()

    # 월별 저장
    save_path = os.path.join(ARCHIVE_DIR, f'tle_{month}.json')
    with open(save_path, 'w') as f:
        json.dump(month_tle, f)
    print(f"  저장 완료: {len(month_tle)}개 위성 → {save_path}")

print(f"\n{'='*50}")
print(f"{DAY}일차 완료: {len(months_todo)}개월 수집")
print(f"총 API 호출: {total_calls}회")
print(f"저장 위치: {ARCHIVE_DIR}/")

if DAY == 1:
    print(f"\n내일 DAY=2로 변경 후 재실행하세요.")
else:
    print(f"\n전체 아카이브 수집 완료!")

session.get('https://www.space-track.org/ajaxauth/logout')