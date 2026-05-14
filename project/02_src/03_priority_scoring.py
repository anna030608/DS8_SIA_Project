import pandas as pd
import numpy as np
import yaml
from geopy.distance import geodesic

# 수정
import os
config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
with open(config_path, encoding="utf-8") as f:
    config = yaml.safe_load(f)

df = pd.read_csv("project/01_data/processed/events_filtered.csv")
df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])
spike = pd.read_csv("project/01_data/processed/spike_events.csv")
spike['SQLDATE'] = pd.to_datetime(spike['SQLDATE'])

weights = config['priority_score']['weights']
tone_threshold = config['priority_score']['avg_tone_threshold']
tw_lat = config['priority_score']['taiwan_strait']['lat']
tw_lon = config['priority_score']['taiwan_strait']['lon']
geo_bins = config['priority_score']['geo_distance_bins']

# ── 스파이크 날짜 이벤트만 ────────────────────────────────
df = df[df['SQLDATE'].isin(spike['SQLDATE'])].copy()

# ── 각 지표 정규화 (0~1) ─────────────────────────────────
def minmax(series):
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

df['score_mentions'] = minmax(df['NumMentions'])
df['score_goldstein'] = minmax(df['GoldsteinScale'].abs())

# AvgTone: -3 이하일 때만 반영
df['score_tone'] = np.where(
    df['AvgTone'] < tone_threshold,
    minmax(df['AvgTone'].abs()),
    0
)

# ── 거리 기반 지리 점수 ───────────────────────────────────
def calc_geo_score(lat, lon):
    try:
        dist_km = geodesic((tw_lat, tw_lon), (lat, lon)).km
        for bin_ in geo_bins:
            if dist_km <= bin_['max_km']:
                return bin_['score']
    except:
        return 0.1

df['score_geo'] = df.apply(
    lambda row: calc_geo_score(row['ActionGeo_Lat'], row['ActionGeo_Long']),
    axis=1
)

# ── Priority Score 산출 ──────────────────────────────────
df['priority_score'] = (
    df['score_mentions']  * weights['num_mentions'] +
    df['score_goldstein'] * weights['goldstein'] +
    df['score_tone']      * weights['avg_tone'] +
    df['score_geo']       * weights['geo_distance']
)

# ── 정렬 및 저장 ─────────────────────────────────────────
df_final = df.sort_values('priority_score', ascending=False)

df_final.to_csv("project/01_data/processed/final_priority.csv", index=False)
print(f"Priority Score 산출 완료: {len(df_final)}행")
print(f"Score 범위: {df_final['priority_score'].min():.3f} ~ {df_final['priority_score'].max():.3f}")
print(f"\n거리 점수 분포:\n{df_final['score_geo'].value_counts()}")