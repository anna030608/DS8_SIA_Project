import pandas as pd

raw = pd.read_csv("project/01_data/raw/gdelt_raw.csv")
filtered = pd.read_csv("project/01_data/processed/events_filtered.csv")
spike = pd.read_csv("project/01_data/processed/spike_events.csv")

raw['SQLDATE'] = pd.to_datetime(raw['SQLDATE'])
filtered['SQLDATE'] = pd.to_datetime(filtered['SQLDATE'])
spike['SQLDATE'] = pd.to_datetime(spike['SQLDATE'])

events = [
    ('2025-12-29', '2025-12-30', '중국 대만 주변 포위형 군사활동',          '매우 높음'),
    ('2025-04-01', '2025-04-02', 'Strait Thunder-2025A',                   '매우 높음'),
    ('2025-02-27', '2025-02-27', '대만 해안 실사격 훈련',                   '매우 높음'),
    ('2024-10-12', '2024-10-16', 'Joint Sword-2024B',                      '매우 높음'),
    ('2024-05-23', '2024-05-24', 'Joint Sword-2024A',                      '매우 높음'),
    ('2024-01-13', '2024-01-13', '라이칭더 총통 당선',                       '높음'),
    ('2023-08-12', '2023-08-18', '라이칭더 미국 경유 방문',                  '높음'),
    ('2023-04-05', '2023-04-10', 'Shandong 작전·Joint Sword',              '매우 높음'),
    ('2022-08-31', '2022-08-31', '금문도 드론 격추',                        '높음'),
    ('2022-08-04', '2022-08-10', '대만 포위 실사격 훈련',                   '매우 높음'),
    ('2022-08-02', '2022-08-03', 'Pelosi 대만 방문',                       '매우 높음'),
    ('2022-07-30', '2022-07-30', 'Pelosi 방문 직전 군사훈련',               '매우 높음'),
    ('2021-10-01', '2021-10-04', '역대 최대 ADIZ 진입',                    '매우 높음'),
    ('2021-01-19', '2021-01-19', '대만 군사 방어 훈련',                     '높음'),
    ('2020-12-31', '2020-12-31', '미국 대만해협 통과',                      '중간~높음'),
    ('2020-09-17', '2020-09-19', '미국 국무차관 대만 방문',                  '높음'),
    ('2020-08-09', '2020-08-12', '미국 보건장관 대만 방문',                  '높음'),
    ('2019-03-31', '2019-03-31', '대만해협 중간선 침범',                    '매우 높음'),
    ('2018-04-18', '2018-04-18', '대만해협 실사격 훈련',                    '높음'),
    ('2016-05-20', '2016-05-20', '차이잉원 취임',                           '높음'),
]

print(f"{'이벤트':<30} {'중요도':<10} {'기간':<24} {'raw':>5} {'filtered':>9} {'spike':>6}")
print('-' * 90)
for start, end, name, level in events:
    r = len(raw[(raw['SQLDATE'] >= start) & (raw['SQLDATE'] <= end)])
    f = len(filtered[(filtered['SQLDATE'] >= start) & (filtered['SQLDATE'] <= end)])
    s = len(spike[(spike['SQLDATE'] >= start) & (spike['SQLDATE'] <= end)])
    print(f"{name:<30} {level:<10} {start}~{end:<12} {r:>5} {f:>9} {s:>6}")