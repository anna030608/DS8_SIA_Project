import pandas as pd
import numpy as np
import yaml
import os
from geopy.distance import geodesic
from shapely.geometry import Point, LineString
import geopy.distance

config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.yaml')
with open(config_path, encoding="utf-8") as f:
    config = yaml.safe_load(f)

df = pd.read_csv("project/01_data/processed/events_filtered.csv")
df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

weights = config['priority_score']['weights']
tone_threshold = config['priority_score']['avg_tone_threshold']
geo_bins = config['priority_score']['geo_distance_bins']

# ── 각 지표 정규화 (0~1) ─────────────────────────────────
def minmax(series):
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

# min-max
# df['score_mentions'] = minmax(df['NumMentions'])
# IQR
_med = df['NumMentions'].median()
_iqr = df['NumMentions'].quantile(0.75) - df['NumMentions'].quantile(0.25)
df['score_mentions'] = np.clip((df['NumMentions'] - _med) / (_iqr + 1e-9), 0, 1)

# Goldstein: 방향성 반영 (음수=갈등이 높은 점수가 되도록 * -1)
df['score_goldstein'] = minmax(df['GoldsteinScale'] * -1)

# AvgTone: -3 이하일 때만 반영
df['score_tone'] = np.where(
    df['AvgTone'] < tone_threshold,
    minmax(df['AvgTone'].abs()),
    0
)

# ── Z-Score: 일별 기사량 이상도 ──────────────────────────
daily_mentions = df.groupby('SQLDATE')['NumMentions'].sum()
daily_mean = daily_mentions.mean()
daily_std  = daily_mentions.std()
daily_zscore = ((daily_mentions - daily_mean) / (daily_std + 1e-9)).clip(lower=0)
# 0~1 정규화 후 각 사건 날짜에 매핑
df['score_zscore'] = df['SQLDATE'].map(
    daily_zscore / (daily_zscore.max() + 1e-9)
).fillna(0)

# ── 거리 기반 지리 점수 ───────────────────────────────────
# 대만해협 중간선
MEDIAN_LINE = LineString([(122.0, 27.0), (118.0, 23.0)])

def calc_geo_score(lat, lon):
    try:
        point = Point(lon, lat)
        # 선분 위의 최근접점 찾기
        nearest = MEDIAN_LINE.interpolate(MEDIAN_LINE.project(point))
        nearest_lat = nearest.y
        nearest_lon = nearest.x
        # 최근접점까지 실제 거리(km) 계산
        dist_km = geopy.distance.geodesic(
            (lat, lon), (nearest_lat, nearest_lon)
        ).km
        # 구간별 점수 적용
        for bin_ in geo_bins:
            if dist_km <= bin_['max_km']:
                return bin_['score']
    except:
        return 0.0

df['score_geo'] = df.apply(
    lambda row: calc_geo_score(row['ActionGeo_Lat'], row['ActionGeo_Long']),
    axis=1
)

# ── Priority Score 1차 산출 (geo_level 패널티는 04에서 반영) ──
df['priority_score'] = (
    df['score_mentions']  * weights['num_mentions'] +
    df['score_goldstein'] * weights['goldstein'] +
    df['score_tone']      * weights['avg_tone'] +
    df['score_geo']       * weights['geo_distance'] +
    df['score_zscore']    * weights['zscore']
)

# ── 정렬 및 저장 ─────────────────────────────────────────
df_final = df.sort_values('priority_score', ascending=False)

df_final.to_csv("project/01_data/processed/final_priority.csv", index=False)
print(f"Priority Score 1차 산출 완료: {len(df_final)}행")
print(f"  (geo_level 패널티는 04_geo_validation.py에서 최종 반영)")
print(f"Score 범위: {df_final['priority_score'].min():.3f} ~ {df_final['priority_score'].max():.3f}")
print(f"\n거리 점수 분포:\n{df_final['score_geo'].value_counts()}")