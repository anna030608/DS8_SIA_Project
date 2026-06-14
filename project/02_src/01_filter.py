import pandas as pd
import yaml

# config 로드
with open("config.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)

df = pd.read_csv("project/01_data/raw/gdelt_raw.csv")
df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

# ── 1. NumMentions 필터 ──────────────────────────
percentile_threshold = config['spike_detection']['mention_percentile']
mention_threshold = df['NumMentions'].quantile(percentile_threshold / 100)

# ── 2. 이동평균 필터 ───────────────
daily = df.groupby('SQLDATE')['NumMentions'].sum().reset_index()
daily.columns = ['SQLDATE', 'DailyMentions']

for window in config['spike_detection']['ma_windows']:
    daily[f'MA_{window}'] = daily['DailyMentions'].rolling(window).mean()

# 3개 이동평균 상회하는 날짜 추출
daily['above_all_ma'] = (
    (daily['DailyMentions'] > daily['MA_7']) |
    (daily['DailyMentions'] > daily['MA_14']) |
    (daily['DailyMentions'] > daily['MA_30'])
)
valid_dates = daily[daily['above_all_ma']]['SQLDATE']

# ── 3. 두 조건 모두 만족하는 이벤트 필터링 ───────────────
df_filtered = df[
    (df['NumMentions'] >= mention_threshold) &
    (df['SQLDATE'].isin(valid_dates))
].copy()

df_filtered.to_csv("project/01_data/processed/events_filtered.csv", index=False)
print(f"필터링 완료: {len(df_filtered)}행 / 전체 {len(df)}행")
print(f"NumMentions 임계값: {mention_threshold}")