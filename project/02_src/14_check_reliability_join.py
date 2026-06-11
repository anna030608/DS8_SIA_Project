"""
14_check_reliability_join.py  (4단계 준비: 신뢰도 결과 ↔ 대시보드 사건 매칭 확인)
----------------------------------------------------------------------
event_reliability.csv 의 event_key 와, 대시보드가 읽는 final_priority_geo.csv 의
사건이 같은 키로 매칭되는지 먼저 확인한다. (매칭 안 되면 4단계 표시가 전부
"정보 없음"이 되므로, 코드 넣기 전에 검증.)
"""

import os
import pandas as pd

DASH_CSV = "project/01_data/processed/final_priority_geo.csv"
REL_CSV = "project/01_data/processed/event_reliability.csv"


def make_key(row):
    """배치 스크립트와 동일한 방식으로 키 생성"""
    if "GLOBALEVENTID" in row and pd.notna(row.get("GLOBALEVENTID")):
        return str(int(row["GLOBALEVENTID"]))
    return f"{row['SQLDATE']}_{row['ActionGeo_Lat']}_{row['ActionGeo_Long']}_{row['EventCode']}"


def main():
    dash = pd.read_csv(DASH_CSV)
    rel = pd.read_csv(REL_CSV, dtype={"event_key": str})

    print(f"대시보드 사건(final_priority_geo): {len(dash)}건")
    print(f"신뢰도 결과(event_reliability):   {len(rel)}건")
    print(f"대시보드 컬럼: {[c for c in dash.columns if c in ('GLOBALEVENTID','SQLDATE','ActionGeo_Lat','ActionGeo_Long','EventCode')]}")
    print("=" * 60)

    # 대시보드 쪽 키 생성
    dash = dash.copy()
    try:
        dash["_key"] = dash.apply(make_key, axis=1)
    except Exception as e:
        print(f"✗ 대시보드 키 생성 실패: {e}")
        print("  필요한 컬럼(SQLDATE, ActionGeo_Lat, ActionGeo_Long, EventCode)이 있는지 확인")
        return

    rel_keys = set(rel["event_key"].astype(str))
    dash_keys = set(dash["_key"].astype(str))

    matched = dash_keys & rel_keys
    print(f"매칭된 사건: {len(matched)} / 대시보드 {len(dash_keys)} "
          f"({len(matched)/len(dash_keys)*100:.0f}%)")
    print(f"신뢰도 결과 중 대시보드와 매칭: {len(matched)} / {len(rel_keys)}")

    # 샘플로 키 형태 비교 (불일치 진단용)
    print("\n키 형태 샘플:")
    print(f"  대시보드: {list(dash_keys)[:2]}")
    print(f"  신뢰도:   {list(rel_keys)[:2]}")

    if len(matched) / max(len(dash_keys), 1) > 0.8:
        print("\n✓ 매칭 양호 → 4단계 표시 코드로 진행 가능")
    else:
        print("\n⚠ 매칭률 낮음 → 키 생성 방식이 양쪽에서 다를 수 있음")
        print("  (날짜 포맷, 좌표 소수점 자리, GLOBALEVENTID 유무 등 확인 필요)")


if __name__ == "__main__":
    main()