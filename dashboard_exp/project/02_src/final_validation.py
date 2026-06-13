import pandas as pd
import numpy as np
import yaml
import os
from datetime import timedelta

config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.yaml')
with open(config_path, encoding="utf-8") as f:
    config = yaml.safe_load(f)

# ── final_priority_geo.csv 사용 (패널티 적용 후) ─────────
df = pd.read_csv("project/01_data/processed/final_priority_geo.csv")
df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

print(f"데이터: {len(df)}행 (패널티 적용 후 기준)")

# ── 가중치 조합 정의 ──────────────────────────────────────
WEIGHT_SETS = {
    '현재':       {'geo': 0.75, 'mentions': 0.25, 'goldstein': 0.00, 'tone': 0.00, 'zscore': 0.00},
    'A_균형형':   {'geo': 0.50, 'mentions': 0.30, 'goldstein': 0.10, 'tone': 0.10, 'zscore': 0.00},
    'B_Z추가':    {'geo': 0.60, 'mentions': 0.25, 'goldstein': 0.05, 'tone': 0.05, 'zscore': 0.05},
    'C_기사량':   {'geo': 0.40, 'mentions': 0.40, 'goldstein': 0.10, 'tone': 0.10, 'zscore': 0.00},
    'C_zscore':   {'geo': 0.40, 'mentions': 0.00, 'goldstein': 0.10, 'tone': 0.10, 'zscore': 0.40},
    'D_지리+Z':   {'geo': 0.70, 'mentions': 0.15, 'goldstein': 0.05, 'tone': 0.05, 'zscore': 0.05},
    'E_BZ강화':   {'geo': 0.55, 'mentions': 0.25, 'goldstein': 0.05, 'tone': 0.05, 'zscore': 0.10},
    'F_균형+Z':   {'geo': 0.45, 'mentions': 0.35, 'goldstein': 0.05, 'tone': 0.05, 'zscore': 0.10},
    'G_tone강화': {'geo': 0.50, 'mentions': 0.25, 'goldstein': 0.05, 'tone': 0.15, 'zscore': 0.05},
    'H_gold강화': {'geo': 0.50, 'mentions': 0.25, 'goldstein': 0.15, 'tone': 0.05, 'zscore': 0.05},
    'I_전균형':   {'geo': 0.40, 'mentions': 0.30, 'goldstein': 0.10, 'tone': 0.10, 'zscore': 0.10},
    'J_geo+Z':    {'geo': 0.75, 'mentions': 0.00, 'goldstein': 0.00, 'tone': 0.00, 'zscore': 0.25},
}

# ── 가중치 조합별 priority_score 재계산 ──────────────────
for name, w in WEIGHT_SETS.items():
    df[f'score_{name}'] = (
        df['score_geo']       * w['geo'] +
        df['score_mentions']  * w['mentions'] +
        df['score_goldstein'] * w['goldstein'] +
        df['score_tone']      * w['tone'] +
        df['score_zscore']    * w['zscore']
    )

# ── 이벤트 리스트 ─────────────────────────────────────────
KNOWN_CRISES = [
    ('2025-12-29', '2025-12-30', '중국 대만 주변 포위형 군사활동',   '매우 높음'),
    ('2025-04-01', '2025-04-02', 'Strait Thunder-2025A',            '매우 높음'),
    ('2025-02-27', '2025-02-27', '대만 해안 실사격 훈련',            '매우 높음'),
    ('2024-10-14', '2024-10-14', 'Joint Sword-2024B',               '매우 높음'),
    ('2024-05-23', '2024-05-24', 'Joint Sword-2024A',               '매우 높음'),
    ('2024-01-13', '2024-01-13', '라이칭더 총통 당선',                '높음'),
    ('2023-08-12', '2023-08-18', '라이칭더 미국 경유 방문',           '높음'),
    ('2023-04-05', '2023-04-10', 'Shandong 작전·Joint Sword',       '매우 높음'),
    ('2022-08-31', '2022-08-31', '금문도 드론 격추',                 '높음'),
    ('2022-08-04', '2022-08-10', '대만 포위 실사격 훈련',            '매우 높음'),
    ('2022-08-02', '2022-08-03', 'Pelosi 대만 방문',                '매우 높음'),
    ('2022-07-30', '2022-07-30', 'Pelosi 방문 직전 군사훈련',        '매우 높음'),
    ('2021-10-01', '2021-10-04', '역대 최대 ADIZ 진입',             '매우 높음'),
    ('2021-01-19', '2021-01-19', '대만 군사 방어 훈련',              '높음'),
    ('2020-12-31', '2020-12-31', '미국 대만해협 통과',               '중간~높음'),
    ('2020-09-17', '2020-09-19', '미국 국무차관 대만 방문',           '높음'),
    ('2018-04-18', '2018-04-18', '대만해협 실사격 훈련',             '높음'),
]

IMPORTANCE_WEIGHT = {'매우 높음': 3, '높음': 2, '중간~높음': 1}
BUFFER_DAYS = 1

data_start = df['SQLDATE'].min().date()
data_end   = df['SQLDATE'].max().date()
crisis_dates = {}
for start, end, name, importance in KNOWN_CRISES:
    s = pd.to_datetime(start).date() - timedelta(days=BUFFER_DAYS)
    e = pd.to_datetime(end).date()   + timedelta(days=BUFFER_DAYS)
    for i in range((e - s).days + 1):
        d = s + timedelta(days=i)
        if not (data_start <= d <= data_end):
            continue
        if d not in crisis_dates:
            crisis_dates[d] = (name, importance)
        else:
            if IMPORTANCE_WEIGHT.get(importance, 0) > IMPORTANCE_WEIGHT.get(crisis_dates[d][1], 0):
                crisis_dates[d] = (name, importance)
actual = set(crisis_dates.keys())

# ── Recall/Precision/F1 비교 ─────────────────────────────
print()
print("=" * 90)
print(f"Recall / Precision / F1 — final_priority_geo.csv 기준 (패널티 0.5 적용 후)")
print(f"버퍼 ±{BUFFER_DAYS}일, 위기 날짜: {len(actual)}일")
print("=" * 90)
print(f"{'방식':<14} {'Precision':>10} {'Recall':>8} {'F1':>8} {'TP':>5} {'FP':>5} {'FN':>5} {'Threshold':>10}")
print("-" * 80)

results = []
for name in WEIGHT_SETS:
    col = f'score_{name}'
    best_f1 = best_p = best_r = 0
    best_thr = best_tp = best_fp = best_fn = 0
    for thr in np.arange(0.00, 1.0, 0.05).round(2):
        predicted = set(df[df[col] >= thr]['SQLDATE'].dt.date)
        tp = len(predicted & actual)
        fp = len(predicted - actual)
        fn = len(actual - predicted)
        p  = tp / (tp + fp) if (tp + fp) > 0 else 0
        r  = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
        if f1 > best_f1:
            best_f1, best_p, best_r = f1, p, r
            best_thr, best_tp, best_fp, best_fn = thr, tp, fp, fn
    print(f"{name:<14} {best_p:>10.3f} {best_r:>8.3f} {best_f1:>8.3f} {best_tp:>5} {best_fp:>5} {best_fn:>5} {best_thr:>10.2f}")
    results.append({
        'name': name, 'precision': best_p, 'recall': best_r,
        'f1': best_f1, 'tp': best_tp, 'fp': best_fp, 'fn': best_fn,
        'threshold': best_thr
    })

df_results = pd.DataFrame(results)
best_f1_row = df_results.loc[df_results['f1'].idxmax()]
best_r_row  = df_results.loc[df_results['recall'].idxmax()]
print()
print(f"F1 최고:     {best_f1_row['name']} — P={best_f1_row['precision']:.3f} / R={best_f1_row['recall']:.3f} / F1={best_f1_row['f1']:.3f} / Thr={best_f1_row['threshold']:.2f}")
print(f"Recall 최고: {best_r_row['name']} — P={best_r_row['precision']:.3f} / R={best_r_row['recall']:.3f} / F1={best_r_row['f1']:.3f} / Thr={best_r_row['threshold']:.2f}")

df_results.to_csv("project/01_data/processed/final_validation_results.csv", index=False)
print(f"\n저장 완료: final_validation_results.csv")
