import pandas as pd
import yaml

with open("config.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)

df = pd.read_csv("project/01_data/processed/events_filtered.csv")
df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

# ── 날짜별 집계 ──────────────────────────────────────────
daily = df.groupby('SQLDATE').agg(
    DailyMentions=('NumMentions', 'sum'),
    EventCount=('EventCode', 'count'),
    AvgGoldstein=('GoldsteinScale', 'mean'),
    AvgTone=('AvgTone', 'mean')
).reset_index()

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