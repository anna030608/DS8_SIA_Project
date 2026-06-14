"""
08_integrated_comparison.py
----------------------------------------------------------------------
5개 가중치 버전의 통합 비교:
  - F1 성능 (Precision/Recall/F1 + 최적 threshold) — 연속 날짜(±3일) 반영
  - 순위 성능 (각 위기의 '기간 내 최고 순위') — 연속성 반영
  - 사건별 순위표 (기간 내 최고 순위)

저장된 score_* 컬럼 사용 (03/04와 완전 일치).
"""

import pandas as pd
import numpy as np
from datetime import timedelta

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

IMPORTANCE_WEIGHT = {'매우 높음': 3, '높음': 2, '중간~높음': 1}

SCORE_COLS = {
    'num_mentions': 'score_mentions', 'goldstein': 'score_goldstein',
    'avg_tone': 'score_tone', 'geo_distance': 'score_geo', 'zscore': 'score_zscore',
}

WEIGHT_VERSIONS = {
    '① mentions만':   {'geo_distance': 0.0,  'num_mentions': 1.0,  'zscore': 0.0,  'goldstein': 0.0,  'avg_tone': 0.0},
    '② 위치 중심':    {'geo_distance': 0.75, 'num_mentions': 0.25, 'zscore': 0.0,  'goldstein': 0.0,  'avg_tone': 0.0},
    '③ 위치+급증도':  {'geo_distance': 0.75, 'num_mentions': 0.0,  'zscore': 0.25, 'goldstein': 0.0,  'avg_tone': 0.0},
    '④ grid 최적':    {'geo_distance': 0.6,  'num_mentions': 0.0,  'zscore': 0.3,  'goldstein': 0.1,  'avg_tone': 0.0},
    '⑤ 우리 config★': {'geo_distance': 0.45, 'num_mentions': 0.35, 'zscore': 0.1,  'goldstein': 0.05, 'avg_tone': 0.05},
}


def compute_score(df, w):
    return (
        df[SCORE_COLS['num_mentions']] * w['num_mentions'] +
        df[SCORE_COLS['goldstein']]    * w['goldstein']    +
        df[SCORE_COLS['avg_tone']]     * w['avg_tone']     +
        df[SCORE_COLS['geo_distance']] * w['geo_distance'] +
        df[SCORE_COLS['zscore']]       * w['zscore']
    )


def get_crisis_dates(data_start, data_end):
    cd = {}
    for start, end, name, importance in KNOWN_CRISES:
        s = pd.to_datetime(start).date() - timedelta(days=3)
        e = pd.to_datetime(end).date()   + timedelta(days=3)
        for i in range((e - s).days + 1):
            d = s + timedelta(days=i)
            if not (data_start <= d <= data_end):
                continue
            if d not in cd or IMPORTANCE_WEIGHT.get(importance,0) > IMPORTANCE_WEIGHT.get(cd[d][1],0):
                cd[d] = (name, importance)
    return cd


def evaluate(df_scored, crisis_dates, threshold):
    predicted = set(df_scored[df_scored['priority_score'] >= threshold]['SQLDATE'].dt.date)
    actual = set(crisis_dates.keys())
    tp = len(predicted & actual); fp = len(predicted - actual); fn = len(actual - predicted)
    p = tp/(tp+fp) if tp+fp>0 else 0
    r = tp/(tp+fn) if tp+fn>0 else 0
    f1 = 2*p*r/(p+r) if p+r>0 else 0
    return p, r, f1


def best_f1(df, w, crisis_dates):
    df2 = df.copy()
    df2['priority_score'] = compute_score(df, w)
    bf1 = bp = br = 0; bthr = 0.2
    for thr in np.arange(0.05, 1.0, 0.05).round(2):
        p, r, f1 = evaluate(df2, crisis_dates, thr)
        if f1 > bf1:
            bf1, bp, br, bthr = f1, p, r, thr
    return bp, br, bf1, bthr


def period_indices(df, start, end, data_start, data_end):
    s = pd.to_datetime(start).date() - timedelta(days=3)
    e = pd.to_datetime(end).date()   + timedelta(days=3)
    s = max(s, data_start); e = min(e, data_end)
    mask = (df['SQLDATE'].dt.date >= s) & (df['SQLDATE'].dt.date <= e)
    return df[mask].index


def main():
    df = pd.read_csv("project/01_data/processed/final_priority_geo.csv")
    df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

    missing = [c for c in SCORE_COLS.values() if c not in df.columns]
    if missing:
        print(f"✗ 점수 컬럼 누락: {missing}"); return

    data_start = df['SQLDATE'].min().date()
    data_end   = df['SQLDATE'].max().date()
    total = len(df)
    crisis_dates = get_crisis_dates(data_start, data_end)

    # 버전별 전체 순위 (1=최고)
    rank_by_version = {v: compute_score(df, w).rank(ascending=False, method='min').astype(int)
                       for v, w in WEIGHT_VERSIONS.items()}

    # ── [표 1] 통합 성능 비교 (F1 + 순위 요약) ───────────
    print(f"{'='*90}")
    print(f"[표 1] 가중치 5개 버전 통합 비교 (전체 {total}건, 정답 {len(KNOWN_CRISES)}건)")
    print(f"{'='*90}")
    header = f"{'버전':<16} {'geo':>5} {'men':>5} {'z':>5} {'gold':>5} {'tone':>5} | {'Prec':>6} {'Recall':>6} {'F1':>6} {'thr':>5} | {'≤10':>4} {'≤50':>4} {'≤100':>5}"
    print(header)
    print('-' * len(header))

    # 각 위기의 '기간 내 최고 순위' (버전별)
    period_best = {v: [] for v in WEIGHT_VERSIONS}  # 위기별 최고순위 리스트
    for start, end, name, imp in KNOWN_CRISES:
        idxs = period_indices(df, start, end, data_start, data_end)
        if len(idxs) == 0:
            for v in WEIGHT_VERSIONS:
                period_best[v].append(None)
            continue
        for v in WEIGHT_VERSIONS:
            period_best[v].append(int(rank_by_version[v].loc[idxs].min()))

    summary = {}
    for v, w in WEIGHT_VERSIONS.items():
        bp, br, bf1, bthr = best_f1(df, w, crisis_dates)
        ranks = [x for x in period_best[v] if x is not None]
        t10 = sum(1 for x in ranks if x <= 10)
        t50 = sum(1 for x in ranks if x <= 50)
        t100 = sum(1 for x in ranks if x <= 100)
        summary[v] = (bp, br, bf1, bthr, t10, t50, t100)
        print(f"{v:<16} {w['geo_distance']:>5} {w['num_mentions']:>5} {w['zscore']:>5} "
              f"{w['goldstein']:>5} {w['avg_tone']:>5} | {bp:>6.3f} {br:>6.3f} {bf1:>6.3f} {bthr:>5} | "
              f"{t10:>4} {t50:>4} {t100:>5}")
    print()
    print("※ Prec/Recall/F1/thr: 연속 날짜(±3일) 반영. ≤N: 각 위기 '기간 내 최고 순위'가 N위 이내인 개수")
    print()

    # ── [표 2] 사건별 기간 내 최고 순위 ──────────────────
    print(f"{'='*90}")
    print(f"[표 2] 사건별 '기간 내 최고 순위' (연속성 반영)")
    print(f"{'='*90}")
    rows = []
    for i, (start, end, name, imp) in enumerate(KNOWN_CRISES):
        idxs = period_indices(df, start, end, data_start, data_end)
        row = {'사건': name, '중요도': imp, '날짜': start}
        if len(idxs) == 0:
            row['mentions'] = None
            for v in WEIGHT_VERSIONS:
                row[v] = None
        else:
            row['mentions'] = int(df.loc[idxs, 'NumMentions'].max())
            for v in WEIGHT_VERSIONS:
                row[v] = period_best[v][i]
        rows.append(row)
    result = pd.DataFrame(rows)

    pd.set_option('display.unicode.east_asian_width', True)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 240)
    print(result.sort_values('mentions', ascending=False, na_position='last').to_string(index=False))
    print()

    result.to_csv("project/01_data/processed/integrated_comparison.csv", index=False, encoding='utf-8-sig')

    # 요약도 CSV
    sum_rows = []
    for v, w in WEIGHT_VERSIONS.items():
        bp, br, bf1, bthr, t10, t50, t100 = summary[v]
        sum_rows.append({'버전': v, 'geo': w['geo_distance'], 'mentions': w['num_mentions'],
                         'zscore': w['zscore'], 'goldstein': w['goldstein'], 'tone': w['avg_tone'],
                         'precision': round(bp,3), 'recall': round(br,3), 'f1': round(bf1,3),
                         'threshold': bthr, 'top10': t10, 'top50': t50, 'top100': t100})
    pd.DataFrame(sum_rows).to_csv("project/01_data/processed/integrated_summary.csv",
                                  index=False, encoding='utf-8-sig')
    print("저장: integrated_comparison.csv (사건별), integrated_summary.csv (버전별 요약)")
    print(f"{'='*90}")


if __name__ == '__main__':
    main()