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
from components.ai_panel import render_ai, generate_response, generate_report, SUGGESTED_QUESTIONS


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
    Input('report-data', 'data'),
    Input('chat-history', 'data'),
)

def update_panel(active_panel, selected_event, selected_satellite,
                 date_range, geo_levels, score_min, cloud_data, report_data, chat_history):
    if active_panel == 'feed':
        return render_feed(selected_event, date_range, geo_levels, score_min)
    elif active_panel == 'satellite':
        return render_satellite(selected_event, selected_satellite, cloud_data)
    elif active_panel == 'ai':
        return render_ai(selected_event, selected_satellite, cloud_data, chat_history, report_data)
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


# ── 콜백: 위성 선택 → 궤도 표시 ─────────────────────────
@app.callback(
    Output('selected-satellite', 'data'),
    Output('orbit-layer', 'children'),
    Input({'type': 'sat-item', 'name': dash.ALL}, 'n_clicks'),
    Input('selected-event', 'data'),
    prevent_initial_call=True
)
def select_satellite(n_clicks, selected_event):
    from dash import ctx

    # ── 이벤트가 바뀐 경우: 가장 가까운 위성 자동 선택 ──
    if ctx.triggered_id == 'selected-event':
        if not selected_event:
            return None, []
        nearest = _nearest_satellite(selected_event)
        if nearest is None:
            # 근접 위성이 없으면 이벤트 위치만 표시
            return None, [dl.CircleMarker(
                center=[selected_event['lat'], selected_event['lon']],
                radius=15, color='#ff2d2d', fillColor='#ff2d2d', fillOpacity=0.3
            )]
        return nearest, _build_orbit_layers(selected_event, nearest)

    # ── 위성을 직접 클릭한 경우: 그 위성으로 변경 ──
    if not ctx.triggered[0]['value'] or not selected_event:
        return dash.no_update, dash.no_update

    sat_name = ctx.triggered_id['name']
    return sat_name, _build_orbit_layers(selected_event, sat_name)


# ── 헬퍼: 그 사건의 가장 가까운 위성 이름 ──────────────────
def _nearest_satellite(selected_event):
    passes = df_passes[
        (df_passes['SQLDATE'].dt.strftime('%Y-%m-%d') == selected_event['date']) &
        (df_passes['event_lat'] == selected_event['lat']) &
        (df_passes['event_lon'] == selected_event['lon'])
    ].sort_values('min_dist_km')
    if len(passes) == 0:
        return None
    return passes.iloc[0]['satellite_name']


# ── 헬퍼: 이벤트 + 위성 궤도 레이어 생성 ──────────────────
def _build_orbit_layers(selected_event, sat_name):
    event_lat = selected_event['lat']
    event_lon = selected_event['lon']

    passes = df_passes[
        (df_passes['SQLDATE'].dt.strftime('%Y-%m-%d') == selected_event['date']) &
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

    return orbit_layers


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
        'num_mentions': int(row['NumMentions']),
        'quad_class': int(row['QuadClass']) if 'QuadClass' in row else 0,
        'actor1': row.get('Actor1Name', ''),
        'actor2': row.get('Actor2Name', ''),
        'reliability': row.get('reliability_grade', 'UNVERIFIED'),
        'reliability_reason': row.get('reliability_reason', ''),
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

# ── 콜백: 보고서 생성 ─────────────────────────────
@app.callback(
    Output('report-data', 'data'),
    Input('selected-event', 'data'),
    State('selected-satellite', 'data'),
    State('cloud-data', 'data'),
    prevent_initial_call=True
)
def generate_ai_report(selected_event, selected_satellite, cloud_data):
    if not selected_event:
        return dash.no_update
    text, error, crawled = generate_report(selected_event, selected_satellite, cloud_data)
    if error:
        return {'error': error}
    return {'text': text, 'crawled': crawled}


if __name__ == '__main__':
    app.run(debug=True, port=8050, dev_tools_ui=False)

@app.callback(
    Output('chat-history', 'data'),
    Output('chat-input', 'value'),
    Input('btn-chat-send', 'n_clicks'),
    Input({'type': 'suggested-question', 'index': dash.ALL}, 'n_clicks'),
    Input('btn-chat-reset', 'n_clicks'),
    State('chat-input', 'value'),
    State('chat-history', 'data'),
    State('selected-event', 'data'),
    State('selected-satellite', 'data'),
    State('cloud-data', 'data'),
    prevent_initial_call=True
)
def handle_chat(send_clicks, suggested_clicks, reset_clicks,
                input_value, chat_history, selected_event,
                selected_satellite, cloud_data):
    from dash import ctx
    if not ctx.triggered_id:
        return dash.no_update, dash.no_update
 
    chat_history = chat_history or []
 
    # 대화 초기화
    if ctx.triggered_id == 'btn-chat-reset':
        return [], ''
 
    # 추천 질문 클릭
    question = None
    if isinstance(ctx.triggered_id, dict) and ctx.triggered_id.get('type') == 'suggested-question':
        if ctx.triggered[0]['value']:
            idx = ctx.triggered_id['index']
            question = SUGGESTED_QUESTIONS[idx]
 
    # 전송 버튼 또는 직접 입력
    elif ctx.triggered_id == 'btn-chat-send':
        if not input_value or not input_value.strip():
            return dash.no_update, dash.no_update
        question = input_value.strip()
 
    if not question:
        return dash.no_update, dash.no_update
 
    # 사용자 메시지 추가
    chat_history.append({'role': 'user', 'content': question})
 
    # Gemini 호출
    answer, success = generate_response(
        question, selected_event, selected_satellite, cloud_data, chat_history
    )
 
    # AI 답변 추가
    chat_history.append({'role': 'assistant', 'content': answer})
 
    return chat_history, ''
