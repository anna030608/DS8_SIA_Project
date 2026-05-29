import base64
from dash import html
import dash_leaflet as dl
import pandas as pd
from components.data_loader import df
from components.helpers import CAMEO_DESC, get_alert_level


def render_markers(date_range, geo_levels, score_min, selected_event):
    dff = df.copy()
    if date_range:
        dff = dff[dff['SQLDATE'].dt.date >= pd.to_datetime(date_range['start']).date()]
        dff = dff[dff['SQLDATE'].dt.date <= pd.to_datetime(date_range['end']).date()]
    if geo_levels:
        dff = dff[dff['geo_level'].isin(geo_levels)]
    dff = dff[dff['priority_score'] >= score_min]

    markers = []
    for _, row in dff.iterrows():
        score = row['priority_score']
        _, color = get_alert_level(score)
        opacity = 1.0 if row['geo_level'] == 'Level1' else 0.5
        code = str(int(row['EventCode']))
        title, _ = CAMEO_DESC.get(code, (f'이벤트 {code}', ''))
        size = int(20 + score * 16)

        is_selected = (
            selected_event and
            selected_event['date'] == row['SQLDATE'].strftime('%Y-%m-%d') and
            selected_event['lat'] == row['ActionGeo_Lat'] and
            selected_event['lon'] == row['ActionGeo_Long']
        )
        if is_selected:
            size += 8

        h = int(size * 1.4)
        svg = f'''<svg width="{size}" height="{h}" viewBox="0 0 30 42" xmlns="http://www.w3.org/2000/svg" opacity="{opacity}">
            <path d="M15 0 C6.716 0 0 6.716 0 15 C0 26 15 42 15 42 C15 42 30 26 30 15 C30 6.716 23.284 0 15 0 Z" fill="{color}"/>
            <circle cx="15" cy="15" r="6" fill="rgba(0,0,0,0.3)"/>
        </svg>'''
        svg_b64 = base64.b64encode(svg.encode()).decode()

        markers.append(dl.Marker(
            position=[row['ActionGeo_Lat'], row['ActionGeo_Long']],
            icon={
                'iconUrl': f"data:image/svg+xml;base64,{svg_b64}",
                'iconSize': [size, h],
                'iconAnchor': [size // 2, h]
            },
            id={'type': 'event-marker', 'index': int(row.name)},
            children=dl.Tooltip(
                f"{title} | {row['SQLDATE'].strftime('%Y-%m-%d')} | Score: {score:.3f}"
            )
        ))

    return markers


def render_overlay(date_range, geo_levels, score_min):
    dff = df.copy()
    if date_range:
        dff = dff[dff['SQLDATE'].dt.date >= pd.to_datetime(date_range['start']).date()]
        dff = dff[dff['SQLDATE'].dt.date <= pd.to_datetime(date_range['end']).date()]
    if geo_levels:
        dff = dff[dff['geo_level'].isin(geo_levels)]
    dff = dff[dff['priority_score'] >= score_min]

    total    = len(dff)
    max_score = f"{dff['priority_score'].max():.3f}" if total > 0 else "N/A"
    lv1 = (dff['geo_level'] == 'Level1').sum()
    lv2 = (dff['geo_level'] == 'Level2').sum()

    return html.Div([html.Div([
        html.Div([html.Div("총 이벤트",  style={'fontSize': '10px', 'color': '#888'}),
                  html.Div(f"{total}건", style={'fontSize': '16px', 'fontWeight': '500', 'color': 'white'})],
                 style={'textAlign': 'center'}),
        html.Div([html.Div("최고 Score",  style={'fontSize': '10px', 'color': '#888'}),
                  html.Div(max_score,     style={'fontSize': '16px', 'fontWeight': '500', 'color': '#ff8c00'})],
                 style={'textAlign': 'center'}),
        html.Div([html.Div("Level1",      style={'fontSize': '10px', 'color': '#888'}),
                  html.Div(f"{lv1}건",   style={'fontSize': '16px', 'fontWeight': '500', 'color': '#4a9eff'})],
                 style={'textAlign': 'center'}),
        html.Div([html.Div("Level2",      style={'fontSize': '10px', 'color': '#888'}),
                  html.Div(f"{lv2}건",   style={'fontSize': '16px', 'fontWeight': '500', 'color': '#aaa'})],
                 style={'textAlign': 'center'}),
    ], style={
        'display': 'flex', 'gap': '20px', 'padding': '8px 16px',
        'backgroundColor': 'rgba(10,14,26,0.85)',
        'border': '1px solid rgba(255,140,0,0.5)', 'borderRadius': '6px'
    })])
