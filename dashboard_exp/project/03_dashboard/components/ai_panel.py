from dash import html


def render_ai():
    return [
        html.Div("💬 AI 분석 인사이트",
                 style={'fontSize': '12px', 'color': '#aaa', 'fontWeight': 'bold',
                        'marginBottom': '12px', 'textTransform': 'uppercase'}),
        html.Div("Gemini API 연동 예정",
                 style={'color': '#666', 'fontSize': '12px',
                        'textAlign': 'center', 'padding': '40px 20px'})
    ]
