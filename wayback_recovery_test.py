"""
wayback_recovery_test.py
----------------------------------------------------------------------
GDELT 사건 URL이 웨이백 머신(Internet Archive)에 얼마나 보존돼 있는지
"회수율"을 시험하는 스크립트.

전체에 돌리기 전에 표본(기본 20개)으로 먼저 확인 → 이 방법이 할 만한지 판단.

사용:
  python wayback_recovery_test.py
  python wayback_recovery_test.py --sample 30   # 표본 수 조정

결과: 표본 중 몇 개가 웨이백에 보존본이 있는지 (회수율 %).
"""

import sys
import time
import argparse
import requests
import pandas as pd

# ── 설정 ─────────────────────────────────────────────────
BASE = "project/01_data"
# SOURCEURL이 있을 만한 파일 후보 (위에서부터 시도)
CANDIDATE_FILES = [
    f"{BASE}/processed/events_filtered.csv",
    f"{BASE}/processed/final_priority_geo.csv",
    f"{BASE}/raw/gdelt_raw.csv",
]
WAYBACK_API = "http://archive.org/wayback/available"
DELAY_SEC = 1.0   # archive.org 예의상 요청 간격
TIMEOUT = 15


def find_url_column(df):
    """SOURCEURL 비슷한 컬럼 찾기"""
    for col in df.columns:
        if col.upper() in ("SOURCEURL", "SOURCE_URL", "URL"):
            return col
    return None


def load_events():
    """URL 컬럼이 있는 첫 번째 파일을 로드"""
    for path in CANDIDATE_FILES:
        try:
            df = pd.read_csv(path)
        except FileNotFoundError:
            continue
        url_col = find_url_column(df)
        if url_col:
            print(f"✓ URL 컬럼 '{url_col}' 발견: {path}")
            return df, url_col, path
        else:
            print(f"  (URL 컬럼 없음: {path})")
    return None, None, None


def check_wayback(url, event_date=None):
    """
    웨이백에 이 URL의 보존본이 있는지 확인.
    event_date(YYYYMMDD)를 주면 그 시점 근처 스냅샷을 우선 탐색.
    반환: (있음 여부, 스냅샷 URL 또는 None, 스냅샷 날짜 또는 None)
    """
    params = {"url": url}
    if event_date:
        params["timestamp"] = event_date  # 예: "20220804"
    try:
        r = requests.get(WAYBACK_API, params=params, timeout=TIMEOUT)
        data = r.json()
        snap = data.get("archived_snapshots", {}).get("closest")
        if snap and snap.get("available"):
            return True, snap.get("url"), snap.get("timestamp")
    except Exception as e:
        return None, f"오류: {e}", None
    return False, None, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=20, help="시험할 표본 수")
    args = parser.parse_args()

    df, url_col, path = load_events()
    if df is None:
        print("\n✗ SOURCEURL 컬럼이 있는 파일을 찾지 못했습니다.")
        print("  CANDIDATE_FILES 경로를 확인하거나, URL이 있는 CSV 경로를 알려주세요.")
        sys.exit(1)

    # 날짜 컬럼 찾기 (있으면 스냅샷 시점 매칭에 사용)
    date_col = "SQLDATE" if "SQLDATE" in df.columns else None

    # URL 있는 행만, 표본 추출
    sub = df[df[url_col].notna()].copy()
    if len(sub) == 0:
        print(f"✗ '{url_col}'에 URL이 하나도 없습니다.")
        sys.exit(1)

    n = min(args.sample, len(sub))
    sample = sub.sample(n=n, random_state=42)
    print(f"\n표본 {n}개로 웨이백 회수율 시험 시작 "
          f"(전체 URL 보유 행: {len(sub)})\n" + "─" * 60)

    found = 0
    dead_in_wayback = 0
    errors = 0
    examples = []

    for i, (_, row) in enumerate(sample.iterrows(), 1):
        url = str(row[url_col]).strip()
        ev_date = None
        if date_col:
            try:
                ev_date = pd.to_datetime(row[date_col]).strftime("%Y%m%d")
            except Exception:
                ev_date = None

        ok, snap_url, snap_ts = check_wayback(url, ev_date)
        if ok is True:
            found += 1
            mark = "✓ 보존됨"
            if len(examples) < 3:
                examples.append((url, snap_url, snap_ts))
        elif ok is False:
            dead_in_wayback += 1
            mark = "✗ 웨이백에도 없음"
        else:
            errors += 1
            mark = f"⚠ {snap_url}"  # 오류 메시지

        print(f"[{i}/{n}] {mark}")
        time.sleep(DELAY_SEC)

    print("─" * 60)
    rate = found / n * 100 if n else 0
    print(f"\n결과:")
    print(f"  보존됨(회수 가능): {found}/{n}  →  회수율 {rate:.0f}%")
    print(f"  웨이백에도 없음:   {dead_in_wayback}/{n}")
    print(f"  조회 오류:        {errors}/{n}")

    if examples:
        print(f"\n회수 가능 예시:")
        for orig, snap, ts in examples:
            print(f"  원본: {orig[:70]}")
            print(f"  보존: {snap}")
            print(f"  시점: {ts}\n")

    print("판단 가이드:")
    print("  회수율 60%+ → 본격 진행할 만함")
    print("  회수율 30~60% → 부분적 보강 가능 (큰 사건 위주로)")
    print("  회수율 30% 미만 → 효과 적음, 다른 방법 고려")


if __name__ == "__main__":
    main()