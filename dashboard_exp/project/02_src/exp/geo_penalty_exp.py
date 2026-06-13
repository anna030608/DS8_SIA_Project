import pandas as pd
import numpy as np
import yaml
import os
from shapely.geometry import Point, LineString
import geopy.distance
from datetime import timedelta

config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.yaml')
with open(config_path, encoding="utf-8") as f:
    config = yaml.safe_load(f)

df = pd.read_csv("project/01_data/processed/events_filtered.csv")
df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

tone_threshold = config['priority_score']['avg_tone_threshold']
geo_bins       = config['priority_score']['geo_distance_bins']
weights        = config['priority_score']['weights']

# ── 공통 점수 계산 ────────────────────────────────────────
def minmax(series):
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

_med = df['NumMentions'].median()
_iqr = df['NumMentions'].quantile(0.75) - df['NumMentions'].quantile(0.25)
df['score_mentions']  = np.clip((df['NumMentions'] - _med) / (_iqr + 1e-9), 0, 1)
df['score_goldstein'] = minmax(df['GoldsteinScale'] * -1)
df['score_tone']      = np.where(df['AvgTone'] < tone_threshold, minmax(df['AvgTone'].abs()), 0)

daily_mentions = df.groupby('SQLDATE')['NumMentions'].sum()
daily_mean     = daily_mentions.mean()
daily_std      = daily_mentions.std()
daily_zscore   = ((daily_mentions - daily_mean) / (daily_std + 1e-9)).clip(lower=0)
df['score_zscore'] = df['SQLDATE'].map(daily_zscore / (daily_zscore.max() + 1e-9)).fillna(0)

# ── 거리 계산 ─────────────────────────────────────────────
MEDIAN_LINE = LineString([(122.0, 27.0), (118.0, 23.0)])

def calc_dist_km(lat, lon):
    try:
        point   = Point(lon, lat)
        nearest = MEDIAN_LINE.interpolate(MEDIAN_LINE.project(point))
        return geopy.distance.geodesic((lat, lon), (nearest.y, nearest.x)).km
    except:
        return 9999

df['dist_km'] = df.apply(lambda r: calc_dist_km(r['ActionGeo_Lat'], r['ActionGeo_Long']), axis=1)

# ── geo 점수 계산 ─────────────────────────────────────────
def calc_geo_bins(dist_km):
    for bin_ in geo_bins:
        if dist_km <= bin_['max_km']:
            return bin_['score']
    return 0.1

df['score_geo_bins']   = df['dist_km'].apply(calc_geo_bins)
df['score_geo_kde200'] = np.exp(-0.5 * (df['dist_km'] / 200) ** 2)

# ── Level 분류 ────────────────────────────────────────────
BBOX = {'lat_min': 20, 'lat_max': 45, 'lon_min': 105, 'lon_max': 135}
AMBIGUOUS_COORDS = [
    (39.9289, 116.388), (24.0, 119.0),   (24.0, 121.0),
    (24.1098, 113.005), (15.0, 115.0),   (38.8951, -77.0364),
    (31.2222, 121.458), (25.0327, 121.275), (21.4167, 121.5),
    (25.0478, 121.532),
]

def validate_geo(row):
    lat, lon = row['ActionGeo_Lat'], row['ActionGeo_Long']
    if not (BBOX['lat_min'] <= lat <= BBOX['lat_max'] and
            BBOX['lon_min'] <= lon <= BBOX['lon_max']):
        return 'Level3'
    for a, b in AMBIGUOUS_COORDS:
        if abs(lat - a) < 0.01 and abs(lon - b) < 0.01:
            return 'Level2'
    return 'Level1'

df['geo_level'] = df.apply(validate_geo, axis=1)

# ── 패널티 적용 geo 점수 ──────────────────────────────────
PENALTIES = [1.0, 0.8, 0.5, 0.3]

for p in PENALTIES:
    penalty_map = {'Level1': 1.0, 'Level2': p, 'Level3': 0.0}
    df[f'geo_bins_p{int(p*10)}']   = df['score_geo_bins']   * df['geo_level'].map(penalty_map)
    df[f'geo_kde200_p{int(p*10)}'] = df['score_geo_kde200'] * df['geo_level'].map(penalty_map)

# ── 가중치 ────────────────────────────────────────────────
W = {'geo': weights.get('geo_distance', 0.45),
     'mentions': weights.get('num_mentions', 0.35),
     'goldstein': weights.get('goldstein', 0.05),
     'tone': weights.get('avg_tone', 0.05),
     'zscore': weights.get('zscore', 0.10)}

def calc_priority(geo_col):
    return (df[geo_col]            * W['geo'] +
            df['score_mentions']   * W['mentions'] +
            df['score_goldstein']  * W['goldstein'] +
            df['score_tone']       * W['tone'] +
            df['score_zscore']     * W['zscore'])

VARIANTS = {}
for p in PENALTIES:
    label_bins   = f'계단식_p{int(p*10)}' if p < 1.0 else '계단식(기본)'
    label_kde    = f'KDE200_p{int(p*10)}' if p < 1.0 else 'KDE200(기본)'
    VARIANTS[label_bins] = calc_priority(f'geo_bins_p{int(p*10)}')
    VARIANTS[label_kde]  = calc_priority(f'geo_kde200_p{int(p*10)}')

for name, scores in VARIANTS.items():
    df[f'priority_{name}'] = scores

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
total  = len(df)

# ── 이벤트별 상위 N% 비교 ────────────────────────────────
print("=" * 110)
print("이벤트별 상위 N% 비교 (낮을수록 좋음)")
print("=" * 110)
header = f"{'이벤트':<28}"
for name in VARIANTS:
    header += f" {name[:10]:>10}"
print(header)
print("-" * 110)

for start, end, ename, level in KNOWN_CRISES:
    mask = (df['SQLDATE'] >= start) & (df['SQLDATE'] <= end)
    sub  = df[mask]
    row  = f"{ename:<28}"
    if len(sub) == 0:
        for _ in VARIANTS:
            row += f" {'없음':>10}"
    else:
        for name in VARIANTS:
            col = f'priority_{name}'
            pct = (df[col] >= sub[col].max()).sum() / total * 100
            row += f" {pct:>9.1f}%"
    print(row)

# ── Recall/Precision/F1 비교 ─────────────────────────────
print()
print("=" * 90)
print(f"Recall / Precision / F1 비교 (버퍼 ±{BUFFER_DAYS}일, 위기 날짜: {len(actual)}일)")
print("=" * 90)
print(f"{'방식':<18} {'Precision':>10} {'Recall':>8} {'F1':>8} {'TP':>5} {'FP':>5} {'FN':>5} {'Threshold':>10}")
print("-" * 80)

results = []
for name in VARIANTS:
    col = f'priority_{name}'
    best_f1 = best_p = best_r = 0
    best_thr = best_tp = best_fp = best_fn = 0
    for thr in np.arange(0.05, 1.0, 0.05).round(2):
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
    print(f"{name:<18} {best_p:>10.3f} {best_r:>8.3f} {best_f1:>8.3f} {best_tp:>5} {best_fp:>5} {best_fn:>5} {best_thr:>10.2f}")
    results.append({'name': name, 'precision': best_p, 'recall': best_r,
                    'f1': best_f1, 'tp': best_tp, 'fp': best_fp, 'fn': best_fn,
                    'threshold': best_thr})

df_results = pd.DataFrame(results)
best_row = df_results.loc[df_results['f1'].idxmax()]
best_recall_row = df_results.loc[df_results['recall'].idxmax()]
print()
print(f"F1 최고:     {best_row['name']} — P={best_row['precision']:.3f} / R={best_row['recall']:.3f} / F1={best_row['f1']:.3f}")
print(f"Recall 최고: {best_recall_row['name']} — P={best_recall_row['precision']:.3f} / R={best_recall_row['recall']:.3f} / F1={best_recall_row['f1']:.3f}")

df_results.to_csv("project/01_data/processed/geo_penalty_results.csv", index=False)
print(f"\n저장 완료: geo_penalty_results.csv")
