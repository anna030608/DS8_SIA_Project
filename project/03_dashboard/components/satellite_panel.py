from dash import html
import pandas as pd
from components.data_loader import df_passes, df_sat_info
from components.helpers import (
    sensor_label, estimate_swath,
    get_sensor_recommendation
)


def render_satellite(selected_event, selected_satellite, cloud_data):
    if not selected_event:
        return [
            html.Div("🛰️ 위성 자산 운용",
                     style={'fontSize': '12px', 'color': '#aaa', 'fontWeight': 'bold',
                            'marginBottom': '12px'}),
            html.Div("📍 지도에서 이벤트를 클릭하면\n근접 위성 정보가 표시됩니다.",
                     style={'color': '#666', 'fontSize': '12px', 'textAlign': 'center',
                            'padding': '40px 20px', 'whiteSpace': 'pre-line'})
        ]

    event_date = selected_event['date']
    event_lat  = selected_event['lat']
    event_lon  = selected_event['lon']

    passes = df_passes[
        (df_passes['SQLDATE'].dt.strftime('%Y-%m-%d') == event_date) &
        (df_passes['event_lat'] == event_lat) &
        (df_passes['event_lon'] == event_lon)
    ].sort_values('min_dist_km').drop_duplicates(subset='satellite_name').reset_index(drop=True)

    sat_items = []

    # ── 선택된 위성 상세 카드 ─────────────────────────────
    if selected_satellite:
        sel = passes[passes['satellite_name'] == selected_satellite]
        if len(sel) > 0:
            sat_row = sel.iloc[0]
            sat_detail = df_sat_info[df_sat_info['NORAD_CAT_ID'] == int(sat_row['norad_id'])]
            if len(sat_detail) > 0:
                r = sat_detail.iloc[0]
                s_type  = r['sensor_type']        if pd.notna(r.get('sensor_type'))        else 'EO'
                alt     = round(float(r['APOAPSIS'])) if pd.notna(r.get('APOAPSIS'))       else 500
                country = r['COUNTRY_CODE']        if pd.notna(r.get('COUNTRY_CODE'))       else 'N/A'
                purpose = r['Detailed Purpose']    if pd.notna(r.get('Detailed Purpose'))   else None
            else:
                s_type, alt, country, purpose = 'EO', 500, 'N/A', None

            swath = estimate_swath(s_type, purpose, alt)
            cloud_cover = cloud_data['cloud_cover'] if cloud_data else None
            rec_text, rec_color = get_sensor_recommendation(cloud_cover, s_type)

            sat_items.append(html.Div([
                html.Div("🛰️ 선택된 위성 정보",
                         style={'color': '#00ff88', 'fontSize': '11px',
                                'fontWeight': 'bold', 'marginBottom': '6px'}),
                html.Div(selected_satellite,
                         style={'color': 'white', 'fontSize': '13px',
                                'fontWeight': '500', 'marginBottom': '6px'}),
                html.Div([
                    html.Span(sensor_label(s_type),
                              style={'background': 'rgba(74,158,255,0.2)',
                                     'border': '1px solid #4a9eff', 'borderRadius': '3px',
                                     'padding': '1px 6px', 'fontSize': '10px',
                                     'color': '#4a9eff', 'marginRight': '6px'}),
                    html.Span(str(country),
                              style={'background': 'rgba(255,255,255,0.1)', 'borderRadius': '3px',
                                     'padding': '1px 6px', 'fontSize': '10px', 'color': '#aaa'})
                ], style={'marginBottom': '8px'}),
                html.Div(f"NORAD ID: {int(sat_row['norad_id'])}",
                         style={'fontSize': '11px', 'color': '#aaa', 'marginBottom': '2px'}),
                html.Div(f"고도: {alt}km",
                         style={'fontSize': '11px', 'color': '#aaa', 'marginBottom': '2px'}),
                html.Div([html.Span("촬영 예상 폭: ", style={'color': '#aaa'}),
                          html.Span(f"{swath}km (추정)", style={'color': '#00ff88', 'fontWeight': '500'})],
                         style={'fontSize': '11px', 'marginBottom': '2px'}),
                html.Div([html.Span("최근접 거리: ", style={'color': '#aaa'}),
                          html.Span(f"{sat_row['min_dist_km']:.1f}km", style={'color': '#00ff88', 'fontWeight': '500'})],
                         style={'fontSize': '11px', 'marginBottom': '2px'}),
                html.Div(f"이벤트 날짜: {event_date}",
                         style={'fontSize': '11px', 'color': '#aaa', 'marginBottom': '2px'}),
                html.Div(f"이벤트 좌표: ({event_lat:.4f}, {event_lon:.4f})",
                         style={'fontSize': '11px', 'color': '#aaa'}),

                html.Div(style={'borderTop': '1px solid rgba(255,255,255,0.1)', 'margin': '8px 0'}),

                html.Div("🌤 촬영 환경",
                         style={'color': '#aaa', 'fontSize': '11px',
                                'fontWeight': 'bold', 'marginBottom': '6px'}),
                html.Div([
                    html.Span("구름량: ", style={'color': '#aaa'}),
                    html.Span(f"{cloud_cover}%" if cloud_cover is not None else "조회 실패",
                              style={'color': 'white', 'fontWeight': '500'})
                ], style={'fontSize': '11px', 'marginBottom': '4px'}),
                html.Div([
                    html.Span("센서 추천: ", style={'color': '#aaa'}),
                    html.Span(rec_text if rec_text else "N/A",
                              style={'color': rec_color, 'fontWeight': '500'})
                ], style={'fontSize': '11px', 'marginBottom': '4px'}),
                html.Div([
                    html.Div(style={
                        'height': '4px',
                        'width': f"{cloud_cover}%" if cloud_cover is not None else "0%",
                        'backgroundColor': rec_color,
                        'borderRadius': '2px', 'transition': 'width 0.3s'
                    })
                ], style={
                    'height': '4px', 'backgroundColor': 'rgba(255,255,255,0.1)',
                    'borderRadius': '2px', 'marginBottom': '4px'
                }),
            ], style={
                'background': 'rgba(0,255,136,0.05)',
                'border': '1px solid rgba(0,255,136,0.3)',
                'borderRadius': '6px', 'padding': '10px', 'marginBottom': '8px'
            }))

    # ── 근접 위성 목록 ────────────────────────────────────
    if len(passes) > 0:
        sat_items.append(html.Div(f"근접 위성 {len(passes)}개 탐지",
                                  style={'color': '#aaa', 'fontSize': '11px', 'marginBottom': '6px'}))
        for _, sat in passes.head(10).iterrows():
            is_sel = selected_satellite == sat['satellite_name']
            color  = '#ff8c00' if is_sel else '#4a9eff'
            bg     = 'rgba(255,140,0,0.1)' if is_sel else 'rgba(255,255,255,0.04)'
            sat_items.append(html.Div([
                html.Div(sat['satellite_name'],
                         style={'color': 'white', 'fontSize': '12px', 'fontWeight': '500'}),
                html.Div([html.Span("최근접 거리: ", style={'color': '#888'}),
                          html.Span(f"{sat['min_dist_km']:.1f}km", style={'color': color})],
                         style={'fontSize': '10px'})
            ], id={'type': 'sat-item', 'name': sat['satellite_name']},
               style={'borderLeft': f'3px solid {color}', 'backgroundColor': bg,
                      'padding': '8px 10px', 'marginBottom': '4px',
                      'borderRadius': '4px', 'cursor': 'pointer'}))
    else:
        sat_items.append(html.Div("해당 이벤트의 근접 위성 정보가 없습니다.",
                                  style={'color': '#666', 'fontSize': '12px', 'padding': '10px 0'}))

    return [
        html.Div("🛰️ 위성 자산 운용",
                 style={'fontSize': '12px', 'color': '#aaa', 'fontWeight': 'bold',
                        'marginBottom': '12px', 'textTransform': 'uppercase'}),
        *sat_items
    ]
