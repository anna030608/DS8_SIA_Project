from dash import html, dcc
import requests
from bs4 import BeautifulSoup
from components.helpers import CAMEO_DESC, get_alert_level, get_sensor_recommendation
from components.data_loader import df_passes, df_sat_info
from components.helpers import sensor_label, estimate_swath
import pandas as pd
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


def _crawl_article(url):
    """기사 크롤링 시도. 실패 시 None 반환."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(res.text, 'html.parser')
        # 본문 텍스트 추출 (p 태그 기준)
        paragraphs = soup.find_all('p')
        text = ' '.join(p.get_text() for p in paragraphs[:10])
        return text.strip() if len(text) > 100 else None
    except Exception:
        return None


def _build_prompt(selected_event, selected_satellite, cloud_data, article_text):
    code = selected_event.get('event_code', '')
    title, desc = CAMEO_DESC.get(code, (f'이벤트 {code}', '분류되지 않은 이벤트'))
    alert, _ = get_alert_level(selected_event['score'])

    # 위성 정보
    sat_section = "위성 정보 없음"
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
                s_type = r['sensor_type'] if pd.notna(r.get('sensor_type')) else 'EO'
                alt = round(float(r['APOAPSIS'])) if pd.notna(r.get('APOAPSIS')) else 500
                country = r['COUNTRY_CODE'] if pd.notna(r.get('COUNTRY_CODE')) else 'N/A'
                purpose = r['Detailed Purpose'] if pd.notna(r.get('Detailed Purpose')) else None
                swath = estimate_swath(s_type, purpose, alt)
                cloud_cover = cloud_data['cloud_cover'] if cloud_data else None
                rec_text, _ = get_sensor_recommendation(cloud_cover, s_type)
                sat_section = f"""
- 위성명: {selected_satellite}
- NORAD ID: {int(sat_row['norad_id'])}
- 국가: {country}
- 센서: {sensor_label(s_type)}
- 고도: {alt}km
- 촬영 예상 폭: {swath}km
- 최근접 거리: {sat_row['min_dist_km']:.1f}km
- 구름량: {cloud_cover}%
- 센서 추천: {rec_text}
"""

    # 기사 섹션
    if article_text:
        article_section = f"[기사 내용]\n{article_text[:1000]}"
    else:
        article_section = f"[기사 크롤링 실패 - CAMEO 코드 기반 분석]\nCAMEO 코드 {code}: {title} - {desc}"

    prompt = f"""
당신은 양안관계 전문 군사 정보 분석관입니다.
아래 이벤트 정보를 바탕으로 의사결정 지원 보고서를 작성하세요.

## 이벤트 정보
- 날짜: {selected_event['date']}
- 위치: ({selected_event['lat']:.4f}, {selected_event['lon']:.4f})
- 이벤트 유형: {title} ({desc})
- Priority Score: {selected_event['score']:.3f} ({alert})
- 기사 수: {selected_event['num_mentions']}건

{article_section}

## 위성 자산
{sat_section}

## 보고서 작성 지침
다음 4개 섹션으로 작성하세요. 각 섹션은 분석관의 즉각적인 의사결정에 도움이 되도록 간결하고 명확하게 작성하세요.

1. **위험도 평가**: Priority Score, 이벤트 유형, 기사 수를 종합한 위협 수준 평가 (2~3문장)
2. **사건 내용**: 이벤트의 군사적/정치적 맥락과 양안관계에 미치는 영향 (3~4문장)
3. **위성 촬영 권고**: 선택된 위성의 촬영 가능 여부, 센서 추천 이유, 최적 촬영 시기 (2~3문장)
4. **촬영 주문 정보**: 아래 형식으로 정리
   - 위성명: 
   - NORAD ID: 
   - 촬영 좌표: 
   - 촬영 일시: 
   - 권장 센서: 
   - 특이사항: 

한국어로 작성하세요.
"""
    return prompt


def generate_report(selected_event, selected_satellite, cloud_data):
    """Gemini API 호출하여 보고서 생성."""
    import time

    if not GEMINI_API_KEY:
        return None, "GEMINI_API_KEY가 설정되지 않았습니다.", False

    # 기사 크롤링 시도
    source_url = None
    try:
        from components.data_loader import df
        mask = (
            (df['SQLDATE'].dt.strftime('%Y-%m-%d') == selected_event['date']) &
            (df['ActionGeo_Lat'] == selected_event['lat']) &
            (df['ActionGeo_Long'] == selected_event['lon'])
        )
        row = df[mask].iloc[0]
        source_url = row['SOURCEURL']
    except Exception:
        pass

    article_text = _crawl_article(source_url) if source_url else None
    crawled = article_text is not None

    prompt = _build_prompt(selected_event, selected_satellite, cloud_data, article_text)

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            return response.text, None, crawled
        except Exception as e:
            if '503' in str(e) and attempt < 2:
                time.sleep(3)
                continue
            return None, str(e), crawled


def render_ai(selected_event, selected_satellite, cloud_data, report_data):
    header = html.Div("💬 AI 분석 보고서",
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

    # 보고서 생성 버튼
    btn = html.Button(
        "🔍 보고서 생성",
        id='btn-generate-report',
        n_clicks=0,
        style={
            'width': '100%', 'padding': '10px',
            'backgroundColor': 'rgba(168,85,247,0.2)',
            'border': '1px solid rgba(168,85,247,0.5)',
            'borderRadius': '4px', 'color': '#a855f7',
            'fontSize': '12px', 'cursor': 'pointer',
            'marginBottom': '12px', 'letterSpacing': '0.5px'
        }
    )

    # 보고서 내용
    report_content = []
    if report_data:
        if report_data.get('error'):
            report_content = [html.Div(f"⚠ 오류: {report_data['error']}",
                                       style={'color': '#ff2d2d', 'fontSize': '12px'})]
        elif report_data.get('loading'):
            report_content = [html.Div("⏳ 보고서 생성 중...",
                                       style={'color': '#aaa', 'fontSize': '12px',
                                              'textAlign': 'center', 'padding': '20px'})]
        else:
            # 크롤링 여부 표시
            crawl_badge = html.Span(
                "📰 기사 기반" if report_data.get('crawled') else "📋 CAMEO 코드 기반",
                style={
                    'fontSize': '10px',
                    'color': '#00ff88' if report_data.get('crawled') else '#ff8c00',
                    'border': f"1px solid {'#00ff88' if report_data.get('crawled') else '#ff8c00'}",
                    'borderRadius': '3px', 'padding': '1px 6px', 'marginBottom': '8px',
                    'display': 'inline-block'
                }
            )
            # 보고서 텍스트 렌더링
            import re
            report_lines = report_data['text'].split('\n')
            report_divs = []
            for line in report_lines:
                raw = line.strip()
                if not raw:
                    continue

                # ## 헤딩 또는 숫자. 로 시작하는 섹션 제목
                if re.match(r'^(##|###|\d+\.)\s', raw):
                    clean = re.sub(r'^(##|###|\d+\.)\s*', '', raw).replace('**', '')
                    report_divs.append(html.Div(clean, style={
                        'color': '#a855f7', 'fontWeight': 'bold',
                        'fontSize': '13px', 'marginTop': '14px', 'marginBottom': '6px',
                        'borderBottom': '1px solid rgba(168,85,247,0.2)', 'paddingBottom': '4px'
                    }))

                # - 로 시작하는 리스트 항목
                elif raw.startswith('- ') or raw.startswith('* '):
                    clean = re.sub(r'\*\*(.*?)\*\*', r'\1', raw[2:])
                    label, _, value = clean.partition(':')
                    if value:
                        report_divs.append(html.Div([
                            html.Span(label + ': ', style={'color': '#aaa', 'fontWeight': '500'}),
                            html.Span(value.strip(), style={'color': 'white'})
                        ], style={'fontSize': '11px', 'lineHeight': '1.8', 'marginBottom': '2px',
                                  'paddingLeft': '8px'}))
                    else:
                        report_divs.append(html.Div(f"• {clean}", style={
                            'color': '#ddd', 'fontSize': '11px',
                            'lineHeight': '1.8', 'marginBottom': '2px', 'paddingLeft': '8px'
                        }))

                # 일반 텍스트 (** 제거)
                else:
                    clean = re.sub(r'\*\*(.*?)\*\*', r'\1', raw)
                    report_divs.append(html.Div(clean, style={
                        'color': '#ddd', 'fontSize': '11px',
                        'lineHeight': '1.8', 'marginBottom': '4px'
                    }))

            report_content = [
                crawl_badge,
                html.Div(report_divs, style={
                    'backgroundColor': 'rgba(168,85,247,0.05)',
                    'border': '1px solid rgba(168,85,247,0.2)',
                    'borderRadius': '4px', 'padding': '12px', 'marginTop': '8px'
                })
            ]

    return [header, event_card, btn, dcc.Loading(
        id='loading-report',
        type='circle',
        color='#a855f7',
        children=html.Div(report_content, id='report-content')
    )]