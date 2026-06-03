import pandas as pd
import numpy as np
from shapely.geometry import Point, LineString
import geopy.distance

df = pd.read_csv("project/01_data/processed/events_filtered.csv")

MEDIAN_LINE = LineString([(122.0, 27.0), (118.0, 23.0)])

def calc_dist(lat, lon):
    try:
        point = Point(lon, lat)
        nearest = MEDIAN_LINE.interpolate(MEDIAN_LINE.project(point))
        return round(geopy.distance.geodesic((lat, lon), (nearest.y, nearest.x)).km, 1)
    except:
        return 9999

df['dist_km'] = df.apply(lambda r: calc_dist(r['ActionGeo_Lat'], r['ActionGeo_Long']), axis=1)

print("=== 거리 분포 ===")
print(df['dist_km'].describe())

print("\n=== 거리별 이벤트 수 ===")
print(df['dist_km'].value_counts().head(10))

print("\n=== 거리 구간별 이벤트 수 ===")
bins = [0, 50, 100, 200, 300, 500, 9999]
labels = ['0-50km', '50-100km', '100-200km', '200-300km', '300-500km', '500km+']
df['dist_group'] = pd.cut(df['dist_km'], bins=bins, labels=labels)
print(df['dist_group'].value_counts().sort_index())

print("\n=== 중간 거리 이벤트 샘플 (100~300km) ===")
mid = df[(df['dist_km'] >= 100) & (df['dist_km'] <= 300)][['SQLDATE', 'dist_km', 'NumMentions']].head(10)
print(mid.to_string())