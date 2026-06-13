import pandas as pd
import yaml
import os

# config 로드 추가
config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.yaml')
with open(config_path, encoding="utf-8") as f:
    config = yaml.safe_load(f)

df = pd.read_csv("project/01_data/processed/final_priority.csv")
df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

# ── 바운딩 박스 정의 (양안관계 관심 범위) ────────────────
BBOX = {
    'lat_min': 20, 'lat_max': 45,
    'lon_min': 105, 'lon_max': 135
}

# ── 반복 좌표 목록 (GDELT 국가 대표 좌표) ────────────────
# 실제 지점이 아닌 국가/지역 중심 좌표로 모호한 경우
AMBIGUOUS_COORDS = [
    (39.9289, 116.388),   # 베이징 중심
    (24.0,    119.0),     # 대만 해협 중심
    (24.0,    121.0),     # 대만 본섬 중심
    (24.1098, 113.005),   # 광둥성
    (15.0,    115.0),     # 남중국해
    (38.8951, -77.0364),  # 워싱턴 D.C.
    (31.2222, 121.458),   # 상하이
    (25.0327, 121.275),   # 타오위안
    (21.4167, 121.5),     # 바시 해협
    (25.0478, 121.532),   # 타이베이
]

def validate_geo(row):
    lat, lon = row['ActionGeo_Lat'], row['ActionGeo_Long']
    
    # Level 3: 바운딩 박스 벗어남
    if not (BBOX['lat_min'] <= lat <= BBOX['lat_max'] and
            BBOX['lon_min'] <= lon <= BBOX['lon_max']):
        return 'Level3'
    
    # Level 2: 바운딩 박스 통과 but 모호한 대표 좌표
    for amb_lat, amb_lon in AMBIGUOUS_COORDS:
        if abs(lat - amb_lat) < 0.01 and abs(lon - amb_lon) < 0.01:
            return 'Level2'
    
    # Level 1: 정상
    return 'Level1'

df['geo_level'] = df.apply(validate_geo, axis=1)

# Level2 패널티 적용 추가
penalty_map = {'Level1': 1.0, 'Level2': 0.5, 'Level3': 0.0}
df['score_geo'] = df['score_geo'] * df['geo_level'].map(penalty_map)

# priority_score 재계산 (F_균형+Z 가중치)
w = config['priority_score']['weights']
df['priority_score'] = (
    df['score_geo']       * w['geo_distance'] +
    df['score_mentions']  * w['num_mentions'] +
    df['score_goldstein'] * w['goldstein'] +
    df['score_tone']      * w['avg_tone'] +
    df['score_zscore']    * w['zscore']
)

# ── 결과 요약 ─────────────────────────────────────────────
print("지리 검증 결과:")
print(df['geo_level'].value_counts())
print(f"\n전체: {len(df)}행")
print(f"Level1 (정상): {(df['geo_level']=='Level1').sum()}행")
print(f"Level2 (모호): {(df['geo_level']=='Level2').sum()}행")
print(f"Level3 (제외): {(df['geo_level']=='Level3').sum()}행")

# ── 저장: Level3 제외, Level1/2 모두 포함 ────────────────
df_geo = df[df['geo_level'] != 'Level3'].copy()

df_geo.to_csv("project/01_data/processed/final_priority_geo.csv", index=False)
print(f"\n저장 완료: {len(df_geo)}행 → final_priority_geo.csv")