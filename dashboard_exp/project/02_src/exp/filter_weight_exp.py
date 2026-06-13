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

df_raw = pd.read_csv("project/01_data/raw/gdelt_raw.csv")
df_raw['SQLDATE'] = pd.to_datetime(df_raw['SQLDATE'])

tone_threshold = config['priority_score']['avg_tone_threshold']
geo_bins       = config['priority_score']['geo_distance_bins']

# ── 공통 함수 ─────────────────────────────────────────────
def minmax(series):
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

MEDIAN_LINE = LineString([(122.0, 27.0), (118.0, 23.0)])

def calc_dist_km(lat, lon):
    try:
        point   = Point(lon, lat)
        nearest = MEDIAN_LINE.interpolate(MEDIAN_LINE.project(point))
        return geopy.distance.geodesic((lat, lon), (nearest.y, nearest.x)).km
    except:
        return 9999

def calc_geo_bins(dist_km):
    for bin_ in geo_bins:
        if dist_km <= bin_['max_km']:
            return bin_['score']
    return 0.1

BBOX = {'lat_min': 20, 'lat_max': 45, 'lon_min': 105, 'lon_max': 135}
AMBIGUOUS_COORDS = [
    (39.9289, 116.388), (24.0, 119.0),    (24.0, 121.0),
    (24.1098, 113.005), (15.0, 115.0),    (38.8951, -77.0364),
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

penalty_map = {'Level1': 1.0, 'Level2': 0.5, 'Level3': 0.0}

# ── 필터 후보 ─────────────────────────────────────────────
FILTER_SETS = [
    ('90% OR',  90, 'OR'),
    ('85% OR',  85, 'OR'),
    ('90% AND', 90, 'AND'),
    ('85% AND', 85, 'AND'),  # 추가
    ('80% OR',  80, 'OR'),   # 추가
    ('80% AND', 80, 'AND'),  # 추가
]

# ── 가중치 조합 ───────────────────────────────────────────
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

data_start = df_raw['SQLDATE'].min().date()
data_end   = df_raw['SQLDATE'].max().date()
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

# ── 필터별 데이터 준비 ────────────────────────────────────
filter_data = {}
for filter_name, pct, ma_cond in FILTER_SETS:
    threshold = df_raw['NumMentions'].quantile(pct / 100)
    daily = df_raw.groupby('SQLDATE')['NumMentions'].sum().reset_index()
    daily.columns = ['SQLDATE', 'DailyMentions']
    for window in config['spike_detection']['ma_windows']:
        daily[f'MA_{window}'] = daily['DailyMentions'].rolling(window).mean()

    if ma_cond == 'AND':
        daily['above_ma'] = (
            (daily['DailyMentions'] > daily['MA_7']) &
            (daily['DailyMentions'] > daily['MA_14']) &
            (daily['DailyMentions'] > daily['MA_30'])
        )
    else:
        daily['above_ma'] = (
            (daily['DailyMentions'] > daily['MA_7']) |
            (daily['DailyMentions'] > daily['MA_14']) |
            (daily['DailyMentions'] > daily['MA_30'])
        )

    valid_dates = set(daily[daily['above_ma']]['SQLDATE'])
    df_f = df_raw[
        (df_raw['NumMentions'] >= threshold) &
        (df_raw['SQLDATE'].isin(valid_dates))
    ].copy()

    # 점수 계산
    _med = df_f['NumMentions'].median()
    _iqr = df_f['NumMentions'].quantile(0.75) - df_f['NumMentions'].quantile(0.25)
    df_f['score_mentions']  = np.clip((df_f['NumMentions'] - _med) / (_iqr + 1e-9), 0, 1)
    df_f['score_goldstein'] = minmax(df_f['GoldsteinScale'] * -1)
    df_f['score_tone']      = np.where(df_f['AvgTone'] < tone_threshold, minmax(df_f['AvgTone'].abs()), 0)

    daily_m = df_f.groupby('SQLDATE')['NumMentions'].sum()
    daily_zscore = ((daily_m - daily_m.mean()) / (daily_m.std() + 1e-9)).clip(lower=0)
    df_f['score_zscore'] = df_f['SQLDATE'].map(daily_zscore / (daily_zscore.max() + 1e-9)).fillna(0)

    df_f['dist_km']   = df_f.apply(lambda r: calc_dist_km(r['ActionGeo_Lat'], r['ActionGeo_Long']), axis=1)
    df_f['score_geo'] = df_f['dist_km'].apply(calc_geo_bins)
    df_f['geo_level'] = df_f.apply(validate_geo, axis=1)
    df_f['score_geo'] = df_f['score_geo'] * df_f['geo_level'].map(penalty_map)
    df_f = df_f[df_f['geo_level'] != 'Level3'].copy()

    filter_data[filter_name] = df_f
    print(f"{filter_name} 준비 완료: {len(df_f)}행")

# ── 36개 조합 평가 ────────────────────────────────────────
all_results = []

for filter_name, _, _ in FILTER_SETS:
    df_f = filter_data[filter_name]
    print(f"\n{'='*80}")
    print(f"필터: {filter_name} ({len(df_f)}행)")
    print(f"{'방식':<14} {'Precision':>10} {'Recall':>8} {'F1':>8} {'TP':>5} {'FP':>5} {'FN':>5} {'Threshold':>10}")
    print("-" * 70)

    for w_name, w in WEIGHT_SETS.items():
        df_f['priority'] = (
            df_f['score_geo']       * w['geo'] +
            df_f['score_mentions']  * w['mentions'] +
            df_f['score_goldstein'] * w['goldstein'] +
            df_f['score_tone']      * w['tone'] +
            df_f['score_zscore']    * w['zscore']
        )

        best_f1 = best_p = best_r = 0
        best_thr = best_tp = best_fp = best_fn = 0
        for thr in np.arange(0.00, 1.0, 0.05).round(2):
            predicted = set(df_f[df_f['priority'] >= thr]['SQLDATE'].dt.date)
            tp = len(predicted & actual)
            fp = len(predicted - actual)
            fn = len(actual - predicted)
            p  = tp / (tp + fp) if (tp + fp) > 0 else 0
            r  = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
            if f1 > best_f1:
                best_f1, best_p, best_r = f1, p, r
                best_thr, best_tp, best_fp, best_fn = thr, tp, fp, fn

        print(f"{w_name:<14} {best_p:>10.3f} {best_r:>8.3f} {best_f1:>8.3f} {best_tp:>5} {best_fp:>5} {best_fn:>5} {best_thr:>10.2f}")
        all_results.append({
            'filter': filter_name, 'weights': w_name,
            'precision': best_p, 'recall': best_r, 'f1': best_f1,
            'tp': best_tp, 'fp': best_fp, 'fn': best_fn, 'threshold': best_thr
        })

df_all = pd.DataFrame(all_results)
best_f1_row = df_all.loc[df_all['f1'].idxmax()]
best_r_row  = df_all.loc[df_all['recall'].idxmax()]

print(f"\n{'='*80}")
print("전체 36개 조합 중")
print(f"F1 최고:     {best_f1_row['filter']}/{best_f1_row['weights']} — P={best_f1_row['precision']:.3f} / R={best_f1_row['recall']:.3f} / F1={best_f1_row['f1']:.3f} / Thr={best_f1_row['threshold']:.2f}")
print(f"Recall 최고: {best_r_row['filter']}/{best_r_row['weights']} — P={best_r_row['precision']:.3f} / R={best_r_row['recall']:.3f} / F1={best_r_row['f1']:.3f} / Thr={best_r_row['threshold']:.2f}")

print(f"\nRecall 상위 10개:")
top10 = df_all.nlargest(10, 'recall')[['filter','weights','precision','recall','f1','fp','threshold']]
print(top10.to_string(index=False))

df_all.to_csv("project/01_data/processed/filter_weight_results.csv", index=False)
print(f"\n저장 완료: filter_weight_results.csv")