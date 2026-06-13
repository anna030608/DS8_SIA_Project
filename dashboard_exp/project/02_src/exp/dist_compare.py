import pandas as pd
from shapely.geometry import Point, LineString
import geopy.distance

df = pd.read_csv("project/01_data/processed/final_priority.csv")

MEDIAN_LINE = LineString([(122.0, 27.0), (118.0, 23.0)])

def calc_dist(lat, lon):
    try:
        point = Point(lon, lat)
        nearest = MEDIAN_LINE.interpolate(MEDIAN_LINE.project(point))
        return round(geopy.distance.geodesic((lat, lon), (nearest.y, nearest.x)).km, 1)
    except:
        return 9999

df['dist_km'] = df.apply(lambda r: calc_dist(r['ActionGeo_Lat'], r['ActionGeo_Long']), axis=1)

AMBIGUOUS_A = [
    (39.9289, 116.388),
    (24.0,    119.0),
]
AMBIGUOUS_B = [
    (39.9289, 116.388),
    (24.0,    119.0),
    (24.0,    121.0),
    (24.1098, 113.005),
    (15.0,    115.0),
    (38.8951, -77.0364),
    (31.2222, 121.458),
    (25.0327, 121.275),
    (21.4167, 121.5),
    (25.0478, 121.532),
]

def is_ambiguous(lat, lon, coords):
    return any(abs(lat - a) < 0.01 and abs(lon - b) < 0.01 for a, b in coords)

df['amb_a'] = df.apply(lambda r: is_ambiguous(r['ActionGeo_Lat'], r['ActionGeo_Long'], AMBIGUOUS_A), axis=1)
df['amb_b'] = df.apply(lambda r: is_ambiguous(r['ActionGeo_Lat'], r['ActionGeo_Long'], AMBIGUOUS_B), axis=1)

df_a = df[~df['amb_a']]
df_b = df[~df['amb_b']]

print("=== 전체 거리 분포 ===")
print(df['dist_km'].describe())
print()
print(df['dist_km'].value_counts().head(10))

print()
print("=== 방식 A (Level1만) 거리 분포 ===")
print(f"행수: {len(df_a)}")
print(df_a['dist_km'].describe())
print()
print(df_a['dist_km'].value_counts().head(10))

print()
print("=== 방식 B (Level1만) 거리 분포 ===")
print(f"행수: {len(df_b)}")
print(df_b['dist_km'].describe())
print()
print(df_b['dist_km'].value_counts().head(10))

bins = [0, 50, 100, 200, 300, 500, 9999]
labels = ['0-50km', '50-100km', '100-200km', '200-300km', '300-500km', '500km+']

print()
print("=== 방식 A 거리 구간별 분포 ===")
df_a['dist_group'] = pd.cut(df_a['dist_km'], bins=bins, labels=labels)
print(df_a['dist_group'].value_counts().sort_index())

print()
print("=== 방식 B 거리 구간별 분포 ===")
df_b['dist_group'] = pd.cut(df_b['dist_km'], bins=bins, labels=labels)
print(df_b['dist_group'].value_counts().sort_index())