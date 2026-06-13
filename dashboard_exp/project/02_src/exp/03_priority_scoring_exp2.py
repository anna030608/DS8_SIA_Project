import pandas as pd
import numpy as np
import yaml
import os
from shapely.geometry import Point, LineString
import geopy.distance

config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.yaml')
with open(config_path, encoding="utf-8") as f:
    config = yaml.safe_load(f)

df = pd.read_csv("project/01_data/processed/events_filtered.csv")
df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

tone_threshold = config['priority_score']['avg_tone_threshold']
geo_bins       = config['priority_score']['geo_distance_bins']

# ── 중요 이벤트 기준 날짜 (±2일) ─────────────────────────
KEY_EVENTS = [
    ('2025-12-29', '2025-12-30', '중국 대만 주변 포위형 군사활동'),
    ('2025-04-01', '2025-04-02', 'Strait Thunder-2025A'),
    ('2025-02-27', '2025-02-27', '대만 해안 실사격 훈련'),
    ('2024-10-14', '2024-10-14', 'Joint Sword-2024B'),
    ('2024-05-23', '2024-05-24', 'Joint Sword-2024A'),
    ('2024-01-13', '2024-01-13', '라이칭더 총통 당선'),
    ('2023-08-12', '2023-08-18', '라이칭더 미국 경유 방문'),
    ('2023-04-05', '2023-04-10', 'Shandong 작전·Joint Sword'),
    ('2022-08-31', '2022-08-31', '금문도 드론 격추'),
    ('2022-08-04', '2022-08-10', '대만 포위 실사격 훈련'),
    ('2022-08-02', '2022-08-03', 'Pelosi 대만 방문'),
    ('2022-07-30', '2022-07-30', 'Pelosi 방문 직전 군사훈련'),
    ('2021-10-01', '2021-10-04', '역대 최대 ADIZ 진입'),
    ('2021-01-19', '2021-01-19', '대만 군사 방어 훈련'),
    ('2020-12-31', '2020-12-31', '미국 대만해협 통과'),
    ('2020-09-17', '2020-09-19', '미국 국무차관 대만 방문'),
    ('2020-08-09', '2020-08-12', '미국 보건장관 대만 방문'),
    ('2019-03-31', '2019-03-31', '대만해협 중간선 침범'),
    ('2018-04-18', '2018-04-18', '대만해협 실사격 훈련'),
    ('2016-05-20', '2016-05-20', '차이잉원 취임'),
]

# ── 공통 점수 계산 ────────────────────────────────────────
def minmax(series):
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

# mentions: IQR 기반
_med = df['NumMentions'].median()
_iqr = df['NumMentions'].quantile(0.75) - df['NumMentions'].quantile(0.25)
df['score_mentions'] = np.clip((df['NumMentions'] - _med) / (_iqr + 1e-9), 0, 1)

# goldstein: 갈등 방향성 반영 (음수일수록 높은 점수)
df['score_goldstein'] = minmax(df['GoldsteinScale'] * -1)

# tone
df['score_tone'] = np.where(
    df['AvgTone'] < tone_threshold,
    minmax(df['AvgTone'].abs()),
    0
)

# geo: 계단식
MEDIAN_LINE = LineString([(122.0, 27.0), (118.0, 23.0)])

def calc_dist_km(lat, lon):
    try:
        point   = Point(lon, lat)
        nearest = MEDIAN_LINE.interpolate(MEDIAN_LINE.project(point))
        return geopy.distance.geodesic((lat, lon), (nearest.y, nearest.x)).km
    except:
        return 9999

df['dist_km'] = df.apply(
    lambda r: calc_dist_km(r['ActionGeo_Lat'], r['ActionGeo_Long']), axis=1
)

def calc_geo_score(dist_km):
    for bin_ in geo_bins:
        if dist_km <= bin_['max_km']:
            return bin_['score']
    return 0.1

df['score_geo'] = df['dist_km'].apply(calc_geo_score)

# Z-Score (날짜별 기사량 기준)
daily_mentions = df.groupby('SQLDATE')['NumMentions'].sum()
daily_mean = daily_mentions.mean()
daily_std  = daily_mentions.std()
daily_zscore = ((daily_mentions - daily_mean) / (daily_std + 1e-9)).clip(lower=0)
daily_zscore_norm = (daily_zscore / (daily_zscore.max() + 1e-9))
df['score_zscore'] = df['SQLDATE'].map(daily_zscore_norm).fillna(0)

# ── 가중치 조합 정의 ──────────────────────────────────────
WEIGHT_SETS = {
    '현재':    {'geo': 0.75, 'mentions': 0.25, 'goldstein': 0.00, 'tone': 0.00, 'zscore': 0.00},
    'A균형형':  {'geo': 0.50, 'mentions': 0.30, 'goldstein': 0.10, 'tone': 0.10, 'zscore': 0.00},
    'B_Z추가':  {'geo': 0.60, 'mentions': 0.25, 'goldstein': 0.05, 'tone': 0.05, 'zscore': 0.05},
    'C기사량':  {'geo': 0.40, 'mentions': 0.40, 'goldstein': 0.10, 'tone': 0.10, 'zscore': 0.00},
    'D지리+Z':  {'geo': 0.70, 'mentions': 0.15, 'goldstein': 0.05, 'tone': 0.05, 'zscore': 0.05},
    'E_BZ강화':   {'geo': 0.55, 'mentions': 0.25, 'goldstein': 0.05, 'tone': 0.05, 'zscore': 0.10},  # Z-Score 비중 높임
    'F_균형+Z':   {'geo': 0.45, 'mentions': 0.35, 'goldstein': 0.05, 'tone': 0.05, 'zscore': 0.10},  # mentions+Z 강화
    'G_tone강화': {'geo': 0.50, 'mentions': 0.25, 'goldstein': 0.05, 'tone': 0.15, 'zscore': 0.05},  # tone 비중 높임
    'H_gold강화': {'geo': 0.50, 'mentions': 0.25, 'goldstein': 0.15, 'tone': 0.05, 'zscore': 0.05},  # goldstein 비중 높임
    'I_전균형':   {'geo': 0.40, 'mentions': 0.30, 'goldstein': 0.10, 'tone': 0.10, 'zscore': 0.10},  # 5개 균등 배분
    # B 기반 튜닝
    'B1_mentions↑': {'geo': 0.58, 'mentions': 0.28, 'goldstein': 0.05, 'tone': 0.04, 'zscore': 0.05},
    'B2_zscore↑':   {'geo': 0.58, 'mentions': 0.23, 'goldstein': 0.04, 'tone': 0.05, 'zscore': 0.10},
    'B3_tone↓':     {'geo': 0.62, 'mentions': 0.26, 'goldstein': 0.06, 'tone': 0.01, 'zscore': 0.05},

    # D 기반 튜닝
    'D1_mentions↑': {'geo': 0.65, 'mentions': 0.20, 'goldstein': 0.05, 'tone': 0.05, 'zscore': 0.05},
    'D2_zscore↑':   {'geo': 0.65, 'mentions': 0.15, 'goldstein': 0.05, 'tone': 0.05, 'zscore': 0.10},
    'D3_geo↓':      {'geo': 0.62, 'mentions': 0.18, 'goldstein': 0.05, 'tone': 0.05, 'zscore': 0.10},
}


# ── 각 조합별 스코어 계산 ─────────────────────────────────
for name, w in WEIGHT_SETS.items():
    df[f'score_{name}'] = (
        df['score_geo']       * w['geo'] +
        df['score_mentions']  * w['mentions'] +
        df['score_goldstein'] * w['goldstein'] +
        df['score_tone']      * w['tone'] +
        df['score_zscore']    * w['zscore']
    )

# ── 중요 이벤트 상위 순위 비교 ────────────────────────────
print("=" * 80)
print("중요 이벤트별 Priority Score 비교 (각 방식의 상위 N% 내 포함 여부)")
print("=" * 80)

total = len(df)

print(f"\n{'이벤트':<22}", end="")
for name in WEIGHT_SETS:
    print(f"  {name:<8}", end="")
print()
print("-" * 80)

for start, end, ename in KEY_EVENTS:
    mask = (df['SQLDATE'] >= start) & (df['SQLDATE'] <= end)
    sub  = df[mask]
    if len(sub) == 0:
        print(f"{ename:<22}", end="")
        for name in WEIGHT_SETS:
            print(f"  {'없음':<8}", end="")
        print()
        continue

    print(f"{ename:<22}", end="")
    for name in WEIGHT_SETS:
        col = f'score_{name}'
        top_score = sub[col].max()
        rank_pct  = (df[col] >= top_score).sum() / total * 100
        print(f"  {rank_pct:>5.1f}%  ", end="")
    print()

# ── 전체 Score 범위 요약 ──────────────────────────────────
print("\n" + "=" * 80)
print("전체 Score 범위 요약")
print("=" * 80)
print(f"{'방식':<12} {'min':>6} {'mean':>6} {'max':>6} {'상위5%기준':>10}")
for name in WEIGHT_SETS:
    col = f'score_{name}'
    print(f"{name:<12} {df[col].min():>6.3f} {df[col].mean():>6.3f} {df[col].max():>6.3f} {df[col].quantile(0.95):>10.3f}")

# ── 저장: 현재 방식 유지, 실험 결과 별도 저장 ───────────────
df['priority_score'] = df['score_현재']
df.sort_values('priority_score', ascending=False).to_csv(
    "project/01_data/processed/final_priority.csv", index=False
)
df.sort_values('score_A균형형', ascending=False).to_csv(
    "project/01_data/processed/final_priority_A.csv", index=False
)
df.sort_values('score_B_Z추가', ascending=False).to_csv(
    "project/01_data/processed/final_priority_B.csv", index=False
)
df.sort_values('score_C기사량', ascending=False).to_csv(
    "project/01_data/processed/final_priority_C.csv", index=False
)
df.sort_values('score_D지리+Z', ascending=False).to_csv(
    "project/01_data/processed/final_priority_D.csv", index=False
)
print("\n저장 완료: final_priority_A/B/C/D.csv")