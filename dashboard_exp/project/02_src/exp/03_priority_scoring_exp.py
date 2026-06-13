import pandas as pd
import numpy as np
import yaml
import os
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
from geopy.distance import geodesic
from shapely.geometry import Point, LineString
import geopy.distance

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.yaml')
with open(config_path, encoding="utf-8") as f:
    config = yaml.safe_load(f)

df = pd.read_csv("project/01_data/processed/events_filtered.csv")
df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

weights = config['priority_score']['weights']
tone_threshold = config['priority_score']['avg_tone_threshold']
geo_bins = config['priority_score']['geo_distance_bins']

# ── 공통 정규화 ───────────────────────────────────────────
def minmax(series):
    return (series - series.min()) / (series.max() - series.min() + 1e-9)

_med = df['NumMentions'].median()
_iqr = df['NumMentions'].quantile(0.75) - df['NumMentions'].quantile(0.25)
df['score_mentions'] = np.clip((df['NumMentions'] - _med) / (_iqr + 1e-9), 0, 1)
df['score_goldstein'] = minmax(df['GoldsteinScale'].abs())
df['score_tone'] = np.where(
    df['AvgTone'] < tone_threshold,
    minmax(df['AvgTone'].abs()),
    0
)

# ── 대만해협 중간선 거리 계산 ─────────────────────────────
MEDIAN_LINE = LineString([(122.0, 27.0), (118.0, 23.0)])

def calc_dist_km(lat, lon):
    try:
        point = Point(lon, lat)
        nearest = MEDIAN_LINE.interpolate(MEDIAN_LINE.project(point))
        return geopy.distance.geodesic((lat, lon), (nearest.y, nearest.x)).km
    except:
        return 9999

df['dist_km'] = df.apply(
    lambda row: calc_dist_km(row['ActionGeo_Lat'], row['ActionGeo_Long']), axis=1
)

# ── 방식 A: 기존 계단식 구간 점수 ────────────────────────
def calc_geo_score_bins(dist_km):
    for bin_ in geo_bins:
        if dist_km <= bin_['max_km']:
            return bin_['score']
    return 0.1

df['score_geo_bins'] = df['dist_km'].apply(calc_geo_score_bins)

# ── 방식 B: KDE 기반 거리 점수 (bandwidth 비교) ───────────
bandwidths = [50, 100, 200, 400]

for bw in bandwidths:
    df[f'score_geo_kde_{bw}'] = np.exp(-0.5 * (df['dist_km'] / bw) ** 2)

# ── Priority Score 비교 산출 ──────────────────────────────
geo_weight = weights.get('geo_distance', 0.75)
other_score = (
    df['score_mentions'] * weights.get('num_mentions', 0.25) +
    df['score_goldstein'] * weights.get('goldstein', 0) +
    df['score_tone'] * weights.get('avg_tone', 0)
)

df['priority_bins'] = other_score + df['score_geo_bins'] * geo_weight
for bw in bandwidths:
    df[f'priority_kde_{bw}'] = other_score + df[f'score_geo_kde_{bw}'] * geo_weight

# ── 거리별 점수 시각화 ────────────────────────────────────
dist_range = np.linspace(0, 600, 500)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle('거리 점수 방식 비교 (대만해협 중간선 기준)', fontsize=13)

# 왼쪽: 거리별 점수 곡선
ax1 = axes[0]
# 계단식
bin_scores = [calc_geo_score_bins(d) for d in dist_range]
ax1.step(dist_range, bin_scores, where='post', label='계단식 (현재)', color='gray', linewidth=2, linestyle='--')
# KDE
colors = ['#ff2d2d', '#ff8c00', '#4a9eff', '#00cc88']
for bw, color in zip(bandwidths, colors):
    kde_scores = np.exp(-0.5 * (dist_range / bw) ** 2)
    ax1.plot(dist_range, kde_scores, label=f'KDE bw={bw}km', color=color, linewidth=2)

ax1.set_xlabel('대만해협 중간선까지 거리 (km)')
ax1.set_ylabel('geo 점수')
ax1.set_title('거리별 점수 곡선')
ax1.legend(fontsize=9)
ax1.grid(alpha=0.3)
ax1.axvline(x=100, color='gray', linestyle=':', alpha=0.5, label='100km')
ax1.axvline(x=300, color='gray', linestyle=':', alpha=0.5)

# 오른쪽: Priority Score 분포
ax2 = axes[1]
ax2.hist(df['priority_bins'], bins=30, alpha=0.5, label='계단식 (현재)', color='gray')
for bw, color in zip(bandwidths, colors):
    ax2.hist(df[f'priority_kde_{bw}'], bins=30, alpha=0.4, label=f'KDE bw={bw}km', color=color)
ax2.set_xlabel('Priority Score')
ax2.set_ylabel('이벤트 수')
ax2.set_title('Priority Score 분포')
ax2.legend(fontsize=9)
ax2.grid(alpha=0.3)

plt.tight_layout()
plt.savefig('project/01_data/processed/geo_score_comparison.png', dpi=150, bbox_inches='tight')
print("시각화 저장: project/01_data/processed/geo_score_comparison.png")

# ── 상위 10개 이벤트 비교 ────────────────────────────────
print("\n=== 상위 10개 이벤트 Priority Score 비교 ===")
print(f"{'날짜':<12} {'거리(km)':<10} {'계단식':<10}", end="")
for bw in bandwidths:
    print(f"{'KDE_'+str(bw):<12}", end="")
print()

df_top = df.nlargest(10, 'priority_bins')[['SQLDATE', 'dist_km', 'priority_bins'] + [f'priority_kde_{bw}' for bw in bandwidths]]
for _, row in df_top.iterrows():
    print(f"{str(row['SQLDATE'].date()):<12} {row['dist_km']:<10.1f} {row['priority_bins']:<10.3f}", end="")
    for bw in bandwidths:
        print(f"{row[f'priority_kde_{bw}']:<12.3f}", end="")
    print()

# ── 저장 ─────────────────────────────────────────────────
df_out = df.copy()
df_out['score_geo'] = df_out['score_geo_bins']
df_out['priority_score'] = df_out['priority_bins']
df_out = df_out.sort_values('priority_score', ascending=False)
df_out.to_csv("project/01_data/processed/final_priority.csv", index=False)
print(f"\n기본 저장 완료 (계단식): final_priority.csv")
print(f"Score 범위: {df_out['priority_score'].min():.3f} ~ {df_out['priority_score'].max():.3f}")
print(f"\n실험 결과 확인 후 원하는 bandwidth를 config.yaml에 추가하세요:")
print(f"  geo_bandwidth: 100  # KDE bandwidth (km)")