from dash import dcc, html
import dash_leaflet as dl
from components.data_loader import DATE_MIN, DATE_MAX


def create_layout():
    return html.Div([

        dcc.Store(id='selected-event', data=None),
        dcc.Store(id='selected-satellite', data=None),
        dcc.Store(id='active-panel', data='feed'),
        dcc.Store(id='go-to-satellite', data=False),
        dcc.Store(id='cloud-data', data=None),
        dcc.Store(id='date-range', data={
            'start': str(DATE_MIN), 'end': str(DATE_MAX)
        }),
        dcc.Store(id='report-data', data=None),

        # ── 타이틀 바 ─────────────────────────────────────
        html.Div([
            html.Div([
                html.Span("🛰️", style={'marginRight': '8px'}),
                html.Span("양안관계 OSINT-GEOINT 의사결정 지원 시스템",
                         style={'fontSize': '16px', 'fontWeight': '500', 'color': 'white'})
            ], style={'display': 'flex', 'alignItems': 'center'}),
            html.Div([
                html.Button("📡 FEED",   id='btn-feed',      n_clicks=0, style={'marginRight': '6px'}),
                html.Button("🛰️ 위성",   id='btn-satellite', n_clicks=0, style={'marginRight': '6px'}),
                html.Button("💬 AI",     id='btn-ai',        n_clicks=0),
                html.Span("Operation Control Room | SIA Wevengers",
                         style={'fontSize': '11px', 'color': '#555', 'marginLeft': '20px'})
            ], style={'display': 'flex', 'alignItems': 'center'})
        ], style={
            'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center',
            'padding': '10px 20px', 'backgroundColor': '#0a0e1a',
            'borderBottom': '1px solid rgba(255,140,0,0.3)',
            'position': 'sticky', 'top': 0, 'zIndex': 1000
        }),

        # ── 필터 바 ───────────────────────────────────────
        html.Div([
            # 기간
            html.Div([
                html.Label("기간", style={'fontSize': '12px', 'color': '#aaa',
                                        'fontWeight': 'bold', 'marginRight': '8px',
                                        'whiteSpace': 'nowrap', 'lineHeight': '28px'}),
                html.Button("3개월", id='btn-period-3m', n_clicks=0,
                            style={'marginRight': '4px', 'fontSize': '11px', 'padding': '3px 10px'}),
                html.Button("6개월", id='btn-period-6m', n_clicks=0,
                            style={'marginRight': '4px', 'fontSize': '11px', 'padding': '3px 10px'}),
                html.Button("1년",   id='btn-period-1y', n_clicks=0,
                            style={'marginRight': '4px', 'fontSize': '11px', 'padding': '3px 10px'}),
                html.Button("전체",  id='btn-period-all', n_clicks=0,
                            style={'marginRight': '12px', 'fontSize': '11px', 'padding': '3px 10px'}),
                dcc.Input(id='input-start-date', type='text', placeholder='YYYY-MM-DD',
                          value=str(DATE_MIN), debounce=True,
                          style={'backgroundColor': '#1a2035', 'color': 'white',
                                 'border': '1px solid rgba(255,255,255,0.2)',
                                 'borderRadius': '4px', 'padding': '3px 6px',
                                 'fontSize': '11px', 'marginRight': '4px', 'width': '90px'}),
                html.Span("~", style={'color': '#aaa', 'marginRight': '4px', 'lineHeight': '28px'}),
                dcc.Input(id='input-end-date', type='text', placeholder='YYYY-MM-DD',
                          value=str(DATE_MAX), debounce=True,
                          style={'backgroundColor': '#1a2035', 'color': 'white',
                                 'border': '1px solid rgba(255,255,255,0.2)',
                                 'borderRadius': '4px', 'padding': '3px 6px',
                                 'fontSize': '11px', 'width': '90px'}),
                html.Div(id='date-range-display', style={'display': 'none'}),
            ], style={'display': 'flex', 'alignItems': 'center', 'marginRight': '24px', 'height': '32px'}),

            # 좌표 신뢰도
            html.Div([
                html.Label("좌표 신뢰도", style={'fontSize': '12px', 'color': '#aaa',
                                            'fontWeight': 'bold', 'marginRight': '8px',
                                            'whiteSpace': 'nowrap', 'lineHeight': '28px'}),
                dcc.Checklist(id='geo-level',
                              options=[{'label': ' Level1', 'value': 'Level1'},
                                       {'label': ' Level2', 'value': 'Level2'}],
                              value=['Level1', 'Level2'], inline=True,
                              labelStyle={'color': 'white', 'marginRight': '12px', 'fontSize': '12px'}),
                html.Span(" ⓘ L1 = 특정 지역 좌표 L2 = 대표 좌표",
                          style={'fontSize': '10px', 'color': '#555', 'marginLeft': '4px', 'whiteSpace': 'nowrap'})
            ], style={'display': 'flex', 'alignItems': 'center', 'marginRight': '24px', 'height': '32px'}),

            # Priority Score 최솟값
            html.Div([
                html.Label("Priority Score 최솟값",
                           style={'fontSize': '12px', 'color': '#aaa', 'fontWeight': 'bold',
                                  'marginRight': '8px', 'whiteSpace': 'nowrap', 'lineHeight': '28px'}),
                html.Div([
                    dcc.Slider(id='score-slider', min=0, max=1, step=0.05, value=0.4,
                               marks=None, tooltip=None)
                ], style={'flex': 1, 'minWidth': '200px'}),
                html.Span(id='score-display',
                          style={'fontSize': '12px', 'color': '#a855f7', 'fontWeight': '300',
                                 'marginLeft': '8px', 'whiteSpace': 'nowrap', 'lineHeight': '28px'}),
            ], style={'display': 'flex', 'alignItems': 'center', 'flex': 1, 'height': '32px'}),

        ], style={
            'display': 'flex', 'alignItems': 'center', 'flexWrap': 'nowrap',
            'padding': '0 20px', 'backgroundColor': '#111827',
            'borderBottom': '1px solid rgba(255,255,255,0.05)',
            'position': 'sticky', 'top': '48px', 'zIndex': 999,
            'overflowX': 'auto', 'height': '48px'
        }),

        # ── 지도 + 사이드 패널 ────────────────────────────
        html.Div([
            html.Div([
                dl.Map(
                    id='main-map', center=[25.0, 121.5], zoom=5,
                    children=[
                        dl.TileLayer(
                            url='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                            attribution='Esri World Imagery'
                        ),
                        dl.LayerGroup(id='event-markers'),
                        dl.LayerGroup(id='orbit-layer'),
                        dl.LayerGroup(id='median-line'),
                    ],
                    style={'height': '100%', 'width': '100%'}
                ),
                html.Div(id='map-overlay', style={
                    'position': 'absolute', 'top': '10px', 'left': '50px',
                    'zIndex': 500, 'pointerEvents': 'none'
                }),
            ], style={'position': 'absolute', 'inset': 0}),

            html.Div(
                id='side-panel',
                children=[html.Div(id='panel-content')],
                style={
                    'position': 'absolute', 'top': 0, 'right': 0, 'bottom': 0,
                    'width': '300px', 'backgroundColor': 'rgba(10,14,26,0.95)',
                    'borderLeft': '1px solid rgba(255,255,255,0.1)',
                    'overflowY': 'auto', 'padding': '12px', 'zIndex': 500
                }
            )
        ], style={'position': 'relative', 'height': '80vh', 'width': '100%'}),

        # ── 하단 섹션 ─────────────────────────────────────
        html.Div([
            dcc.Tabs(id='bottom-tabs', value='timeseries', children=[
                dcc.Tab(label='📈 시계열 분석', value='timeseries',
                        style={'backgroundColor': '#111827', 'color': '#aaa', 'border': 'none'},
                        selected_style={'backgroundColor': '#0a0e1a', 'color': 'white', 'border': 'none'}),
                dcc.Tab(label='📋 이벤트 상세', value='events',
                        style={'backgroundColor': '#111827', 'color': '#aaa', 'border': 'none'},
                        selected_style={'backgroundColor': '#0a0e1a', 'color': 'white', 'border': 'none'}),
            ], style={'backgroundColor': '#111827'}),
            html.Div(id='bottom-content')
        ], style={
            'width': '100%', 'backgroundColor': '#0a0e1a',
            'borderTop': '1px solid rgba(255,255,255,0.1)',
        }),

        # ── Footer ───────────────────────────────────────
        html.Div(
            "본 사이트는 SIA와 모두의 연구소의 협력을 통한 교육과정에서 제작된 결과물입니다.",
            style={
                'textAlign': 'center',
                'fontSize': '11px',
                'color': '#444',
                'padding': '12px',
                'borderTop': '1px solid rgba(255,255,255,0.05)',
                'backgroundColor': '#0a0e1a',
            }
        ),

    ], style={'backgroundColor': '#0a0e1a', 'fontFamily': 'sans-serif', 'minHeight': '100vh'})
