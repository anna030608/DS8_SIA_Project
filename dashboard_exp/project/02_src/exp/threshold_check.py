import pandas as pd
import numpy as np
from datetime import timedelta

df = pd.read_csv("project/01_data/processed/final_priority_geo.csv")
df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

KNOWN_CRISES = [
    ('2025-12-29', '2025-12-30'), ('2025-04-01', '2025-04-02'),
    ('2025-02-27', '2025-02-27'), ('2024-10-14', '2024-10-14'),
    ('2024-05-23', '2024-05-24'), ('2024-01-13', '2024-01-13'),
    ('2023-08-12', '2023-08-18'), ('2023-04-05', '2023-04-10'),
    ('2022-08-31', '2022-08-31'), ('2022-08-04', '2022-08-10'),
    ('2022-08-02', '2022-08-03'), ('2022-07-30', '2022-07-30'),
    ('2021-10-01', '2021-10-04'), ('2021-01-19', '2021-01-19'),
    ('2020-12-31', '2020-12-31'), ('2020-09-17', '2020-09-19'),
    ('2018-04-18', '2018-04-18'),
]

data_start = df['SQLDATE'].min().date()
data_end   = df['SQLDATE'].max().date()
crisis_dates = set()
for start, end in KNOWN_CRISES:
    s = pd.to_datetime(start).date() - timedelta(days=1)
    e = pd.to_datetime(end).date()   + timedelta(days=1)
    for i in range((e - s).days + 1):
        d = s + timedelta(days=i)
        if data_start <= d <= data_end:
            crisis_dates.add(d)

print(f"위기 날짜: {len(crisis_dates)}일")
print(f"{'Threshold':>12} {'Precision':>10} {'Recall':>8} {'F1':>8} {'TP':>5} {'FP':>5} {'FN':>5}")
print('-' * 60)

for thr in [0.20, 0.30, 0.45]:
    predicted = set(df[df['priority_score'] >= thr]['SQLDATE'].dt.date)
    tp = len(predicted & crisis_dates)
    fp = len(predicted - crisis_dates)
    fn = len(crisis_dates - predicted)
    p  = tp / (tp + fp) if (tp + fp) > 0 else 0
    r  = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
    print(f"{thr:>12.2f} {p:>10.3f} {r:>8.3f} {f1:>8.3f} {tp:>5} {fp:>5} {fn:>5}")