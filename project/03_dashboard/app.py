<<<<<<< HEAD
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

    st_folium(m, width=None, height=480, returned_objects=[])

# ════════════════════════════════════════════════════════
# 우측: 현황 요약 + 위성 자산 운용
# ════════════════════════════════════════════════════════
with right_col:

    # ── 위성 자산 운용 패널 (Mock) ────────────────────────
    st.markdown("#### 🛰️ 위성 자산 운용")

    # 최고 Score 이벤트 기준으로 Mock 데이터 생성
    if len(df_filtered) > 0:
        top_event = df_filtered.nlargest(1, 'priority_score').iloc[0]
        score = top_event['priority_score']

        # Score 기반 촬영 성공률 및 센서 추천 (규칙 기반)
        cloud_cover = max(5, int((1 - score) * 40))   # Score 높을수록 구름 적게
        success_rate = min(99, int(score * 100 + 10))  # Score 높을수록 성공률 높게

        if cloud_cover <= 20:
            sensor = "EO (광학)"
            sensor_color = "#4a9eff"
            sensor_reason = "구름 수치 양호, 광학 촬영 최적"
        else:
            sensor = "SAR (레이더)"
            sensor_color = "#ff8c00"
            sensor_reason = "구름 수치 높음, 레이더 촬영 권고"

        # Next Pass Mock (현재 시각 기준 + 랜덤 오프셋)
        from datetime import datetime, timedelta
        import random
        random.seed(int(score * 1000))  # Score 기반 고정값
        minutes_until = random.randint(8, 45)
        next_pass = datetime.now() + timedelta(minutes=minutes_until)

        # 최적 위성 추천
        st.markdown(
            f"""
            <div style="
                background-color: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,140,0,0.4);
                border-radius: 6px;
                padding: 12px;
                margin-bottom: 10px;
            ">
                <div style="color:#aaaaaa; font-size:11px;">최적 위성 추천</div>
                <div style="color:#ff8c00; font-size:18px; font-weight:bold;">
                    SpaceEye-T
                </div>
                <div style="color:#aaaaaa; font-size:10px;">(EO/SAR)</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 촬영 성공 확률
        bar_color = '#ff2d2d' if success_rate >= 80 else '#ff8c00'
        st.markdown(
            f"""
            <div style="margin-bottom:10px;">
                <div style="color:#aaaaaa; font-size:11px; margin-bottom:4px;">촬영 성공 확률 예측</div>
                <div style="color:{bar_color}; font-size:26px; font-weight:bold;">
                    {success_rate}%
                </div>
                <div style="
                    background-color: rgba(255,255,255,0.1);
                    border-radius: 4px;
                    height: 6px;
                    margin-top: 4px;
                ">
                    <div style="
                        background-color: {bar_color};
                        width: {success_rate}%;
                        height: 6px;
                        border-radius: 4px;
                    "></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Next Pass 카운트다운
        st.markdown(
            f"""
            <div style="margin-bottom:10px;">
                <div style="color:#aaaaaa; font-size:11px; margin-bottom:2px;">
                    Next Pass 예상
                </div>
                <div style="color:white; font-size:20px; font-weight:bold;">
                    {minutes_until}분 후
                </div>
                <div style="color:#888888; font-size:10px;">
                    {next_pass.strftime('%Y-%m-%d %H:%M')} (KST)
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 구름량 및 센서 추천
        st.markdown(
            f"""
            <div style="margin-bottom:10px;">
                <div style="color:#aaaaaa; font-size:11px; margin-bottom:2px;">
                    구름량
                </div>
                <div style="color:white; font-size:16px; font-weight:bold;">
                    {cloud_cover}%
                </div>
            </div>
            <div style="margin-bottom:14px;">
                <div style="color:#aaaaaa; font-size:11px; margin-bottom:2px;">
                    센서 유형 추천
                </div>
                <div style="color:{sensor_color}; font-size:14px; font-weight:bold;">
                    {sensor}
                </div>
                <div style="color:#888888; font-size:10px;">
                    {sensor_reason}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # 촬영 예약 버튼
        if st.button("📷 촬영 예약", use_container_width=True, type="primary"):
            st.success(
                f"✅ 촬영 예약 완료\n\n"
                f"위성: SpaceEye-T\n"
                f"시각: {next_pass.strftime('%Y-%m-%d %H:%M')}\n"
                f"센서: {sensor}"
            )

    else:
        st.info("필터 조건에 해당하는 이벤트가 없습니다.")
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
=======
import dash
import sys, os
sys.path.insert(0, os.path.dirname(__file__)) 
from dash import dcc, html, Input, Output, State, dash_table
import dash_leaflet as dl
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import timedelta

# ── 컴포넌트 import ───────────────────────────────────────
from components.data_loader import (
    df, df_daily, df_spike, df_passes, df_sat_info,
    DATE_MIN, DATE_MAX
)
from components.helpers import (
    CAMEO_DESC, get_alert_level, get_cloud_cover
)
from components.layout import create_layout
from components.feed_panel import render_feed
from components.map_panel import render_markers, render_overlay
from components.satellite_panel import render_satellite
from components.ai_panel import render_ai

# ── Dash 앱 초기화 ────────────────────────────────────────
app = dash.Dash(__name__, assets_folder='assets', suppress_callback_exceptions=True)
server = app.server
app.title = "양안관계 OSINT-GEOINT 의사결정 지원 시스템"
app.layout = create_layout()


# ── 콜백: 날짜 범위 ───────────────────────────────────────
@app.callback(
    Output('date-range', 'data'),
    Output('date-range-display', 'children'),
    Output('input-start-date', 'value'),
    Output('input-end-date', 'value'),
    Input('btn-period-3m', 'n_clicks'),
    Input('btn-period-6m', 'n_clicks'),
    Input('btn-period-1y', 'n_clicks'),
    Input('btn-period-all', 'n_clicks'),
    Input('input-start-date', 'value'),
    Input('input-end-date', 'value'),
    prevent_initial_call=False
)
def update_date_range(n_3m, n_6m, n_1y, n_all, input_start, input_end):
    from dash import ctx
    triggered = ctx.triggered_id if ctx.triggered_id else 'btn-period-all'

    if triggered == 'btn-period-3m':
        start, end = DATE_MAX - timedelta(days=90), DATE_MAX
    elif triggered == 'btn-period-6m':
        start, end = DATE_MAX - timedelta(days=180), DATE_MAX
    elif triggered == 'btn-period-1y':
        start, end = DATE_MAX - timedelta(days=365), DATE_MAX
    elif triggered in ('input-start-date', 'input-end-date'):
        try:
            start = pd.to_datetime(input_start).date() if input_start else DATE_MIN
            end   = pd.to_datetime(input_end).date()   if input_end   else DATE_MAX
            start = max(start, DATE_MIN)
            end   = min(end,   DATE_MAX)
        except:
            start, end = DATE_MIN, DATE_MAX
    else:
        start, end = DATE_MIN, DATE_MAX

    return {'start': str(start), 'end': str(end)}, "", str(start), str(end)


# ── 콜백: Score 슬라이더 표시 ─────────────────────────────
@app.callback(
    Output('score-display', 'children'),
    Input('score-slider', 'value')
)
def update_score_display(value):
    return f"{value:.2f}"


# ── 콜백: 대만해협 중간선 ────────────────────────────────
@app.callback(Output('median-line', 'children'), Input('main-map', 'id'))
def render_median_line(_):
    return [dl.Polyline(positions=[[27.0, 122.0], [23.0, 118.0]],
                        color='white', weight=1.5, dashArray='6 4', opacity=0.6)]


# ── 콜백: 지도 마커 + 오버레이 ───────────────────────────
@app.callback(
    Output('event-markers', 'children'),
    Output('map-overlay', 'children'),
    Input('date-range', 'data'),
    Input('geo-level', 'value'),
    Input('score-slider', 'value'),
    Input('selected-event', 'data')
)
def update_markers(date_range, geo_levels, score_min, selected_event):
    markers = render_markers(date_range, geo_levels, score_min, selected_event)
    overlay = render_overlay(date_range, geo_levels, score_min)
    return markers, overlay


# ── 콜백: 패널 전환 (버튼) ───────────────────────────────
@app.callback(
    Output('active-panel', 'data'),
    Input('btn-feed', 'n_clicks'),
    Input('btn-satellite', 'n_clicks'),
    Input('btn-ai', 'n_clicks'),
    prevent_initial_call=True
)
def switch_panel(feed, satellite, ai):
    from dash import ctx
    mapping = {'btn-feed': 'feed', 'btn-satellite': 'satellite', 'btn-ai': 'ai'}
    return mapping.get(ctx.triggered_id, dash.no_update)


# ── 콜백: 마커 클릭 → 패널 전환 ─────────────────────────
@app.callback(
    Output('active-panel', 'data', allow_duplicate=True),
    Input('btn-feed', 'n_clicks'),
    Input('btn-satellite', 'n_clicks'),
    Input('btn-ai', 'n_clicks'),
    Input({'type': 'event-marker', 'index': dash.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def switch_panel_marker(feed, satellite, ai, marker_clicks):
    from dash import ctx
    triggered = ctx.triggered_id
    if triggered == 'btn-feed':       return 'feed'
    if triggered == 'btn-satellite':  return 'satellite'
    if triggered == 'btn-ai':         return 'ai'
    if isinstance(triggered, dict) and triggered.get('type') == 'event-marker':
        if ctx.triggered[0]['value']:
            return 'satellite'
    return dash.no_update


# ── 콜백: 마커 클릭 → 이벤트 저장 ───────────────────────
@app.callback(
    Output('selected-event', 'data'),
    Output('active-panel', 'data', allow_duplicate=True),
    Input({'type': 'event-marker', 'index': dash.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def select_event(n_clicks):
    from dash import ctx
    if not ctx.triggered_id or ctx.triggered[0]['value'] is None:
        return dash.no_update, dash.no_update
    row = df.loc[ctx.triggered_id['index']]
    return _event_data(row), 'satellite'


# ── 콜백: 피드 카드 클릭 → 이벤트 저장 ──────────────────
@app.callback(
    Output('selected-event', 'data', allow_duplicate=True),
    Output('active-panel', 'data', allow_duplicate=True),
    Input({'type': 'feed-item', 'index': dash.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def select_event_from_feed(n_clicks):
    from dash import ctx
    if not ctx.triggered_id or ctx.triggered[0]['value'] is None:
        return dash.no_update, dash.no_update
    row = df.loc[ctx.triggered_id['index']]
    return _event_data(row), 'feed'


# ── 콜백: 피드 → 위성 패널 이동 버튼 ────────────────────
@app.callback(
    Output('active-panel', 'data', allow_duplicate=True),
    Output('selected-event', 'data', allow_duplicate=True),
    Input({'type': 'go-satellite', 'index': dash.ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def go_to_satellite_panel(n_clicks):
    from dash import ctx
    if not ctx.triggered_id or not any(n for n in n_clicks if n):
        return dash.no_update, dash.no_update
    if not ctx.triggered[0]['value']:
        return dash.no_update, dash.no_update
    row = df.loc[ctx.triggered_id['index']]
    return 'satellite', _event_data(row)


# ── 콜백: 사이드 패널 콘텐츠 ─────────────────────────────
@app.callback(
    Output('panel-content', 'children'),
    Input('active-panel', 'data'),
    Input('selected-event', 'data'),
    Input('selected-satellite', 'data'),
    Input('date-range', 'data'),
    Input('geo-level', 'value'),
    Input('score-slider', 'value'),
    Input('cloud-data', 'data'),
)
def update_panel(active_panel, selected_event, selected_satellite,
                 date_range, geo_levels, score_min, cloud_data):
    if active_panel == 'feed':
        return render_feed(selected_event, date_range, geo_levels, score_min)
    elif active_panel == 'satellite':
        return render_satellite(selected_event, selected_satellite, cloud_data)
    elif active_panel == 'ai':
        return render_ai()
    return []


# ── 콜백: 구름량 조회 ────────────────────────────────────
@app.callback(
    Output('cloud-data', 'data'),
    Input('selected-satellite', 'data'),
    State('selected-event', 'data'),
    prevent_initial_call=True
)
def fetch_cloud_data(selected_satellite, selected_event):
    if not selected_satellite or not selected_event:
        return None
    cloud = get_cloud_cover(
        selected_event['lat'],
        selected_event['lon'],
        selected_event['date']
    )
    return {'cloud_cover': cloud}


# ── 콜백: 위성 클릭 → 궤도 표시 ─────────────────────────
@app.callback(
    Output('selected-satellite', 'data'),
    Output('orbit-layer', 'children'),
    Input({'type': 'sat-item', 'name': dash.ALL}, 'n_clicks'),
    Input('selected-event', 'data'),
    prevent_initial_call=True
)
def select_satellite(n_clicks, selected_event):
    from dash import ctx

    if ctx.triggered_id == 'selected-event':
        if not selected_event:
            return None, []
        return None, [dl.CircleMarker(
            center=[selected_event['lat'], selected_event['lon']],
            radius=15, color='#ff2d2d', fillColor='#ff2d2d', fillOpacity=0.3
        )]

    if not ctx.triggered[0]['value'] or not selected_event:
        return dash.no_update, dash.no_update

    sat_name   = ctx.triggered_id['name']
    event_date = selected_event['date']
    event_lat  = selected_event['lat']
    event_lon  = selected_event['lon']

    passes = df_passes[
        (df_passes['SQLDATE'].dt.strftime('%Y-%m-%d') == event_date) &
        (df_passes['event_lat'] == event_lat) &
        (df_passes['event_lon'] == event_lon) &
        (df_passes['satellite_name'] == sat_name)
    ]

    orbit_layers = [dl.CircleMarker(
        center=[event_lat, event_lon],
        radius=15, color='#ff2d2d', fillColor='#ff2d2d', fillOpacity=0.3
    )]

    if len(passes) > 0:
        row = passes.iloc[0]
        try:
            lats = eval(row['track_lats'])
            lons = eval(row['track_lons'])
            coords = list(zip(lats, lons))
            segments, current = [], [coords[0]]
            for i in range(1, len(coords)):
                if abs(coords[i][1] - coords[i-1][1]) > 180:
                    segments.append(current)
                    current = [coords[i]]
                else:
                    current.append(coords[i])
            segments.append(current)
            for seg in segments:
                if len(seg) > 1:
                    orbit_layers.append(
                        dl.Polyline(positions=seg, color='#00ff88', weight=2, opacity=0.8)
                    )
        except:
            pass

    return sat_name, orbit_layers


# ── 콜백: 하단 탭 ────────────────────────────────────────
@app.callback(
    Output('bottom-content', 'children'),
    Input('bottom-tabs', 'value'),
    Input('date-range', 'data'),
    Input('geo-level', 'value'),
    Input('score-slider', 'value'),
)
def update_bottom(tab, date_range, geo_levels, score_min):
    start_date = date_range['start'] if date_range else str(DATE_MIN)
    end_date   = date_range['end']   if date_range else str(DATE_MAX)

    if tab == 'timeseries':
        return _render_timeseries(start_date, end_date)
    elif tab == 'events':
        return _render_event_table(start_date, end_date, geo_levels, score_min)
    return html.Div()


# ── 내부 헬퍼 ────────────────────────────────────────────
def _event_data(row):
    return {
        'date': row['SQLDATE'].strftime('%Y-%m-%d'),
        'lat': row['ActionGeo_Lat'],
        'lon': row['ActionGeo_Long'],
        'score': row['priority_score'],
        'event_code': str(int(row['EventCode'])),
        'num_mentions': int(row['NumMentions'])
    }


def _render_timeseries(start_date, end_date):
    dff = df_daily.copy()
    dff = dff[dff['SQLDATE'].dt.date >= pd.to_datetime(start_date).date()]
    dff = dff[dff['SQLDATE'].dt.date <= pd.to_datetime(end_date).date()]

    spike_dates  = df_spike[
        (df_spike['SQLDATE'].dt.date >= pd.to_datetime(start_date).date()) &
        (df_spike['SQLDATE'].dt.date <= pd.to_datetime(end_date).date())
    ]
    spike_merged = dff[dff['SQLDATE'].isin(spike_dates['SQLDATE'])]

    rolling_mean = dff['DailyMentions'].rolling(30).mean()
    dff['spike_intensity'] = dff['DailyMentions'] / rolling_mean.replace(0, float('nan'))

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.7, 0.3], vertical_spacing=0.05)

    fig.add_trace(go.Scatter(
        x=dff['SQLDATE'], y=dff['DailyMentions'], name='기사량', mode='lines',
        line=dict(color='rgba(30,144,255,0.4)', width=1),
        hovertemplate='%{x|%Y-%m-%d}<br>기사량: %{y}<extra></extra>'
    ), row=1, col=1)

    for col_name, label, color in [
        ('MA_7',  'MA7',  'rgba(255,255,255,0.9)'),
        ('MA_14', 'MA14', 'rgba(255,200,0,0.9)'),
        ('MA_30', 'MA30', 'rgba(100,255,100,0.9)'),
        ('MA_60', 'MA60', 'rgba(255,100,100,0.9)'),
    ]:
        if col_name in dff.columns:
            fig.add_trace(go.Scatter(
                x=dff['SQLDATE'], y=dff[col_name], name=label, mode='lines',
                line=dict(color=color, width=2),
                hovertemplate=f'{label}: %{{y:.0f}}<extra></extra>'
            ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=spike_merged['SQLDATE'], y=spike_merged['DailyMentions'],
        name='Spike', mode='markers',
        marker=dict(color='#ff2d2d', size=8, symbol='circle'),
        hovertemplate='Spike<br>%{x|%Y-%m-%d}<br>%{y}<extra></extra>'
    ), row=1, col=1)

    intensity_colors = [
        '#ff2d2d' if v >= 3 else '#ff8c00' if v >= 2 else '#4a9eff'
        for v in dff['spike_intensity'].fillna(0)
    ]
    fig.add_trace(go.Bar(
        x=dff['SQLDATE'], y=dff['spike_intensity'], name='Spike 강도',
        marker_color=intensity_colors,
        hovertemplate='%{x|%Y-%m-%d}<br>강도: %{y:.1f}x<extra></extra>'
    ), row=2, col=1)

    fig.add_hline(y=2, line=dict(color='rgba(255,140,0,0.5)', width=1, dash='dash'), row=2, col=1)
    fig.add_hline(y=3, line=dict(color='rgba(255,45,45,0.5)',  width=1, dash='dash'), row=2, col=1)

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white', size=11), height=300,
        margin=dict(l=50, r=20, t=10, b=30),
        legend=dict(orientation='h', yanchor='bottom', y=1.02,
                    xanchor='right', x=1, font=dict(size=10), bgcolor='rgba(0,0,0,0)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.08)', title='기사량', title_font_size=10),
        yaxis2=dict(gridcolor='rgba(255,255,255,0.08)', title='Spike 강도(x)', title_font_size=10),
        hovermode='x unified', bargap=0.1,
        hoverlabel=dict(bgcolor='rgba(10,14,26,0.9)',
                        bordercolor='rgba(255,255,255,0.2)',
                        font=dict(color='white', size=11)),
    )
    fig.update_xaxes(gridcolor='rgba(255,255,255,0.08)')

    return html.Div([
        dcc.Graph(figure=fig, config={'displayModeBar': False}, style={'height': '300px'})
    ])


def _render_event_table(start_date, end_date, geo_levels, score_min):
    dff = df.copy()
    dff = dff[dff['SQLDATE'].dt.date >= pd.to_datetime(start_date).date()]
    dff = dff[dff['SQLDATE'].dt.date <= pd.to_datetime(end_date).date()]
    if geo_levels:
        dff = dff[dff['geo_level'].isin(geo_levels)]
    dff = dff[dff['priority_score'] >= score_min]
    dff = dff.sort_values(['SQLDATE', 'priority_score'], ascending=[False, False]).reset_index(drop=True)

    dff['날짜']   = dff['SQLDATE'].dt.strftime('%Y-%m-%d')
    dff['이벤트'] = dff['EventCode'].apply(
        lambda x: f"{int(x)} {CAMEO_DESC.get(str(int(x)), ('',''))[0]}"
    )

    cols = ['날짜', '이벤트', 'NumMentions', 'GoldsteinScale', 'AvgTone', 'priority_score', 'geo_level']
    rename_map = {'NumMentions': '기사수', 'GoldsteinScale': 'Goldstein',
                  'priority_score': 'Score', 'geo_level': '신뢰도'}
    table_cols = [
        {'name': '날짜',      'id': '날짜'},
        {'name': '이벤트',    'id': '이벤트'},
        {'name': '기사수',    'id': '기사수'},
        {'name': 'Goldstein', 'id': 'Goldstein', 'type': 'numeric', 'format': {'specifier': '.2f'}},
        {'name': 'AvgTone',   'id': 'AvgTone',   'type': 'numeric', 'format': {'specifier': '.2f'}},
        {'name': 'Score',     'id': 'Score',      'type': 'numeric', 'format': {'specifier': '.3f'}},
        {'name': '신뢰도',    'id': '신뢰도'},
    ]
    if 'score_geo' in dff.columns:
        cols.insert(5, 'score_geo')
        rename_map['score_geo'] = '지리점수'
        table_cols.insert(5, {'name': '지리점수', 'id': '지리점수',
                               'type': 'numeric', 'format': {'specifier': '.2f'}})

    return html.Div([
        dash_table.DataTable(
            data=dff[cols].rename(columns=rename_map).to_dict('records'),
            columns=table_cols,
            style_table={'height': '300px', 'overflowY': 'auto', 'backgroundColor': '#0a0e1a'},
            style_header={
                'backgroundColor': '#111827', 'color': '#aaa',
                'fontWeight': '500', 'fontSize': '12px',
                'border': 'none',
                'borderBottom': '1px solid rgba(255,255,255,0.15)',
            },
            style_cell={
                'backgroundColor': 'transparent',  # #0a0e1a → transparent 로 변경
                'color': 'white',
                'fontSize': '12px',
                'borderTop': 'none',
                'borderBottom': '1px solid rgba(255,255,255,0.05)',
                'borderLeft': 'none',
                'borderRight': 'none',
                'padding': '8px 12px', 'textAlign': 'left',
            },
            style_data_conditional=[
                # 배경: 피드 카드와 동일한 투명도
                {'if': {'filter_query': '{Score} >= 0.7'},
                 'backgroundColor': 'rgba(255,45,45,0.08)',
                 'borderLeft': '3px solid #ff2d2d'},
                {'if': {'filter_query': '{Score} >= 0.5 && {Score} < 0.7'},
                 'backgroundColor': 'rgba(255,140,0,0.08)',
                 'borderLeft': '3px solid #ff8c00'},
                {'if': {'filter_query': '{Score} < 0.5'},
                'backgroundColor': 'rgba(255,215,0,0.03)',
                'borderLeft': '3px solid #ffd700'},
                # Score 컬럼 컬러
                {'if': {'column_id': 'Score', 'filter_query': '{Score} >= 0.7'},
                 'color': '#ff2d2d', 'fontWeight': '500'},
                {'if': {'column_id': 'Score', 'filter_query': '{Score} >= 0.5 && {Score} < 0.7'},
                 'color': '#ff8c00', 'fontWeight': '500'},
                {'if': {'column_id': 'Score', 'filter_query': '{Score} < 0.5'},
                 'color': '#ffd700', 'fontWeight': '500'},
                # Level1 신뢰도 강조
                {'if': {'column_id': '신뢰도', 'filter_query': '{신뢰도} = "Level1"'},
                 'color': '#4a9eff'},
                 # 기존 코드 마지막에 추가
                {'if': {'state': 'active'},
                'backgroundColor': 'rgba(168,85,247,0.2)',
                'border': '1px solid rgba(168,85,247,0.5)'},
            ],
            style_as_list_view=True,
            cell_selectable=False, 
            sort_action='native', page_size=50
        )
    ], style={'padding': '8px 16px'})


if __name__ == '__main__':
    app.run(debug=True, port=8050, dev_tools_ui=False)
>>>>>>> origin/dashboard
