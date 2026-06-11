import pandas as pd
from datetime import date

# ── CSV 로드 ──────────────────────────────────────────────
df = pd.read_csv("project/01_data/processed/final_priority_geo.csv")
df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

# ── 신뢰도 등급 병합 ─────────────────────────────────────
import os
 
_REL_PATH = "project/01_data/processed/event_reliability.csv"
if os.path.exists(_REL_PATH):
    _rel = pd.read_csv(_REL_PATH)
    # event_key가 GLOBALEVENTID 문자열이므로 숫자로 변환해 병합
    _rel['_gid'] = pd.to_numeric(_rel['event_key'], errors='coerce')
    _rel_small = _rel[['_gid', 'grade', 'verdict', 'reason']].dropna(subset=['_gid'])
    _rel_small['_gid'] = _rel_small['_gid'].astype('int64')
 
    df = df.merge(
        _rel_small.rename(columns={
            '_gid': 'GLOBALEVENTID',
            'grade': 'reliability_grade',
            'verdict': 'reliability_verdict',
            'reason': 'reliability_reason',
        }),
        on='GLOBALEVENTID', how='left'
    )
    # 매칭 안 된 사건은 UNVERIFIED
    df['reliability_grade'] = df['reliability_grade'].fillna('UNVERIFIED')
else:
    # 신뢰도 파일이 없으면 전부 UNVERIFIED (대시보드가 깨지지 않게)
    df['reliability_grade'] = 'UNVERIFIED'
    df['reliability_verdict'] = '-'
    df['reliability_reason'] = ''

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
