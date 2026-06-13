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
weights        = config['priority_score']['weights']

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

# ── 필터 조합 정의 ────────────────────────────────────────
FILTER_SETS = [
    ('90% AND', 90, 'AND'),
    ('90% OR',  90, 'OR'),
    ('85% AND', 85, 'AND'),
    ('85% OR',  85, 'OR'),
    ('80% AND', 80, 'AND'),  # 추가
    ('80% OR',  80, 'OR'),   # 추가
]

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

# ── 필터 조합별 파이프라인 실행 ───────────────────────────
print("=" * 90)
print(f"필터 조합별 F_균형+Z 평가지표 비교 (버퍼 ±{BUFFER_DAYS}일, 위기 날짜: {len(actual)}일)")
print("=" * 90)
print(f"{'필터':<12} {'filtered':>9} {'Precision':>10} {'Recall':>8} {'F1':>8} {'TP':>5} {'FP':>5} {'FN':>5} {'Threshold':>10}")
print("-" * 80)

all_results = []

for filter_name, pct, ma_cond in FILTER_SETS:

    # 1. 필터링
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
    df_filtered = df_raw[
        (df_raw['NumMentions'] >= threshold) &
        (df_raw['SQLDATE'].isin(valid_dates))
    ].copy()

    # 2. 점수 계산
    _med = df_filtered['NumMentions'].median()
    _iqr = df_filtered['NumMentions'].quantile(0.75) - df_filtered['NumMentions'].quantile(0.25)
    df_filtered['score_mentions']  = np.clip((df_filtered['NumMentions'] - _med) / (_iqr + 1e-9), 0, 1)
    df_filtered['score_goldstein'] = minmax(df_filtered['GoldsteinScale'] * -1)
    df_filtered['score_tone']      = np.where(df_filtered['AvgTone'] < tone_threshold, minmax(df_filtered['AvgTone'].abs()), 0)

    daily_m = df_filtered.groupby('SQLDATE')['NumMentions'].sum()
    daily_mean = daily_m.mean()
    daily_std  = daily_m.std()
    daily_zscore = ((daily_m - daily_mean) / (daily_std + 1e-9)).clip(lower=0)
    df_filtered['score_zscore'] = df_filtered['SQLDATE'].map(
        daily_zscore / (daily_zscore.max() + 1e-9)
    ).fillna(0)

    df_filtered['dist_km']   = df_filtered.apply(lambda r: calc_dist_km(r['ActionGeo_Lat'], r['ActionGeo_Long']), axis=1)
    df_filtered['score_geo'] = df_filtered['dist_km'].apply(calc_geo_bins)

    # 3. geo validation + 패널티
    df_filtered['geo_level'] = df_filtered.apply(validate_geo, axis=1)
    df_filtered['score_geo'] = df_filtered['score_geo'] * df_filtered['geo_level'].map(penalty_map)

    # Level3 제외
    df_geo = df_filtered[df_filtered['geo_level'] != 'Level3'].copy()

    # 4. F_균형+Z priority_score 계산
    df_geo['priority_score'] = (
        df_geo['score_geo']       * weights['geo_distance'] +
        df_geo['score_mentions']  * weights['num_mentions'] +
        df_geo['score_goldstein'] * weights['goldstein'] +
        df_geo['score_tone']      * weights['avg_tone'] +
        df_geo['score_zscore']    * weights['zscore']
    )

    # 5. 평가지표
    best_f1 = best_p = best_r = 0
    best_thr = best_tp = best_fp = best_fn = 0
    for thr in np.arange(0.00, 1.0, 0.05).round(2):
        predicted = set(df_geo[df_geo['priority_score'] >= thr]['SQLDATE'].dt.date)
        tp = len(predicted & actual)
        fp = len(predicted - actual)
        fn = len(actual - predicted)
        p  = tp / (tp + fp) if (tp + fp) > 0 else 0
        r  = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
        if f1 > best_f1:
            best_f1, best_p, best_r = f1, p, r
            best_thr, best_tp, best_fp, best_fn = thr, tp, fp, fn

    print(f"{filter_name:<12} {len(df_filtered):>9} {best_p:>10.3f} {best_r:>8.3f} {best_f1:>8.3f} {best_tp:>5} {best_fp:>5} {best_fn:>5} {best_thr:>10.2f}")
    all_results.append({
        'filter': filter_name, 'filtered': len(df_filtered),
        'precision': best_p, 'recall': best_r, 'f1': best_f1,
        'tp': best_tp, 'fp': best_fp, 'fn': best_fn, 'threshold': best_thr
    })

pd.DataFrame(all_results).to_csv("project/01_data/processed/filter_validation_results.csv", index=False)
print("\n저장 완료: filter_validation_results.csv")