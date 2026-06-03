import pandas as pd
import yaml
import os

config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.yaml')
with open(config_path, encoding="utf-8") as f:
    config = yaml.safe_load(f)  # ← 들여쓰기 필요

df = pd.read_csv("project/01_data/processed/events_filtered.csv")
df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

# ── 날짜별 집계 ──────────────────────────────────────────
daily = df.groupby('SQLDATE').agg(
    DailyMentions=('NumMentions', 'sum'),
    EventCount=('EventCode', 'count'),
    AvgGoldstein=('GoldsteinScale', 'mean'),
    AvgTone=('AvgTone', 'mean')
).reset_index()

# ── 전체 날짜 범위 채우기 (rolling 정확도 확보) ─────────── 추가
full_dates = pd.DataFrame({
    'SQLDATE': pd.date_range(daily['SQLDATE'].min(), daily['SQLDATE'].max())
})
daily = full_dates.merge(daily, on='SQLDATE', how='left')
daily['DailyMentions'] = daily['DailyMentions'].fillna(0)
daily['EventCount']    = daily['EventCount'].fillna(0)
daily['AvgGoldstein']  = daily['AvgGoldstein'].fillna(0)
daily['AvgTone']       = daily['AvgTone'].fillna(0)

# ── 이동평균 및 증가율 산출 ──────────────────────────────
for window in config['spike_detection']['ma_windows']:
    daily[f'MA_{window}'] = daily['DailyMentions'].rolling(window).mean()

daily['MoM_rate'] = daily['DailyMentions'].pct_change(periods=7) * 100  # 7일 전 대비 증가율

# ── 스파이크 여부 라벨링 ─────────────────────────────────
daily['is_spike'] = (
    (daily['DailyMentions'] > daily['MA_7']) &
    (daily['DailyMentions'] > daily['MA_14']) &
    (daily['DailyMentions'] > daily['MA_30'])
)

spike_events = daily[daily['is_spike']].copy()

spike_events.to_csv("project/01_data/processed/spike_events.csv", index=False)
print(f"스파이크 탐지 완료: {len(spike_events)}일")
print(f"전체 기간 중 스파이크 비율: {len(spike_events)/len(daily)*100:.1f}%")