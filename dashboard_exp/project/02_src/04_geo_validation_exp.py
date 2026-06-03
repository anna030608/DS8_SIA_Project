import pandas as pd

df = pd.read_csv("project/01_data/processed/final_priority.csv")
df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

BBOX = {
    'lat_min': 20, 'lat_max': 45,
    'lon_min': 105, 'lon_max': 135
}

# ── 방식 A: 기존 (2개) ───────────────────────────────────
AMBIGUOUS_COORDS_A = [
    (39.9289, 116.388),   # 베이징 중심
    (24.0,    119.0),     # 대만 해협 중심
]

# ── 방식 B: 추가 (거리 분포 기반) ────────────────────────
AMBIGUOUS_COORDS_B = [
    (39.9289, 116.388),   # 베이징 중심
    (24.0,    119.0),     # 대만 해협 중심
    (24.0,    121.0),     # 대만 본섬 중심
    (24.1098, 113.005),   # 광둥성
    (15.0,    115.0),     # 남중국해
    (38.8951, -77.0364),  # 워싱턴 D.C.
    (31.2222, 121.458),   # 상하이
    (25.0327, 121.275),   # 대만 타오위안
    (21.4167, 121.5),     # 바시 해협
]

def validate_geo(row, ambiguous_coords):
    lat, lon = row['ActionGeo_Lat'], row['ActionGeo_Long']

    if not (BBOX['lat_min'] <= lat <= BBOX['lat_max'] and
            BBOX['lon_min'] <= lon <= BBOX['lon_max']):
        return 'Level3'

    for amb_lat, amb_lon in ambiguous_coords:
        if abs(lat - amb_lat) < 0.01 and abs(lon - amb_lon) < 0.01:
            return 'Level2'

    return 'Level1'

df['geo_level_a'] = df.apply(lambda r: validate_geo(r, AMBIGUOUS_COORDS_A), axis=1)
df['geo_level_b'] = df.apply(lambda r: validate_geo(r, AMBIGUOUS_COORDS_B), axis=1)

# ── 비교 출력 ────────────────────────────────────────────
print("=== 방식 A (기존 2개) ===")
print(df['geo_level_a'].value_counts())

print("\n=== 방식 B (추가 9개) ===")
print(df['geo_level_b'].value_counts())

print("\n=== A→B 변화: Level1 → Level2로 바뀐 좌표 ===")
changed = df[
    (df['geo_level_a'] == 'Level1') &
    (df['geo_level_b'] == 'Level2')
][['SQLDATE', 'ActionGeo_Lat', 'ActionGeo_Long', 'NumMentions']].drop_duplicates(
    subset=['ActionGeo_Lat', 'ActionGeo_Long']
)
print(changed.to_string())

print("\n=== A→B 변화: Level2 → Level3로 바뀐 것 ===")
changed2 = df[
    (df['geo_level_a'] != 'Level3') &
    (df['geo_level_b'] == 'Level3')
][['SQLDATE', 'ActionGeo_Lat', 'ActionGeo_Long']].drop_duplicates(
    subset=['ActionGeo_Lat', 'ActionGeo_Long']
)
print(changed2.to_string())

# ── 저장 ─────────────────────────────────────────────────
df['geo_level'] = df['geo_level_a']
df_geo_a = df[df['geo_level'] != 'Level3'].copy()
df_geo_a.to_csv("project/01_data/processed/final_priority_geo.csv", index=False)

df['geo_level'] = df['geo_level_b']
df_geo_b = df[df['geo_level'] != 'Level3'].copy()
df_geo_b.to_csv("project/01_data/processed/final_priority_geo_exp.csv", index=False)

print(f"\n저장 완료:")
print(f"  final_priority_geo.csv     → 기존 A ({len(df_geo_a)}행)")
print(f"  final_priority_geo_exp.csv → 실험 B ({len(df_geo_b)}행)")