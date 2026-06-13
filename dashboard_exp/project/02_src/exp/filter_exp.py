import pandas as pd
import numpy as np
import yaml
import os

config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.yaml')
with open(config_path, encoding="utf-8") as f:
    config = yaml.safe_load(f)

df = pd.read_csv("project/01_data/raw/gdelt_raw.csv")
df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

print(f"전체 raw 데이터: {len(df)}행")
print()

# ── 날짜별 집계 및 이동평균 계산 ─────────────────────────
daily = df.groupby('SQLDATE')['NumMentions'].sum().reset_index()
daily.columns = ['SQLDATE', 'DailyMentions']

for window in config['spike_detection']['ma_windows']:
    daily[f'MA_{window}'] = daily['DailyMentions'].rolling(window).mean()

daily['above_and'] = (
    (daily['DailyMentions'] > daily['MA_7']) &
    (daily['DailyMentions'] > daily['MA_14']) &
    (daily['DailyMentions'] > daily['MA_30'])
)
daily['above_or'] = (
    (daily['DailyMentions'] > daily['MA_7']) |
    (daily['DailyMentions'] > daily['MA_14']) |
    (daily['DailyMentions'] > daily['MA_30'])
)

valid_dates_and = set(daily[daily['above_and']]['SQLDATE'])
valid_dates_or  = set(daily[daily['above_or']]['SQLDATE'])

# ── 실험 조합 정의 ────────────────────────────────────────
experiments = [
    ('95%', 95, 'AND'),
    ('90%', 90, 'AND'),
    ('90%', 90, 'OR'),
    ('85%', 85, 'AND'),
    ('85%', 85, 'OR'),
    ('80%', 80, 'AND'),
    ('80%', 80, 'OR'),
]

print(f"{'조합':<14} {'임계값':>8} {'filtered':>10} {'spike날짜':>10}")
print('-' * 48)

for label, pct, ma_cond in experiments:
    threshold = df['NumMentions'].quantile(pct / 100)
    valid_dates = valid_dates_and if ma_cond == 'AND' else valid_dates_or

    df_filtered = df[
        (df['NumMentions'] >= threshold) &
        (df['SQLDATE'].isin(valid_dates))
    ]

    # spike 날짜 계산 (전체 날짜 채우기)
    daily_f = df_filtered.groupby('SQLDATE')['NumMentions'].sum().reset_index()
    daily_f.columns = ['SQLDATE', 'DailyMentions']

    full_dates = pd.DataFrame({
        'SQLDATE': pd.date_range(daily_f['SQLDATE'].min(), daily_f['SQLDATE'].max())
    })
    daily_full = full_dates.merge(daily_f, on='SQLDATE', how='left').fillna(0)

    for window in config['spike_detection']['ma_windows']:
        daily_full[f'MA_{window}'] = daily_full['DailyMentions'].rolling(window).mean()

    daily_full['is_spike'] = (
        (daily_full['DailyMentions'] > daily_full['MA_7']) &
        (daily_full['DailyMentions'] > daily_full['MA_14']) &
        (daily_full['DailyMentions'] > daily_full['MA_30'])
    )
    spike_days = daily_full['is_spike'].sum()

    name = f"{label} {ma_cond}"
    print(f"{name:<14} {threshold:>8.1f} {len(df_filtered):>10} {spike_days:>10}")
    