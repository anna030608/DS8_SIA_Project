import pandas as pd

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