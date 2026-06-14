"""
07_rank_comparison.py
----------------------------------------------------------------------
정답 위기 사건이 가중치 버전별로 '전체 몇 위'에 오는지 비교.

- 대표 행: 각 위기의 날짜 범위(±3일) 안에서 NumMentions 최대인 사건 행 (고정)
- 4개 가중치 버전으로 각각 전체 점수 → 순위 계산 → 대표 행 순위 추출
- 결과를 CSV로 저장 (발표용 표/이미지 재료)

저장된 score_* 컬럼을 사용 (03/04와 완전 일치, 재계산 없음).
"""

import pandas as pd
import numpy as np
from datetime import timedelta

# ── 정답 위기 (06_validation.py와 동일) ──────────────────
KNOWN_CRISES = [
    ('2025-12-29', '2025-12-30', '중국 대만 주변 포위형 군사활동',      '매우 높음'),
    ('2025-04-01', '2025-04-02', 'Strait Thunder-2025A',               '매우 높음'),
    ('2025-02-27', '2025-02-27', '대만 해안 실사격 훈련',               '매우 높음'),
    ('2024-10-14', '2024-10-14', 'Joint Sword-2024B',                  '매우 높음'),
    ('2024-05-23', '2024-05-24', 'Joint Sword-2024A',                  '매우 높음'),
    ('2024-01-13', '2024-01-13', '라이칭더 총통 당선',                   '높음'),
    ('2023-08-12', '2023-08-18', '라이칭더 미국 경유 방문',              '높음'),
    ('2023-04-05', '2023-04-10', 'Shandong 대만 동부 작전·Joint Sword', '매우 높음'),
    ('2022-08-31', '2022-08-31', '금문도 드론 격추',                    '높음'),
    ('2022-08-04', '2022-08-10', '대만 포위 실사격 훈련',               '매우 높음'),
    ('2022-08-02', '2022-08-03', 'Pelosi 대만 방문',                   '매우 높음'),
    ('2022-07-30', '2022-07-30', 'Pelosi 방문 직전 군사훈련',           '매우 높음'),
    ('2021-10-01', '2021-10-04', '역대 최대 ADIZ 진입',                '매우 높음'),
    ('2021-01-19', '2021-01-19', '대만 군사 방어 훈련',                 '높음'),
    ('2020-12-31', '2020-12-31', '미국 대만해협 통과',                  '중간~높음'),
    ('2020-09-17', '2020-09-19', '미국 국무차관 대만 방문',              '높음'),
    ('2020-08-09', '2020-08-12', '미국 보건장관 대만 방문',              '높음'),
    ('2019-03-31', '2019-03-31', '대만해협 중간선 침범',                '매우 높음'),
    ('2018-04-18', '2018-04-18', '대만해협 실사격 훈련',                '높음'),
    ('2016-05-20', '2016-05-20', '차이잉원 취임',                       '높음'),
]

SCORE_COLS = {
    'num_mentions': 'score_mentions',
    'goldstein':    'score_goldstein',
    'avg_tone':     'score_tone',
    'geo_distance': 'score_geo',
    'zscore':       'score_zscore',
}

# ── 비교할 가중치 버전 4개 [mentions, goldstein, tone, geo, zscore] ──
WEIGHT_VERSIONS = {
    '① mentions만':   {'num_mentions': 1.0, 'goldstein': 0.0, 'avg_tone': 0.0, 'geo_distance': 0.0,  'zscore': 0.0},
    '② 위치 중심':    {'num_mentions': 0.25,'goldstein': 0.0, 'avg_tone': 0.0, 'geo_distance': 0.75, 'zscore': 0.0},
    '③ 위치+급증도':  {'num_mentions': 0.0, 'goldstein': 0.0, 'avg_tone': 0.0, 'geo_distance': 0.75, 'zscore': 0.25},
    '④ 최종★':        {'num_mentions': 0.35,'goldstein': 0.05,'avg_tone': 0.05,'geo_distance': 0.45, 'zscore': 0.1},
}


def compute_score(df, w):
    s = (
        df[SCORE_COLS['num_mentions']] * w['num_mentions'] +
        df[SCORE_COLS['goldstein']]    * w['goldstein']    +
        df[SCORE_COLS['avg_tone']]     * w['avg_tone']     +
        df[SCORE_COLS['geo_distance']] * w['geo_distance'] +
        df[SCORE_COLS['zscore']]       * w['zscore']
    )
    return s


def find_representative_row(df, start, end, data_start, data_end):
    """위기 날짜 범위(±3일) 안에서 NumMentions 최대 행의 인덱스 반환 (고정 대표)."""
    s = pd.to_datetime(start).date() - timedelta(days=3)
    e = pd.to_datetime(end).date()   + timedelta(days=3)
    s = max(s, data_start)
    e = min(e, data_end)
    mask = (df['SQLDATE'].dt.date >= s) & (df['SQLDATE'].dt.date <= e)
    sub = df[mask]
    if len(sub) == 0:
        return None
    return sub['NumMentions'].idxmax()  # NumMentions 최대 행 (가중치와 무관 → 고정)


def main():
    df = pd.read_csv("project/01_data/processed/final_priority_geo.csv")
    df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

    missing = [c for c in SCORE_COLS.values() if c not in df.columns]
    if missing:
        print(f"✗ 점수 컬럼 누락: {missing}")
        return

    data_start = df['SQLDATE'].min().date()
    data_end   = df['SQLDATE'].max().date()
    total_events = len(df)

    # 각 버전별 전체 순위 미리 계산 (rank: 1=점수 최고)
    rank_by_version = {}
    for vname, w in WEIGHT_VERSIONS.items():
        scores = compute_score(df, w)
        # 내림차순 순위 (점수 높을수록 1위)
        rank_by_version[vname] = scores.rank(ascending=False, method='min').astype(int)

    # 각 정답 사건의 대표 행 → 버전별 순위
    rows = []
    for start, end, name, importance in KNOWN_CRISES:
        idx = find_representative_row(df, start, end, data_start, data_end)
        if idx is None:
            # 데이터 범위 밖 → 표시만
            row = {'사건': name, '중요도': importance, '날짜': start,
                   'geo': None, 'goldstein': None, 'mentions': None}
            for vname in WEIGHT_VERSIONS:
                row[vname] = None
            rows.append(row)
            continue

        r = df.loc[idx]
        row = {
            '사건': name,
            '중요도': importance,
            '날짜': start,
            'geo': round(float(r['score_geo']), 2),
            'goldstein': round(float(r['GoldsteinScale']), 1) if 'GoldsteinScale' in r else None,
            'mentions': int(r['NumMentions']),
        }
        for vname in WEIGHT_VERSIONS:
            row[vname] = int(rank_by_version[vname].loc[idx])
        rows.append(row)

    result = pd.DataFrame(rows)

    # 출력
    print(f"{'='*70}")
    print(f"정답 사건 순위 비교 — 가중치 4개 버전 (전체 {total_events}건)")
    print(f"{'='*70}")
    print(f"대표 행 기준: 각 위기 날짜 ±3일 내 NumMentions 최대 사건")
    print()
    pd.set_option('display.unicode.east_asian_width', True)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 200)
    print(result.to_string(index=False))
    print()

    # 버전별 '상위 N위 안에 든 정답 사건 수' 요약
    print(f"{'─'*50}")
    print("버전별 요약 (정답 사건이 상위권에 든 개수)")
    print(f"{'─'*50}")
    valid = result.dropna(subset=list(WEIGHT_VERSIONS.keys()))
    for topn in (10, 30, 50):
        line = f"상위 {topn:>3}위 이내: "
        for vname in WEIGHT_VERSIONS:
            cnt = (valid[vname] <= topn).sum()
            line += f"{vname}={cnt}  "
        print(line)
    print()

    result.to_csv("project/01_data/processed/rank_comparison.csv", index=False, encoding='utf-8-sig')
    print("저장: project/01_data/processed/rank_comparison.csv")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()