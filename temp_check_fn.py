import pandas as pd
import numpy as np

df = pd.read_csv('project/01_data/processed/final_priority_geo.csv')
df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])

check_events = [
    ('2019-03-28', '2019-04-03', '대만해협 중간선 침범'),
    ('2018-04-15', '2018-04-21', '대만해협 실사격 훈련'),
    ('2013-11-20', '2013-11-26', '동중국해 ADIZ 선포'),
]

for start, end, name in check_events:
    mask = (df['SQLDATE'] >= start) & (df['SQLDATE'] <= end)
    result = df[mask][['SQLDATE', 'EventCode', 'priority_score', 'NumMentions', 'score_geo']]
    print(f'=== {name} ({start} ~ {end}) ===')
    if len(result) == 0:
        print('  → 해당 기간 이벤트 없음 (필터링에서 제외됨)')
    else:
        print(result.sort_values('priority_score', ascending=False).to_string(index=False))
    print()