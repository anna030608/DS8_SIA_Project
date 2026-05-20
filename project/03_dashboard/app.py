import streamlit as st
import pandas as pd
import folium
import plotly.graph_objects as go
from streamlit_folium import st_folium

# ── 페이지 설정 ───────────────────────────────────────────
st.set_page_config(
    page_title="양안관계 위성 촬영 의사결정 지원 시스템",
    layout="wide"
)

# ── 커스텀 CSS ────────────────────────────────────────────
st.markdown("""
<style>
    /* 전체 배경 및 여백 */
    .main .block-container {
        padding-top: 1rem;
        padding-left: 2rem;
        padding-right: 2rem;
        max-width: 100%;
    }

    /* 상단 타이틀 바 스타일 */
    .dashboard-title {
        background: linear-gradient(90deg, #0a0e1a 0%, #111827 100%);
        border-bottom: 1px solid rgba(255,140,0,0.3);
        padding: 10px 20px;
        margin: -1rem -2rem 1rem -2rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    /* 섹션 헤더 통일 */
    h4 {
        font-size: 13px !important;
        color: #aaaaaa !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 8px !important;
    }

    /* metric 카드 크기 */
    [data-testid="metric-container"] {
        background-color: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 6px;
        padding: 8px 12px;
        margin-bottom: 6px;
    }

    [data-testid="metric-container"] label {
        font-size: 11px !important;
        color: #888888 !important;
    }

    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 20px !important;
    }

    /* 구분선 */
    hr {
        border-color: rgba(255,255,255,0.08) !important;
        margin: 10px 0 !important;
    }

    /* 버튼 */
    .stButton button {
        background-color: #ff8c00 !important;
        color: white !important;
        border: none !important;
        font-weight: bold !important;
        letter-spacing: 0.5px;
    }

    /* 스크롤바 */
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-track { background: rgba(255,255,255,0.05); }
    ::-webkit-scrollbar-thumb { background: rgba(255,140,0,0.4); border-radius: 2px; }

    /* Folium 지도 테두리 제거 */
    iframe { border: none !important; }

    /* 필터 라벨 통일 */
    .stDateInput label,
    .stSlider label {
        font-size: 14px !important;
        color: #aaaaaa !important;
        font-weight: bold !important;
    }
</style>
""", unsafe_allow_html=True)

# ── CAMEO 코드 매핑 ───────────────────────────────────────
CAMEO_DESC = {
    '150': ('군사력 사용', '병력 동원 및 군사 행동 수행'),
    '151': ('군사 충돌', '무력 충돌 발생'),
    '152': ('영공 침범', '전투기·군용기 영공 진입'),
    '153': ('해상 봉쇄', '해군 봉쇄 작전 수행'),
    '154': ('군사 점령', '영토·시설 군사 점령'),
    '155': ('핵 위협', '핵무기 관련 위협 또는 행동'),
    '190': ('군사 훈련', '대규모 군사 훈련 및 기동'),
    '191': ('군비 증강', '군사력 확충 및 무기 배치'),
    '192': ('미사일 발사', '탄도·순항미사일 발사'),
    '193': ('군사 시위', '무력 시위 및 과시'),
    '194': ('군사 도발', '회색지대 도발 행위'),
    '195': ('해군 이동', '함정 이동 및 해상 기동'),
    '196': ('공군 이동', '전투기·폭격기 출격'),
    '200': ('대량살상무기', 'WMD 관련 활동'),
    '201': ('화학무기', '화학무기 사용 또는 위협'),
    '202': ('생물무기', '생물무기 관련 활동'),
    '203': ('방사성무기', '방사성 물질 관련 위협'),
    '204': ('사이버 공격', '사이버전 및 해킹 작전'),
}

def get_alert_level(score):
    if score >= 0.7:
        return 'HIGH', '#ff2d2d'
    elif score >= 0.5:
        return 'MED', '#ff8c00'
    else:
        return 'LOW', '#ffd700'

# ── 데이터 로드 ───────────────────────────────────────────
@st.cache_data
def load_data():
    df = pd.read_csv("project/01_data/processed/final_priority_geo.csv")
    df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])
    return df

@st.cache_data
def load_spike():
    df = pd.read_csv("project/01_data/processed/spike_events.csv")
    df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])
    return df

@st.cache_data
def load_satellite_passes():
    df = pd.read_csv("project/01_data/processed/satellite_passes.csv")
    df['SQLDATE'] = pd.to_datetime(df['SQLDATE'])
    return df

df_passes = load_satellite_passes()

df = load_data()
df_spike = load_spike()

# ── 상단 타이틀 ───────────────────────────────────────────
st.markdown("""
<div class="dashboard-title">
    <div style="font-size:20px; font-weight:bold; color:white; letter-spacing:1px;">
        🛰️ &nbsp; 양안관계 OSINT-GEOINT 의사결정 지원 시스템
    </div>
    <div style="font-size:11px; color:#888888;">
        Operation Control Room &nbsp;|&nbsp; SIA Wevengers
    </div>
</div>
""", unsafe_allow_html=True)

# ── 상단 필터 바 ──────────────────────────────────────────

with st.container():
    f1, f2, f3 = st.columns([1.0, 1.0, 1.2])

    with f1:
        date_min = df['SQLDATE'].min().date()
        date_max = df['SQLDATE'].max().date()
        date_range = st.date_input(
            "기간",
            value=(date_min, date_max),
            min_value=date_min,
            max_value=date_max,
        )

    with f2:
        st.markdown("<p style='font-size:14px;margin-bottom:8px;color:#aaaaaa;font-weight:bold;'>좌표 신뢰도</p>", unsafe_allow_html=True)
        chk_col1, chk_col2 = st.columns(2)
        chk_l1 = chk_col1.checkbox("Level1", value=True)
        chk_l2 = chk_col2.checkbox("Level2", value=True)

    with f3:
        score_min = st.slider(
            "Priority Score 최솟값",
            min_value=0.0, max_value=1.0,
            value=0.3, step=0.05,
        )

geo_levels = []
if chk_l1:
    geo_levels.append('Level1')
if chk_l2:
    geo_levels.append('Level2')

st.divider()

# ── 3단 레이아웃 ──────────────────────────────────────────
left_col, map_col, right_col = st.columns([1, 3, 0.8])

# ════════════════════════════════════════════════════════
# 좌측: OSINT Feed + 필터
# ════════════════════════════════════════════════════════
with left_col:

    # OSINT Feed
    st.markdown("#### 📡 실시간 OSINT Feed")

    # 필터 적용
    if len(date_range) == 2:
        df_feed = df[
            (df['SQLDATE'].dt.date >= date_range[0]) &
            (df['SQLDATE'].dt.date <= date_range[1]) &
            (df['geo_level'].isin(geo_levels)) &
            (df['priority_score'] >= score_min)
        ].sort_values(['SQLDATE', 'priority_score'], ascending=[False, False]).head(10)
    else:
        df_feed = df.sort_values(['SQLDATE', 'priority_score'], ascending=[False, False]).head(10)

    # ── feed_html 생성 ─────────────────────────
    feed_html = ""

    for _, row in df_feed.iterrows():
        code = str(int(row['EventCode']))
        alert, color = get_alert_level(row['priority_score'])
        title, desc = CAMEO_DESC.get(code, (f'이벤트 {code}', '분류되지 않은 이벤트'))
        date_str = row['SQLDATE'].strftime('%Y-%m-%d')
        mentions = int(row['NumMentions'])
        score_val = f"{row['priority_score']:.3f}"
        url = row['SOURCEURL']

        feed_html += (
            '<div style="border-left:3px solid ' + color + ';'
            'background-color:rgba(255,255,255,0.05);'
            'padding:10px 12px;margin-bottom:10px;border-radius:4px;">'
            '<div style="color:' + color + ';font-size:11px;font-weight:bold;margin-bottom:4px;">'
            '⚠ ' + alert + ' ALERT</div>'
            '<div style="font-size:13px;font-weight:bold;color:white;margin-bottom:4px;">'
            + title + '</div>'
            '<div style="font-size:11px;color:#aaaaaa;margin-bottom:6px;">'
            + desc + '</div>'
            '<div style="font-size:11px;color:#888888;">'
            '📅 ' + date_str + ' &nbsp;|&nbsp; '
            '📰 ' + str(mentions) + '건 &nbsp;|&nbsp; '
            'Score: <b style="color:' + color + '">' + score_val + '</b></div>'
            '<div style="margin-top:6px;">'
            '<a href="' + url + '" target="_blank" style="font-size:11px;color:#4a9eff;">'
            '🔗 원문 보기</a></div>'
            '</div>'
        )

    st.markdown(
        f'<div style="max-height:480px;overflow-y:auto;padding-right:4px;scrollbar-width:thin;">'
        + feed_html +
        '</div>',
        unsafe_allow_html=True
    )

# ── 필터 적용 (지도·테이블용) ─────────────────────────────
if len(date_range) == 2:
    df_filtered = df[
        (df['SQLDATE'].dt.date >= date_range[0]) &
        (df['SQLDATE'].dt.date <= date_range[1]) &
        (df['geo_level'].isin(geo_levels)) &
        (df['priority_score'] >= score_min)
    ]
else:
    df_filtered = df

# ════════════════════════════════════════════════════════
# 중앙: 지도
# ════════════════════════════════════════════════════════
with map_col:

    st.markdown("#### 📍 이상 징후 지도")

    m = folium.Map(
        location=[25.0, 121.5],
        zoom_start=5,
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri World Imagery'
    )

    for _, row in df_filtered.iterrows():
        score = row['priority_score']
        _, color = get_alert_level(score)
        opacity = 0.9 if row['geo_level'] == 'Level1' else 0.4
        code = str(int(row['EventCode']))
        title, _ = CAMEO_DESC.get(code, (f'이벤트 {code}', ''))

        pin_size = 30 + int(score * 15)  # Score 비례 크기

        icon_html = (
            '<div style="opacity:' + str(opacity) + ';text-align:center;">'
            # 구글 핀
            '<div style="line-height:1;">'
            '<svg width="' + str(pin_size) + '" height="' + str(int(pin_size*1.4)) + '" viewBox="0 0 24 32" xmlns="http://www.w3.org/2000/svg">'
            '<path d="M12 0C7.6 0 4 3.6 4 8c0 5.4 8 16 8 16s8-10.6 8-16c0-4.4-3.6-8-8-8z" fill="' + color + '"/>'
            '<circle cx="12" cy="8" r="3.5" fill="rgba(0,0,0,0.3)"/>'
            '</svg>'
            '</div>'
            '</div>'
        )

        icon = folium.DivIcon(
            html=icon_html,
            icon_size=(40, 50),
            icon_anchor=(20, 50)
        )

        folium.Marker(
            location=[row['ActionGeo_Lat'], row['ActionGeo_Long']],
            icon=icon,
            popup=folium.Popup(
                f"""
                <b>날짜:</b> {row['SQLDATE'].strftime('%Y-%m-%d')}<br>
                <b>이벤트:</b> {title}<br>
                <b>EventCode:</b> {row['EventCode']}<br>
                <b>Priority Score:</b> {row['priority_score']:.3f}<br>
                <b>기사 수:</b> {int(row['NumMentions'])}건<br>
                <b>GoldsteinScale:</b> {row['GoldsteinScale']}<br>
                <b>신뢰도:</b> {row['geo_level']}<br>
                <a href="{row['SOURCEURL']}" target="_blank">원문 보기</a>
                """,
                max_width=300
            ),
            tooltip=f"{title} | Score: {score:.3f} | {row['geo_level']}"
        ).add_to(m)

    folium.PolyLine(
        locations=[[27.0, 122.0], [23.0, 118.0]],
        color='#ffffff',
        weight=1.5,
        dash_array='6 4',
        opacity=0.6,
        tooltip='Taiwan Strait Median Line'
    ).add_to(m)

    # ── 현황 요약 오버레이 (Folium 내부) ─────────────────
    total = len(df_filtered)
    max_score_str = f"{df_filtered['priority_score'].max():.3f}" if len(df_filtered) > 0 else "N/A"
    lv1 = (df_filtered['geo_level']=='Level1').sum()
    lv2 = (df_filtered['geo_level']=='Level2').sum()

    overlay_html = (
        '<div style="position:fixed;top:10px;left:50px;z-index:9999;'
        'background-color:rgba(10,14,26,0.85);border:1px solid rgba(255,140,0,0.5);'
        'border-radius:6px;padding:8px 16px;display:flex;gap:20px;pointer-events:none;">'
        '<div style="text-align:center;">'
        '<div style="color:#888;font-size:10px;">총 이벤트</div>'
        '<div style="color:white;font-size:16px;font-weight:bold;">' + str(total) + '건</div>'
        '</div>'
        '<div style="text-align:center;">'
        '<div style="color:#888;font-size:10px;">최고 Score</div>'
        '<div style="color:#ff8c00;font-size:16px;font-weight:bold;">' + max_score_str + '</div>'
        '</div>'
        '<div style="text-align:center;">'
        '<div style="color:#888;font-size:10px;">Level1</div>'
        '<div style="color:#4a9eff;font-size:16px;font-weight:bold;">' + str(lv1) + '건</div>'
        '</div>'
        '<div style="text-align:center;">'
        '<div style="color:#888;font-size:10px;">Level2</div>'
        '<div style="color:#aaaaaa;font-size:16px;font-weight:bold;">' + str(lv2) + '건</div>'
        '</div>'
        '</div>'
    )
    m.get_root().html.add_child(folium.Element(overlay_html))

    # ── 범례 오버레이 (Folium 내부) ───────────────────────
    legend_html = (
        '<div style="position:fixed;bottom:20px;left:50px;z-index:9999;'
        'background-color:rgba(10,14,26,0.85);border:1px solid rgba(255,255,255,0.1);'
        'border-radius:6px;padding:6px 12px;font-size:11px;color:white;pointer-events:none;">'
        '🔴 고위험(≥0.7) &nbsp; 🟠 중위험(0.5~0.7) &nbsp; 🟡 저위험(&lt;0.5) &nbsp;|&nbsp; 투명: Level2'
        '</div>'
    )
    m.get_root().html.add_child(folium.Element(legend_html))

    map_data = st_folium(m, width=None, height=480, returned_objects=["last_object_clicked"])

# ════════════════════════════════════════════════════════
# 우측: 현황 요약 + 위성 자산 운용
# ════════════════════════════════════════════════════════
with right_col:
    st.markdown("#### 🛰️ 위성 자산 운용")

    # 클릭된 이벤트 좌표 확인
    clicked_lat = None
    clicked_lon = None

    if map_data and map_data.get("last_object_clicked"):
        clicked_lat = map_data["last_object_clicked"].get("lat")
        clicked_lon = map_data["last_object_clicked"].get("lng")

    if clicked_lat and clicked_lon:
        # 클릭된 좌표와 가장 가까운 이벤트 찾기
        from geopy.distance import geodesic
        df_filtered['_dist'] = df_filtered.apply(
            lambda r: geodesic(
                (clicked_lat, clicked_lon),
                (r['ActionGeo_Lat'], r['ActionGeo_Long'])
            ).km, axis=1
        )
        nearest_event = df_filtered.nsmallest(1, '_dist').iloc[0]
        event_date = nearest_event['SQLDATE'].strftime('%Y-%m-%d')
        event_lat = nearest_event['ActionGeo_Lat']
        event_lon = nearest_event['ActionGeo_Long']

        # 해당 이벤트의 근접 위성 필터링
        passes = df_passes[
            (df_passes['SQLDATE'].dt.strftime('%Y-%m-%d') == event_date) &
            (df_passes['event_lat'] == event_lat) &
            (df_passes['event_lon'] == event_lon)
        ].sort_values('min_dist_km')

        st.markdown(
            '<div style="background-color:rgba(255,255,255,0.05);'
            'border:1px solid rgba(255,140,0,0.4);border-radius:6px;'
            'padding:10px;margin-bottom:10px;">'
            '<div style="color:#aaa;font-size:11px;">선택된 이벤트</div>'
            '<div style="color:white;font-size:13px;font-weight:bold;">'
            + event_date + '</div>'
            '<div style="color:#aaa;font-size:10px;">'
            + f'({event_lat:.4f}, {event_lon:.4f})</div>'
            '</div>',
            unsafe_allow_html=True
        )

        if len(passes) > 0:
            st.markdown(
                f"<div style='color:#aaa;font-size:11px;margin-bottom:6px;'>"
                f"근접 위성 {len(passes)}개 탐지</div>",
                unsafe_allow_html=True
            )

            for _, sat in passes.head(5).iterrows():
                st.markdown(
                    '<div style="border-left:3px solid #4a9eff;'
                    'background-color:rgba(255,255,255,0.04);'
                    'padding:8px 10px;margin-bottom:6px;border-radius:4px;">'
                    '<div style="color:white;font-size:12px;font-weight:bold;">'
                    + sat['satellite_name'] + '</div>'
                    '<div style="color:#aaa;font-size:10px;">'
                    '최근접 거리: <b style="color:#4a9eff;">'
                    + f"{sat['min_dist_km']:.1f}km</b></div>"
                    '</div>',
                    unsafe_allow_html=True
                )
        else:
            st.info("1년 이내 이벤트만 위성 정보를 제공합니다.")

    else:
        st.markdown(
            '<div style="color:#aaa;font-size:12px;text-align:center;'
            'padding:20px;">지도에서 이벤트 핀을 클릭하면<br>근접 위성 정보가 표시됩니다.</div>',
            unsafe_allow_html=True
        )

        # 기존 Mock 데이터 유지 (클릭 전 기본 표시)
        if len(df_filtered) > 0:
            top_event = df_filtered.nlargest(1, 'priority_score').iloc[0]
            score = top_event['priority_score']
            cloud_cover = max(5, int((1 - score) * 40))
            success_rate = min(99, int(score * 100 + 10))

            if cloud_cover <= 20:
                sensor = "EO (광학)"
                sensor_color = "#4a9eff"
                sensor_reason = "구름 수치 양호, 광학 촬영 최적"
            else:
                sensor = "SAR (레이더)"
                sensor_color = "#ff8c00"
                sensor_reason = "구름 수치 높음, 레이더 촬영 권고"

            from datetime import datetime, timedelta
            import random
            random.seed(int(score * 1000))
            minutes_until = random.randint(8, 45)
            next_pass = datetime.now() + timedelta(minutes=minutes_until)

            st.markdown(
                f"""
                <div style="background-color:rgba(255,255,255,0.05);
                border:1px solid rgba(255,140,0,0.4);border-radius:6px;
                padding:12px;margin-bottom:10px;">
                    <div style="color:#aaaaaa;font-size:11px;">최적 위성 추천</div>
                    <div style="color:#ff8c00;font-size:18px;font-weight:bold;">SpaceEye-T</div>
                    <div style="color:#aaaaaa;font-size:10px;">(EO/SAR)</div>
                </div>
                <div style="margin-bottom:10px;">
                    <div style="color:#aaaaaa;font-size:11px;margin-bottom:4px;">촬영 성공 확률 예측</div>
                    <div style="color:#ff2d2d;font-size:26px;font-weight:bold;">{success_rate}%</div>
                </div>
                <div style="margin-bottom:10px;">
                    <div style="color:#aaaaaa;font-size:11px;margin-bottom:2px;">Next Pass 예상</div>
                    <div style="color:white;font-size:20px;font-weight:bold;">{minutes_until}분 후</div>
                    <div style="color:#888888;font-size:10px;">{next_pass.strftime('%Y-%m-%d %H:%M')} (KST)</div>
                </div>
                <div style="margin-bottom:10px;">
                    <div style="color:#aaaaaa;font-size:11px;margin-bottom:2px;">구름량</div>
                    <div style="color:white;font-size:16px;font-weight:bold;">{cloud_cover}%</div>
                </div>
                <div style="margin-bottom:14px;">
                    <div style="color:#aaaaaa;font-size:11px;margin-bottom:2px;">센서 유형 추천</div>
                    <div style="color:{sensor_color};font-size:14px;font-weight:bold;">{sensor}</div>
                    <div style="color:#888888;font-size:10px;">{sensor_reason}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            if st.button("📷 촬영 예약", use_container_width=True, type="primary"):
                st.success(
                    f"✅ 촬영 예약 완료\n\n"
                    f"위성: SpaceEye-T\n"
                    f"시각: {next_pass.strftime('%Y-%m-%d %H:%M')}\n"
                    f"센서: {sensor}"
                )
# ════════════════════════════════════════════════════════
# 하단: 시계열 그래프
# ════════════════════════════════════════════════════════
st.divider()
st.markdown("#### 📈 트렌드 분석 및 시계열 데이터 (Analytics Timeline)")

if len(date_range) == 2:
    df_spike_filtered = df_spike[
        (df_spike['SQLDATE'].dt.date >= date_range[0]) &
        (df_spike['SQLDATE'].dt.date <= date_range[1])
    ]
else:
    df_spike_filtered = df_spike

spike_only = df_spike_filtered[df_spike_filtered['is_spike'] == True]

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df_spike_filtered['SQLDATE'],
    y=df_spike_filtered['DailyMentions'],
    name='기사량',
    fill='tozeroy',
    fillcolor='rgba(30, 144, 255, 0.2)',
    line=dict(color='rgba(30, 144, 255, 0.8)', width=1.5),
    hovertemplate='%{x|%Y-%m-%d}<br>기사량: %{y}<extra></extra>'
))

for ma, color in [('MA_7', 'rgba(255,255,255,0.4)'),
                  ('MA_14', 'rgba(255,200,0,0.4)'),
                  ('MA_30', 'rgba(100,255,100,0.4)')]:
    fig.add_trace(go.Scatter(
        x=df_spike_filtered['SQLDATE'],
        y=df_spike_filtered[ma],
        name=ma,
        mode='lines',
        line=dict(color=color, width=1, dash='dot'),
        hovertemplate=f'{ma}: %{{y:.0f}}<extra></extra>'
    ))

for _, row in spike_only.iterrows():
    fig.add_vline(
        x=row['SQLDATE'],
        line=dict(color='rgba(255, 80, 80, 0.5)', width=1, dash='dash')
    )

fig.add_trace(go.Scatter(
    x=spike_only['SQLDATE'],
    y=spike_only['DailyMentions'],
    name='Spike',
    mode='markers',
    marker=dict(color='#ff2d2d', size=8, symbol='circle'),
    hovertemplate='Spike<br>%{x|%Y-%m-%d}<br>기사량: %{y}<extra></extra>'
))

fig.update_layout(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(color='white'),
    height=250,
    margin=dict(l=20, r=20, t=20, b=20),
    legend=dict(
        orientation='h', 
        yanchor='bottom', 
        y=1.02, xanchor='right', x=1, 
        font=dict(size=11), bgcolor='rgba(0,0,0,0)'),
    xaxis=dict(gridcolor='rgba(255,255,255,0.1)'),
    yaxis=dict(gridcolor='rgba(255,255,255,0.1)', title='기사량'),
    hovermode='x unified'
)

st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════
# 하단: 이벤트 상세 테이블
# ════════════════════════════════════════════════════════
st.divider()
st.markdown("#### 📋 이벤트 상세 정보")

if len(df_filtered) > 0:
    df_table = df_filtered[[
        'SQLDATE', 'EventCode', 'NumMentions',
        'GoldsteinScale', 'AvgTone', 'score_geo',
        'priority_score', 'geo_level', 'SOURCEURL'
    ]].copy()

    df_table['SQLDATE'] = df_table['SQLDATE'].dt.strftime('%Y-%m-%d')
    df_table['EventCode'] = df_table['EventCode'].apply(
        lambda x: f"{int(x)} {CAMEO_DESC.get(str(int(x)), ('',''))[0]}"
    )
    df_table = df_table.sort_values(['SQLDATE', 'priority_score'], ascending=[False, False]).reset_index(drop=True)
    df_table.columns = ['날짜', '이벤트', '기사수', 'Goldstein', 'AvgTone', '지리점수', 'Score', '신뢰도', '원문링크']

    def highlight_score(val):
        if val >= 0.7:
            return 'background-color: rgba(255, 45, 45, 0.3)'
        elif val >= 0.5:
            return 'background-color: rgba(255, 140, 0, 0.3)'
        else:
            return 'background-color: rgba(255, 215, 0, 0.15)'

    st.dataframe(
        df_table.style.map(highlight_score, subset=['Score']),
        use_container_width=True,
        hide_index=True,
        height=400,
        column_config={
            "원문링크": st.column_config.LinkColumn("원문링크", display_text="🔗 보기")
        }
    )
    st.caption(f"총 {len(df_table)}건 | Priority Score 높은 순 정렬")
else:
    st.info("선택한 필터 조건에 해당하는 이벤트가 없습니다.")