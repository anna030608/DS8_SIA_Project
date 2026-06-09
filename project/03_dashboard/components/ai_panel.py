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

# ── 보고서 후속 추천 질문 (보고서 생성 후 1개) ───────────
SUGGESTED_QUESTIONS = [
    "이 위성 말고 다른 촬영 옵션은?",
]

def _build_context(selected_event, selected_satellite, cloud_data):
    """이벤트 + 위성 정보 + CSIS 분석을 텍스트로 정리"""
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
 
    # ── 이 사건의 위성 통과 후보 추리기 ──────────────────
    event_passes = df_passes[
        (df_passes['SQLDATE'].dt.strftime('%Y-%m-%d') == selected_event['date']) &
        (df_passes['event_lat'] == selected_event['lat']) &
        (df_passes['event_lon'] == selected_event['lon'])
    ].sort_values('min_dist_km')
 
    # 사용할 위성 결정: 분석관이 골랐으면 그것, 아니면 가장 가까운 것
    sat_name = None
    if selected_satellite:
        sat_name = selected_satellite
    elif len(event_passes) > 0:
        sat_name = event_passes.iloc[0]['satellite_name']
 
    # ── 위성 정보 추가 ──────────────────────────────────
    if sat_name:
        passes = event_passes[event_passes['satellite_name'] == sat_name]
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
                auto_note = "" if selected_satellite else " (가장 가까운 위성 자동 선택)"
                context += f"""
[촬영 위성 정보{auto_note}]
- 위성명: {sat_name}
- NORAD ID: {int(sat_row['norad_id'])}
- 국가: {country}
- 센서: {sensor_label(s_type)}
- 고도: {alt}km
- 촬영 폭: {swath}km
- 최근접 거리: {sat_row['min_dist_km']:.1f}km
- 구름량: {cloud_cover}%
- 센서 추천: {rec_text}
"""
 
    # ── 그 외 위성 후보 목록 ("다른 촬영 옵션" 질문 대비) ──
    others = event_passes[event_passes['satellite_name'] != sat_name]
    if len(others) > 0:
        context += "\n[그 외 근접 위성 후보]\n"
        for _, r in others.head(5).iterrows():
            context += f"- {r['satellite_name']} (최근접 {r['min_dist_km']:.1f}km)\n"
    else:
        # 후보가 없을 때 "없음"을 명시 → AI가 위성을 지어내지 않도록
        context += ("\n[그 외 근접 위성 후보] 없음. "
                    f"이 사건에 탐지된 근접 위성은 총 {len(event_passes)}개이며, "
                    "위에 명시된 위성 외 다른 촬영 옵션은 데이터에 없음.\n")
 
    # ── CSIS 분석 추가 (블록 1) ──────────────────────────
    try:
        from components.csis_rag import search_csis
        csis = search_csis({
            "SQLDATE": selected_event['date'],
            "EventCode": code,
            "QuadClass": selected_event.get('quad_class', 0),
            "Actor1Name": selected_event.get('actor1', ''),
            "Actor2Name": selected_event.get('actor2', ''),
        })
        if csis['outcome'] == 'DIRECT':
            context += "\n[CSIS 분석 — 이 사건을 직접 다룬 분석]\n"
        elif csis['outcome'] == 'CONTEXT':
            context += "\n[CSIS 분석 — 직접 분석은 없음, 유사 유형의 일반 맥락]\n"
        elif csis['outcome'] == 'NONE':
            context += "\n[CSIS 분석] 이 사건과 관련된 CSIS 분석을 찾지 못함.\n"
        for h in csis.get('hits', []):
            context += f"- {h['title']} ({h['time_note']})\n  {h['excerpt']}\n"
    except Exception as e:
        context += f"\n[CSIS 분석 조회 실패: {e}]\n"
 
    return context


def _build_report_prompt(context):
    return f"""당신은 양안관계 전문 군사 정보 분석 AI입니다.
아래 정보를 바탕으로 분석관의 위성 촬영 판단을 돕는 보고서를 작성하세요.

{context}

작성 지침:
- 한국어로, 아래 4개 섹션을 '## 제목' 형식으로 구분해 작성
- 각 섹션은 2~3문장으로 간결하게

## 사건 개요
언제·어디서·무슨 유형의 사건인지 (날짜·위치·이벤트 유형 기반)

## 전략적 의미
제공된 CSIS 분석을 근거로 이 사건의 전략적 함의를 설명.
CSIS 분석이 "직접 분석"이면 그 내용을 인용, "일반 맥락"이면 유사 사례로서
참고임을 명시, "찾지 못함"이면 관련 CSIS 분석이 없다고 솔직히 밝힐 것.
근거 없는 추측 금지.

## 촬영 우선순위
Priority Score와 그 의미(왜 이 점수인지) 기반의 촬영 필요성 평가

## 위성 촬영 권고
선택된 위성이 있으면 그 위성의 적합성(거리·센서·구름량)을, 없으면
"위성을 선택하면 촬영 권고를 제공할 수 있음"이라고 안내
"""


def generate_report(selected_event, selected_satellite, cloud_data):
    """이벤트 선택 시 4단락 기본 보고서 생성."""
    if not client:
        return "", "GEMINI_API_KEY가 설정되지 않았습니다.", []
    if not selected_event:
        return "", "선택된 이벤트가 없습니다.", []

    context = _build_context(selected_event, selected_satellite, cloud_data)
    prompt = _build_report_prompt(context)

    import time
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash', contents=prompt
            )
            return response.text, None, []
        except Exception as e:
            if '503' in str(e) and attempt < 2:
                time.sleep(3)
                continue
            return "", f"오류: {str(e)}", []


def _build_prompt(question, context, chat_history):
    """Gemini 프롬프트 구성 (추가 질문용)"""
    history_text = ""
    for msg in chat_history[-6:]:
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
- 위성 관련 질문에는 context의 '근접 위성' 정보(촬영 위성 정보 + 그 외 근접 위성 후보)만 사용할 것.
  데이터에 없는 위성(Capella, ICEYE 등 상업 위성 이름 포함)을 절대 지어내지 말 것.
  '그 외 근접 위성 후보'가 '없음'이면 "이 사건에 탐지된 근접 위성은 OO 하나뿐이며, 다른 촬영 옵션은 데이터에 없습니다"라고 솔직히 답할 것.
- 위성 관련 질문에는 CSIS 분석을 끌어오지 말 것 (위성 가용성과 무관함).
- CSIS 분석이 제공된 경우 그 내용을 근거로 인용하고, "분석을 찾지 못함"이면 솔직히 없다고 명시할 것 (지어내지 말 것).
- 근거 없는 추측 금지. context에 있는 데이터만으로 답할 것.
- 300자 이내로 핵심만 답변
- 불필요한 배경 설명 생략
"""


def generate_response(question, selected_event, selected_satellite, cloud_data, chat_history):
    """Gemini API 호출 (추가 질문용)"""
    if not client:
        return "GEMINI_API_KEY가 설정되지 않았습니다.", False

    context = _build_context(selected_event, selected_satellite, cloud_data)
    prompt  = _build_prompt(question, context, chat_history)

    import time
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash', contents=prompt
            )
            return response.text, True
        except Exception as e:
            if '503' in str(e) and attempt < 2:
                time.sleep(3)
                continue
            return f"오류: {str(e)}", False


def _render_markdown(text):
    """간단 마크다운 → Dash 컴포넌트 (## 제목, - 항목, 일반 텍스트)"""
    rendered = []
    for line in text.split('\n'):
        raw = line.strip()
        if not raw:
            rendered.append(html.Div(style={'height': '8px'}))
            continue
        if re.match(r'^(##|###|\d+\.)\s', raw):
            clean = re.sub(r'^(##|###|\d+\.)\s*', '', raw).replace('**', '')
            rendered.append(html.Div(clean, style={
                'color': '#a855f7', 'fontWeight': 'bold', 'fontSize': '12px',
                'marginTop': '12px', 'marginBottom': '6px',
                'borderLeft': '3px solid #a855f7',
                'paddingLeft': '8px', 'paddingBottom': '2px'
            }))
        elif raw.startswith('- ') or raw.startswith('* '):
            clean = re.sub(r'\*\*(.*?)\*\*', r'\1', raw[2:])
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
    return rendered


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
                'padding': '8px 12px', 'fontSize': '12px', 'color': 'white',
                'marginBottom': '8px', 'marginLeft': '20px', 'textAlign': 'right',
            }
        )
    return html.Div([
        html.Div("🤖 AI", style={'fontSize': '10px', 'color': '#a855f7',
                                 'marginBottom': '4px', 'fontWeight': 'bold'}),
        html.Div(_render_markdown(msg['content']))
    ], style={
        'backgroundColor': 'rgba(255,255,255,0.04)',
        'border': '1px solid rgba(255,255,255,0.08)',
        'borderRadius': '2px 12px 12px 12px',
        'padding': '8px 12px', 'marginBottom': '8px', 'marginRight': '20px',
    })


def render_ai(selected_event, selected_satellite, cloud_data, chat_history, report_data):
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

    # ── 보고서 영역 (자동 생성) ──────────────────────────
    if report_data and report_data.get('error'):
        report_block = html.Div(f"보고서 생성 오류: {report_data['error']}",
                                style={'color': '#ff8c00', 'fontSize': '11px',
                                       'padding': '10px 0'})
    elif report_data and report_data.get('text'):
        report_block = html.Div([
            html.Div("📋 분석 보고서", style={'fontSize': '11px', 'color': '#a855f7',
                                            'fontWeight': 'bold', 'marginBottom': '6px'}),
            html.Div(_render_markdown(report_data['text']))
        ], style={
            'backgroundColor': 'rgba(255,255,255,0.04)',
            'border': '1px solid rgba(255,255,255,0.08)',
            'borderRadius': '8px', 'padding': '10px 12px', 'marginBottom': '12px'
        })
    else:
        report_block = html.Div("보고서를 생성하는 중입니다...",
                                style={'color': '#666', 'fontSize': '11px',
                                       'textAlign': 'center', 'padding': '20px 0'})

    # 채팅 히스토리 (추가 질문/답변)
    chat_messages = [_render_message(m) for m in (chat_history or [])]
    chat_area = html.Div(
        chat_messages,
        id='chat-messages',
        style={'maxHeight': '250px', 'overflowY': 'auto',
               'marginBottom': '8px'} if chat_messages else {'display': 'none'}
    )

    # 후속 추천 질문 (보고서 뒤, 1개)
    suggested = []
    if not chat_history:
        suggested = [
            html.Div("💡 추가 질문", style={'fontSize': '11px', 'color': '#aaa', 'marginBottom': '6px'}),
            *[html.Button(
                q, id={'type': 'suggested-question', 'index': i}, n_clicks=0,
                style={
                    'display': 'block', 'width': '100%',
                    'padding': '7px 10px', 'marginBottom': '4px',
                    'backgroundColor': 'rgba(168,85,247,0.08)',
                    'border': '1px solid rgba(168,85,247,0.25)',
                    'borderRadius': '4px', 'color': '#c084fc',
                    'fontSize': '11px', 'cursor': 'pointer', 'textAlign': 'left',
                }
            ) for i, q in enumerate(SUGGESTED_QUESTIONS)],
            html.Div(style={'marginBottom': '8px'})
        ]

    # 입력창
    input_area = html.Div([
        dcc.Input(
            id='chat-input', type='text', placeholder='추가 질문을 입력하세요...',
            debounce=False, n_submit=0,
            style={
                'flex': 1, 'backgroundColor': '#1a2035', 'color': 'white',
                'border': '1px solid rgba(168,85,247,0.3)',
                'borderRadius': '4px 0 0 4px', 'padding': '8px 10px', 'fontSize': '12px',
            }
        ),
        html.Button(
            "전송", id='btn-chat-send', n_clicks=0,
            style={
                'padding': '8px 12px', 'backgroundColor': 'rgba(168,85,247,0.3)',
                'border': '1px solid rgba(168,85,247,0.5)', 'borderLeft': 'none',
                'borderRadius': '0 4px 4px 0', 'color': '#c084fc',
                'fontSize': '12px', 'cursor': 'pointer',
            }
        ),
    ], style={'display': 'flex', 'marginBottom': '4px'})

    reset_btn = html.Button(
        "🔄 대화 초기화", id='btn-chat-reset', n_clicks=0,
        style={'fontSize': '10px', 'color': '#555', 'backgroundColor': 'transparent',
               'border': 'none', 'cursor': 'pointer', 'padding': '2px 0'}
    )

    return [header, event_card, report_block, chat_area, *suggested, input_area, reset_btn]