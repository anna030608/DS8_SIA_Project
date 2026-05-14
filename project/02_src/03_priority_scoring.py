import pandas as pd
import numpy as np
import yaml

with open("config.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)

df = pd.read_csv("project/01_data/processed/events_filtered.csv")
df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])
spike = pd.read_csv("project/01_data/processed/spike_events.csv")
spike['SQLDATE'] = pd.to_datetime(spike['SQLDATE'])

weights = config['priority_score']['weights']
tone_threshold = config['priority_score']['avg_tone_threshold']

# ── 스파이크 날짜의 이벤트만 대상 ────────────────────────
df = df[df['SQLDATE'].isin(spike['SQLDATE'])].copy()

# ── 각 지표 정규화 (0~1) ─────────────────────────────────
def minmax(series):
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

df['score_mentions'] = minmax(df['NumMentions'])
df['score_goldstein'] = minmax(df['GoldsteinScale'].abs())  # 절댓값: 클수록 위험

# AvgTone: -3 이하일 때만 소폭 반영, 이상이면 0
df['score_tone'] = np.where(
    df['AvgTone'] < tone_threshold,
    minmax(df['AvgTone'].abs()),
    0
)

# ── Priority Score 산출 ──────────────────────────────────
df['priority_score'] = (
    df['score_mentions']  * weights['num_mentions'] +
    df['score_goldstein'] * weights['goldstein'] +
    df['score_tone']      * weights['avg_tone']
)

# ── 정렬 및 저장 ─────────────────────────────────────────
df_final = df.sort_values('priority_score', ascending=False)

df_final.to_csv("project/01_data/processed/final_priority.csv", index=False)
print(f"Priority Score 산출 완료: {len(df_final)}행")
print(f"Score 범위: {df_final['priority_score'].min():.3f} ~ {df_final['priority_score'].max():.3f}")