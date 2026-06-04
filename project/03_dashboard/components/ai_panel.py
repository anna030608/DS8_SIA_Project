from dash import html, dcc
import pandas as pd
from components.helpers import CAMEO_DESC, get_alert_level, get_sensor_recommendation, sensor_label, estimate_swath
from components.data_loader import df_passes, df_sat_info
import os
import re
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini 클라이언트 초기화
client = None
if GEMINI_API_KEY:
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini 초기화 실패: {e}")

# ── 추천 질문 목록 ────────────────────────────────────────
SUGGESTED_QUESTIONS = [
    "해당 이벤트에 대한 기본 정보를 알려줘",
    "유사한 과거 사례가 있어?",
    "위성 촬영 권고사항은?",
    "중국 PLA의 예상 반응 패턴은?",
]


def _build_context(selected_event, selected_satellite, cloud_data):
    """이벤트 + 위성 정보를 텍스트로 정리"""
    if not selected_event:
        return ""

    code = selected_event.get('event_code', '')
    title, desc = CAMEO_DESC.get(code, (f'이벤트 {code}', '분류되지 않은 이벤트'))
    alert, _ = get_alert_level(selected_event['score'])

    context = f"""
[현재 선택된 이벤트 정보]
- 날짜: {selected_event['date']}
- 위치: ({selected_event['lat']:.4f}, {selected_event['lon']:.4f})
- 이벤트 유형: {title} ({desc})
- CAMEO 코드: {code}
- Priority Score: {selected_event['score']:.3f} ({alert})
- 기사 수: {selected_event['num_mentions']}건
"""

    # 위성 정보 추가
    if selected_satellite:
        passes = df_passes[
            (df_passes['SQLDATE'].dt.strftime('%Y-%m-%d') == selected_event['date']) &
            (df_passes['event_lat'] == selected_event['lat']) &
            (df_passes['event_lon'] == selected_event['lon']) &
            (df_passes['satellite_name'] == selected_satellite)
        ]
        if len(passes) > 0:
            sat_row = passes.iloc[0]
            sat_detail = df_sat_info[df_sat_info['NORAD_CAT_ID'] == int(sat_row['norad_id'])]
            if len(sat_detail) > 0:
                r = sat_detail.iloc[0]
                s_type  = r['sensor_type']     if pd.notna(r.get('sensor_type'))     else 'EO'
                alt     = round(float(r['APOAPSIS'])) if pd.notna(r.get('APOAPSIS')) else 500
                country = r['COUNTRY_CODE']    if pd.notna(r.get('COUNTRY_CODE'))    else 'N/A'
                purpose = r['Detailed Purpose'] if pd.notna(r.get('Detailed Purpose')) else None
                swath   = estimate_swath(s_type, purpose, alt)
                cloud_cover = cloud_data['cloud_cover'] if cloud_data else None
                rec_text, _ = get_sensor_recommendation(cloud_cover, s_type)
                context += f"""
[선택된 위성 정보]
- 위성명: {selected_satellite}
- NORAD ID: {int(sat_row['norad_id'])}
- 국가: {country}
- 센서: {sensor_label(s_type)}
- 고도: {alt}km
- 촬영 폭: {swath}km
- 최근접 거리: {sat_row['min_dist_km']:.1f}km
- 구름량: {cloud_cover}%
- 센서 추천: {rec_text}
"""
    return context


def _build_prompt(question, context, chat_history):
    """Gemini 프롬프트 구성"""
    history_text = ""
    for msg in chat_history[-6:]:  # 최근 6개만 유지
        role = "분석관" if msg['role'] == 'user' else "AI"
        history_text += f"{role}: {msg['content']}\n"

    return f"""당신은 양안관계 전문 군사 정보 분석 AI입니다.
분석관의 의사결정을 돕기 위해 정확하고 간결하게 답변하세요.

{context}

[대화 기록]
{history_text}

[분석관 질문]
{question}

답변 지침:
- 한국어로 답변
- 군사적/정치적 맥락을 포함
- "해당 이벤트에 대한 기본 정보를 알려줘" 질문 시: 위험도 평가, 사건 내용, 과거 유사 사례, 위성 촬영 권고사항 순으로 답변
- 근거 없는 추측 금지
- 300자 이내로 핵심만 답변
- 불필요한 배경 설명 생략
"""


def generate_response(question, selected_event, selected_satellite, cloud_data, chat_history):
    """Gemini API 호출"""
    if not client:
        return "GEMINI_API_KEY가 설정되지 않았습니다.", False

    context = _build_context(selected_event, selected_satellite, cloud_data)
    prompt  = _build_prompt(question, context, chat_history)

    import time
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            return response.text, True
        except Exception as e:
            if '503' in str(e) and attempt < 2:
                time.sleep(3)
                continue
            return f"오류: {str(e)}", False


def _render_message(msg):
    """채팅 메시지 버블 렌더링"""
    is_user = msg['role'] == 'user'

    if is_user:
        return html.Div(
            msg['content'],
            style={
                'backgroundColor': 'rgba(168,85,247,0.2)',
                'border': '1px solid rgba(168,85,247,0.4)',
                'borderRadius': '12px 12px 2px 12px',
                'padding': '8px 12px',
                'fontSize': '12px', 'color': 'white',
                'marginBottom': '8px',
                'marginLeft': '20px',
                'textAlign': 'right',
            }
        )
    else:
        # AI 답변 마크다운 처리
        lines = msg['content'].split('\n')
        rendered = []
                for line in lines:
                    raw = line.strip()
                    if not raw:
                        continue
                    if re.match(r'^(##|###|\d+\.)\s', raw):
                        clean = re.sub(r'^(##|###|\d+\.)\s*', '', raw).replace('**', '')
                        rendered.append(html.Div(clean, style={
                            'color': '#a855f7', 'fontWeight': 'bold',
                            'fontSize': '12px',
                            'marginTop': '12px', 'marginBottom': '6px',
                            'borderLeft': '3px solid #a855f7',
                            'paddingLeft': '8px', 'paddingBottom': '2px'
                        }))
                    elif raw.startswith('- ') or raw.startswith('* '):
                        clean = re.sub(r'\*\*(.*?)\*\*', r'\1', raw[2:])
                        label, _, value = clean.partition(':')
                        if value:
                            rendered.append(html.Div([
                                html.Span(label + ': ', style={'color': '#aaa', 'fontWeight': '500'}),
                                html.Span(value.strip(), style={'color': 'white'})
                            ], style={'fontSize': '11px', 'lineHeight': '2.0',
                                      'marginBottom': '4px', 'paddingLeft': '8px'}))
                        else:
                            rendered.append(html.Div(f"• {clean}", style={
                                'color': '#ddd', 'fontSize': '11px',
                                'lineHeight': '2.0', 'marginBottom': '4px', 'paddingLeft': '8px'
                            }))
                    else:
                        clean = re.sub(r'\*\*(.*?)\*\*', r'\1', raw)
                        rendered.append(html.Div(clean, style={
                            'color': '#ddd', 'fontSize': '11px',
                            'lineHeight': '2.0', 'marginBottom': '4px'
                        }))

        return html.Div([
            html.Div("🤖 AI", style={'fontSize': '10px', 'color': '#a855f7',
                                     'marginBottom': '4px', 'fontWeight': 'bold'}),
            html.Div(rendered)
        ], style={
            'backgroundColor': 'rgba(255,255,255,0.04)',
            'border': '1px solid rgba(255,255,255,0.08)',
            'borderRadius': '2px 12px 12px 12px',
            'padding': '8px 12px',
            'marginBottom': '8px',
            'marginRight': '20px',
        })


def render_ai(selected_event, selected_satellite, cloud_data, chat_history):
    header = html.Div("💬 AI 분석 챗봇",
                      style={'fontSize': '12px', 'color': '#aaa', 'fontWeight': 'bold',
                             'marginBottom': '12px', 'textTransform': 'uppercase'})

    if not selected_event:
        return [
            header,
            html.Div("📍 이벤트를 먼저 선택하세요.",
                     style={'color': '#666', 'fontSize': '12px',
                            'textAlign': 'center', 'padding': '40px 20px'})
        ]

    code = selected_event.get('event_code', '')
    title, _ = CAMEO_DESC.get(code, (f'이벤트 {code}', ''))
    alert, color = get_alert_level(selected_event['score'])

    # 이벤트 요약 카드
    event_card = html.Div([
        html.Div(f"⚠ {alert} ALERT",
                 style={'color': color, 'fontSize': '11px', 'fontWeight': 'bold', 'marginBottom': '4px'}),
        html.Div(title,
                 style={'color': 'white', 'fontSize': '13px', 'fontWeight': '500', 'marginBottom': '4px'}),
        html.Div(f"📅 {selected_event['date']} | Score: {selected_event['score']:.3f}",
                 style={'color': '#888', 'fontSize': '11px'}),
    ], style={
        'borderLeft': f'3px solid {color}',
        'backgroundColor': f'{color}15',
        'padding': '10px 12px', 'borderRadius': '4px', 'marginBottom': '12px'
    })

    # 채팅 히스토리
    chat_messages = []
    if chat_history:
        for msg in chat_history:
            chat_messages.append(_render_message(msg))

    chat_area = html.Div(
        chat_messages if chat_messages else [
            html.Div("아래 추천 질문을 클릭하거나 직접 입력하세요.",
                     style={'color': '#555', 'fontSize': '11px',
                            'textAlign': 'center', 'padding': '20px 0'})
        ],
        id='chat-messages',
        style={
            'minHeight': '100px',
            'maxHeight': '300px',
            'overflowY': 'auto',
            'marginBottom': '12px',
        }
    )

    # 추천 질문 버튼 (히스토리 없을 때만 표시)
    suggested = []
    if not chat_history:
        suggested = [
            html.Div("💡 추천 질문",
                     style={'fontSize': '11px', 'color': '#aaa', 'marginBottom': '6px'}),
            *[html.Button(
                q,
                id={'type': 'suggested-question', 'index': i},
                n_clicks=0,
                style={
                    'display': 'block', 'width': '100%',
                    'padding': '7px 10px', 'marginBottom': '4px',
                    'backgroundColor': 'rgba(168,85,247,0.08)',
                    'border': '1px solid rgba(168,85,247,0.25)',
                    'borderRadius': '4px', 'color': '#c084fc',
                    'fontSize': '11px', 'cursor': 'pointer',
                    'textAlign': 'left',
                }
            ) for i, q in enumerate(SUGGESTED_QUESTIONS)],
            html.Div(style={'marginBottom': '8px'})
        ]

    # 입력창
    input_area = html.Div([
        dcc.Input(
            id='chat-input',
            type='text',
            placeholder='질문을 입력하세요...',
            debounce=False,
            n_submit=0,
            style={
                'flex': 1, 'backgroundColor': '#1a2035', 'color': 'white',
                'border': '1px solid rgba(168,85,247,0.3)',
                'borderRadius': '4px 0 0 4px', 'padding': '8px 10px',
                'fontSize': '12px',
            }
        ),
        html.Button(
            "전송",
            id='btn-chat-send',
            n_clicks=0,
            style={
                'padding': '8px 12px',
                'backgroundColor': 'rgba(168,85,247,0.3)',
                'border': '1px solid rgba(168,85,247,0.5)',
                'borderLeft': 'none',
                'borderRadius': '0 4px 4px 0',
                'color': '#c084fc', 'fontSize': '12px', 'cursor': 'pointer',
            }
        ),
    ], style={'display': 'flex', 'marginBottom': '4px'})

    # 대화 초기화 버튼
    reset_btn = html.Button(
        "🔄 대화 초기화",
        id='btn-chat-reset',
        n_clicks=0,
        style={
            'fontSize': '10px', 'color': '#555',
            'backgroundColor': 'transparent', 'border': 'none',
            'cursor': 'pointer', 'padding': '2px 0',
        }
    )

    return [header, event_card, chat_area, *suggested, input_area, reset_btn]
