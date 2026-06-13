import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import timedelta
from itertools import product
import yaml

# ── config 로드 ───────────────────────────────────────────
with open("config.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# ── 알려진 위기 이벤트 정답 레이블 ───────────────────────
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

# 검증할 점수 컬럼 (03/04에서 저장된 값 — 재계산 없이 그대로 사용)
SCORE_COLS = {
    'num_mentions': 'score_mentions',
    'goldstein':    'score_goldstein',
    'avg_tone':     'score_tone',
    'geo_distance': 'score_geo',     # 이미 Level2 패널티 반영됨
    'zscore':       'score_zscore',
}


def get_crisis_dates(data_start, data_end):
    crisis_dates = {}
    for start, end, name, importance in KNOWN_CRISES:
        s = pd.to_datetime(start).date() - timedelta(days=3)  # GDELT 보고지연 대응 앞 3일
        e = pd.to_datetime(end).date()   + timedelta(days=3)  # 뒤 3일
        for i in range((e - s).days + 1):
            d = s + timedelta(days=i)
            if not (data_start <= d <= data_end):
                continue
            if d not in crisis_dates:
                crisis_dates[d] = (name, importance)
            elif IMPORTANCE_WEIGHT.get(importance, 0) > IMPORTANCE_WEIGHT.get(crisis_dates[d][1], 0):
                crisis_dates[d] = (name, importance)
    return crisis_dates


def evaluate(df_scores, crisis_dates, threshold):
    predicted = set(df_scores[df_scores['priority_score'] >= threshold]['SQLDATE'].dt.date)
    actual    = set(crisis_dates.keys())
    tp = len(predicted & actual)
    fp = len(predicted - actual)
    fn = len(actual - predicted)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    return precision, recall, f1, tp, fp, fn


def compute_score(df_raw, w_mentions, w_goldstein, w_tone, w_geo, w_zscore):
    """저장된 score_* 컬럼을 가중치로 조합 (재계산 없음 → 03/04와 완전 일치)."""
    df = df_raw.copy()
    df['priority_score'] = (
        df[SCORE_COLS['num_mentions']] * w_mentions  +
        df[SCORE_COLS['goldstein']]    * w_goldstein +
        df[SCORE_COLS['avg_tone']]     * w_tone      +
        df[SCORE_COLS['geo_distance']] * w_geo       +
        df[SCORE_COLS['zscore']]       * w_zscore
    )
    return df


def grid_search(df_raw, crisis_dates):
    step = 0.1
    weights = np.arange(0, 1 + step, step).round(1)
    best = {'f1': 0, 'w': None, 'p': 0, 'r': 0, 'thr': 0.3}
    results = []
    total = 0

    print("Grid Search 진행 중... (5개 가중치 조합 탐색)")
    # mentions, goldstein, tone, geo, zscore 5개 가중치, 합=1.0
    for wm, wg, wt, wgeo, wz in product(weights, repeat=5):
        if round(wm + wg + wt + wgeo + wz, 1) != 1.0:
            continue
        total += 1
        df_scored = compute_score(df_raw, wm, wg, wt, wgeo, wz)
        best_f1 = best_p = best_r = 0
        best_thr = 0.3
        for thr in np.arange(0.1, 1.0, 0.05).round(2):
            p, r, f1, _, _, _ = evaluate(df_scored, crisis_dates, thr)
            if f1 > best_f1:
                best_f1, best_p, best_r, best_thr = f1, p, r, thr
        results.append({
            'w_mentions': wm, 'w_goldstein': wg, 'w_tone': wt,
            'w_geo': wgeo, 'w_zscore': wz,
            'f1': best_f1, 'precision': best_p,
            'recall': best_r, 'best_threshold': best_thr
        })
        if best_f1 > best['f1']:
            best = {'f1': best_f1, 'w': (wm, wg, wt, wgeo, wz),
                    'p': best_p, 'r': best_r, 'thr': best_thr}

    print(f"탐색 완료: {total}개 조합")
    return best, pd.DataFrame(results)


def main():
    df = pd.read_csv("project/01_data/processed/final_priority_geo.csv")
    df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

    # 점수 컬럼 존재 확인
    missing = [c for c in SCORE_COLS.values() if c not in df.columns]
    if missing:
        print(f"✗ 필요한 점수 컬럼 누락: {missing}")
        print("  03_priority_scoring.py / 04_geo_validation.py 를 먼저 실행하세요.")
        return

    data_start = df['SQLDATE'].min().date()
    data_end   = df['SQLDATE'].max().date()
    crisis_dates = get_crisis_dates(data_start, data_end)

    print(f"{'='*60}")
    print(f"Priority Score 검증 보고서 (최신 로직: zscore + Level2 패널티 반영)")
    print(f"{'='*60}")
    print(f"전체 이벤트: {len(df)}행")
    print(f"데이터 기간: {data_start} ~ {data_end}")
    print(f"유효 위기 날짜(±3일 포함): {len(crisis_dates)}일")
    print(f"정답 위기 이벤트: {len(KNOWN_CRISES)}건")
    print()

    # ── 현재 가중치 성능 (config 기준) ───────────────────
    w = config['priority_score']['weights']
    print(f"{'─'*50}")
    print(f"현재 config 가중치:")
    print(f"  mentions={w['num_mentions']} goldstein={w['goldstein']} "
          f"tone={w['avg_tone']} geo={w['geo_distance']} zscore={w['zscore']}")
    print(f"{'─'*50}")
    df_cur = compute_score(df, w['num_mentions'], w['goldstein'],
                           w['avg_tone'], w['geo_distance'], w['zscore'])
    best_f1_cur, best_result_cur = 0, None
    for thr in np.arange(0.05, 1.0, 0.05).round(2):
        p, r, f1, tp, fp, fn = evaluate(df_cur, crisis_dates, thr)
        if f1 > best_f1_cur:
            best_f1_cur = f1
            best_result_cur = (thr, p, r, f1, tp, fp, fn)
    thr, p, r, f1, tp, fp, fn = best_result_cur
    print(f"최적 Threshold: {thr} | Precision: {p:.3f} | Recall: {r:.3f} | F1: {f1:.3f}")
    print(f"TP: {tp} | FP: {fp} | FN: {fn}")
    print()

    print("Threshold별 성능 (현재 가중치):")
    print('{:>10} | {:>9} | {:>8} | {:>8} | {:>4} | {:>4} | {:>4}'.format(
        'Threshold', 'Precision', 'Recall', 'F1', 'TP', 'FP', 'FN'))
    print('-' * 65)
    for t in np.arange(0.05, 0.50, 0.05).round(2):
        p, r, f1, tp, fp, fn = evaluate(df_cur, crisis_dates, t)
        print('{:>10.2f} | {:>9.3f} | {:>8.3f} | {:>8.3f} | {:>4} | {:>4} | {:>4}'.format(
            t, p, r, f1, tp, fp, fn))
    print()

    # ── Grid Search ───────────────────────────────────────
    best, df_results = grid_search(df, crisis_dates)
    wm, wg, wt, wgeo, wz = best['w']

    print()
    print(f"{'─'*50}")
    print("최적 가중치 조합 (F1 기준)")
    print(f"{'─'*50}")
    print(f"  num_mentions : {wm}")
    print(f"  goldstein    : {wg}")
    print(f"  avg_tone     : {wt}")
    print(f"  geo_distance : {wgeo}")
    print(f"  zscore       : {wz}")
    print(f"  Precision    : {best['p']:.3f}")
    print(f"  Recall       : {best['r']:.3f}")
    print(f"  F1 Score     : {best['f1']:.3f}")
    print(f"  Threshold    : {best['thr']}")
    print()

    print(f"{'─'*50}")
    print("F1 상위 10개 가중치 조합")
    print(f"{'─'*50}")
    top10 = df_results.nlargest(10, 'f1')
    print(top10[['w_mentions', 'w_goldstein', 'w_tone', 'w_geo', 'w_zscore',
                 'precision', 'recall', 'f1', 'best_threshold']].to_string(index=False))
    print()

    # 이벤트별 탐지 결과 (현재 config 가중치 기준)
    detected = set(df_cur[df_cur['priority_score'] >= best_result_cur[0]]['SQLDATE'].dt.date)
    print(f"{'─'*50}")
    print(f"현재 가중치 이벤트별 탐지 (threshold={best_result_cur[0]})")
    print(f"{'─'*50}")
    for start, end, name, importance in KNOWN_CRISES:
        s = pd.to_datetime(start).date()
        e = pd.to_datetime(end).date()
        period = [s + timedelta(days=i) for i in range((e - s).days + 1)
                  if data_start <= s + timedelta(days=i) <= data_end]
        if not period:
            continue
        status = "✅ 탐지" if any(d in detected for d in period) else "❌ 미탐지"
        print(f"{status} [{importance:6}] {start} ~ {end} | {name}")

    df_results.to_csv('project/01_data/processed/gridsearch_results.csv', index=False)
    print()
    print("결과 저장: project/01_data/processed/gridsearch_results.csv")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()