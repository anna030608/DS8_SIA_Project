import pandas as pd
from datetime import date

# ── CSV 로드 ──────────────────────────────────────────────
df = pd.read_csv("project/01_data/processed/final_priority_geo.csv")
df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

df_spike = pd.read_csv("project/01_data/processed/spike_events.csv")
df_spike['SQLDATE'] = pd.to_datetime(df_spike['SQLDATE'])

df_passes = pd.read_csv("project/01_data/processed/satellite_passes.csv")
df_passes['SQLDATE'] = pd.to_datetime(df_passes['SQLDATE'])

df_sat_info = pd.read_csv("project/01_data/raw/satellite_info.csv")

# ── 일별 집계 ─────────────────────────────────────────────
df_raw = pd.read_csv("project/01_data/raw/gdelt_raw.csv")
df_raw['SQLDATE'] = pd.to_datetime(df_raw['SQLDATE'])

df_daily = df_raw.groupby('SQLDATE').agg(
    DailyMentions=('NumMentions', 'sum'),
    EventCount=('EventCode', 'count'),
    AvgGoldstein=('GoldsteinScale', 'mean'),
    AvgTone=('AvgTone', 'mean')
).reset_index().sort_values('SQLDATE')

df_daily['MA_7']  = df_daily['DailyMentions'].rolling(7).mean()
df_daily['MA_14'] = df_daily['DailyMentions'].rolling(14).mean()
df_daily['MA_30'] = df_daily['DailyMentions'].rolling(30).mean()
df_daily['MA_60'] = df_daily['DailyMentions'].rolling(60).mean()

# ── 날짜 범위 상수 ────────────────────────────────────────
DATE_MIN = df['SQLDATE'].min().date()
DATE_MAX = df['SQLDATE'].max().date()
DATE_RANGE_DAYS = (df['SQLDATE'].max() - df['SQLDATE'].min()).days
