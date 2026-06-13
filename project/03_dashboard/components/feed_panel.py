from dash import html
import pandas as pd
from components.data_loader import df, df_passes
from components.helpers import CAMEO_DESC, get_alert_level

# 소스신뢰도 색상 (표·AI패널과 통일)
_GRADE_COLOR = {
    'HIGH':       '#22c55e',
    'MEDIUM':     '#eab308',
    'LOW':        '#ff2d2d',
    'UNVERIFIED': '#888888',
}

PAGE_SIZE = 3  # 한 페이지에 보여줄 피드 개수


def render_feed(selected_event, date_range, geo_levels, score_min, page=0):
    dff = df.copy()
    if date_range:
        dff = dff[dff['SQLDATE'].dt.date >= pd.to_datetime(date_range['start']).date()]
        dff = dff[dff['SQLDATE'].dt.date <= pd.to_datetime(date_range['end']).date()]
    if geo_levels:
        dff = dff[dff['geo_level'].isin(geo_levels)]
    dff = dff[dff['priority_score'] >= score_min]
    dff = dff.sort_values(['SQLDATE', 'priority_score'], ascending=[False, False]).head(30)

    # ── 페이지네이션 계산 ────────────────────────────────
    total = len(dff)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))  # 범위 보정
    start = page * PAGE_SIZE
    page_df = dff.iloc[start:start + PAGE_SIZE]

    feed_items = []
    for _, row in page_df.iterrows():
        code = str(int(row['EventCode']))
        alert, color = get_alert_level(row['priority_score'])
        title, desc = CAMEO_DESC.get(code, (f'이벤트 {code}', '분류되지 않은 이벤트'))

        grade = row.get('reliability_grade', 'UNVERIFIED')
        grade_color = _GRADE_COLOR.get(grade, '#888888')

        is_selected = (
            selected_event and
            selected_event['date'] == row['SQLDATE'].strftime('%Y-%m-%d') and
            selected_event['lat'] == row['ActionGeo_Lat'] and
            selected_event['lon'] == row['ActionGeo_Long']
        )

        card_children = [
            html.Div(f"⚠ {alert} ALERT",
                     style={'color': color, 'fontSize': '11px',
                            'fontWeight': 'bold', 'marginBottom': '4px'}),
            html.Div(title,
                     style={'color': 'white', 'fontSize': '13px',
                            'fontWeight': '500', 'marginBottom': '4px'}),
            html.Div(desc,
                     style={'color': '#aaa', 'fontSize': '11px', 'marginBottom': '6px'}),
            html.Div([
                html.Span(f"📅 {row['SQLDATE'].strftime('%Y-%m-%d')}"),
                html.Span(f" | 📰 {int(row['NumMentions'])}건"),
                html.Span(" | Score: ", style={'color': '#888'}),
                html.Span(f"{row['priority_score']:.3f}",
                          style={'color': color, 'fontWeight': '500'})
            ], style={'fontSize': '11px', 'color': '#888', 'marginBottom': '4px'}),
            html.Div([
                html.Span(f"📍 ({row['ActionGeo_Lat']:.2f}, {row['ActionGeo_Long']:.2f})",
                          style={'color': '#555', 'fontSize': '10px', 'marginRight': '8px'}),
                html.A("🔗 원문 보기", href=row['SOURCEURL'], target='_blank',
                       style={'fontSize': '11px', 'color': '#4a9eff', 'marginRight': '8px'}),
                html.Span(f"{grade}",
                          style={'fontSize': '10px', 'color': grade_color,
                                 'fontWeight': '500',
                                 'border': f'1px solid {grade_color}55',
                                 'backgroundColor': f'{grade_color}15',
                                 'borderRadius': '3px', 'padding': '1px 6px'})
            ], style={'display': 'flex', 'alignItems': 'center', 'flexWrap': 'wrap'})
        ]

        feed_items.append(html.Div([
            html.Div(
                card_children,
                id={'type': 'feed-item', 'index': int(row.name)},
                n_clicks=0,
                style={
                    'borderLeft': f'3px solid {color}',
                    'backgroundColor': 'rgba(255,255,255,0.13)' if is_selected else 'rgba(255,255,255,0.05)',
                    'boxShadow': f'0 0 12px {color}55' if is_selected else 'none',
                    'outline': f'1px solid {color}' if is_selected else 'none',
                    'padding': '10px 12px',
                    'borderRadius': '4px 4px 0 0' if is_selected else '4px',
                    'cursor': 'pointer',
                    'transition': 'all 0.2s',
                }
            ),
            html.Button(
                "🛰️ 위성 자산 확인 →",
                id={'type': 'go-satellite', 'index': int(row.name)},
                n_clicks=0,
                style={
                    'display': 'block' if is_selected else 'none',
                    'width': '100%', 'padding': '8px',
                    'backgroundColor': f'{color}22',
                    'border': 'none',
                    'borderTop': f'1px solid {color}44',
                    'borderRadius': '0 0 4px 4px',
                    'color': color,
                    'fontSize': '12px', 'cursor': 'pointer',
                    'textAlign': 'center', 'letterSpacing': '0.5px',
                }
            ),
        ], style={'marginBottom': '10px'}))

    # 필터 결과 0개
    if total == 0:
        feed_items = [html.Div(
            "조건에 맞는 이벤트가 없습니다. (기간·신뢰도·Score 필터를 확인하세요)",
            style={'color': '#666', 'fontSize': '12px', 'textAlign': 'center',
                   'padding': '40px 20px'}
        )]

    # ── 이전/다음 페이지네이션 컨트롤 ────────────────────
    prev_disabled = (page <= 0)
    next_disabled = (page >= total_pages - 1)

    def _nav_btn(label, btn_id, disabled):
        return html.Button(
            label, id=btn_id, n_clicks=0, disabled=disabled,
            style={
                'padding': '4px 14px', 'fontSize': '12px',
                'backgroundColor': 'rgba(168,85,247,0.08)' if disabled else 'rgba(168,85,247,0.25)',
                'border': '1px solid rgba(168,85,247,0.3)',
                'borderRadius': '4px',
                'color': '#555' if disabled else '#c084fc',
                'cursor': 'default' if disabled else 'pointer',
            }
        )

    pagination = html.Div([
        _nav_btn("◀ 이전", 'btn-feed-prev', prev_disabled),
        html.Span(f"{page + 1} / {total_pages}",
                  style={'fontSize': '12px', 'color': '#aaa', 'margin': '0 12px'}),
        _nav_btn("다음 ▶", 'btn-feed-next', next_disabled),
    ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center',
              'marginTop': '8px'}) if total > 0 else html.Div()

    return [
        html.Div("📡 실시간 OSINT FEED",
                 style={'fontSize': '12px', 'color': '#aaa', 'fontWeight': 'bold',
                        'marginBottom': '12px', 'textTransform': 'uppercase',
                        'letterSpacing': '1px'}),
        *feed_items,
        pagination,
    ]