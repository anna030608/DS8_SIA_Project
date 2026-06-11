"""
11_llm_code_verify_test.py  (2단계: LLM 코드 검증 — 표본 테스트)
----------------------------------------------------------------------
1단계로 확보한 기사 본문을, GDELT가 붙인 CAMEO 코드와 대조해
Gemini가 "일치 / 불일치 / 애매"를 판단한다.

신뢰도 등급 매핑:
  본문 확보 성공(OK) + 일치    → HIGH(원본) / MEDIUM(웨이백)
  본문 확보 성공(OK) + 불일치  → LOW
  본문 확보 성공(OK) + 애매    → MEDIUM
  본문 확보 실패(EMPTY/NOTFOUND) → UNVERIFIED (LLM 호출 안 함)

표본으로, 특히 무관 기사(도메인 바뀜·관광버스 등)가 LOW로 잡히는지 확인.

사용:
  python 11_llm_code_verify_test.py
  python 11_llm_code_verify_test.py --sample 10
"""

import os
import sys
import time
import json
import argparse
import requests
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

EVENTS_CSV = "project/01_data/processed/events_filtered.csv"
WAYBACK_API = "http://archive.org/wayback/available"
DELAY_SEC = 1.0
TIMEOUT = 15
HEADERS = {"User-Agent": "Mozilla/5.0 (research; contact: team)"}
MIN_BODY_LEN = 200
GEMINI_MODEL = "gemini-2.5-flash-lite"

# CAMEO 코드 → 의미 (검증용, 군사 관련 위주)
CAMEO_TEXT = {
    "150": "군사 태세(military posturing)",
    "151": "경계 수준 강화(increase alert status)",
    "152": "군사력 증강(military exercise/buildup)",
    "153": "군사 순찰 증가(increase military patrol)",
    "154": "군사 동원·증강(mobilization/buildup)",
    "190": "재래식 무력 사용(use conventional force)",
    "191": "봉쇄·이동제한(blockade/restrict movement)",
    "192": "영토 점령(occupy territory)",
    "193": "소형화기 충돌(small-arms clash)",
    "194": "중화기 무력충돌(armed clash, heavy weapons)",
    "195": "공중무기 사용(air weapons)",
    "196": "정전 위반(ceasefire violation)",
    "200": "대규모 폭력(mass violence)",
    "201": "대규모 추방(mass expulsion)",
    "202": "대량 살상(mass killing)",
}


# ── 1단계 로직 재사용 (본문 확보) ─────────────────────────
def get_wayback_url(url, event_date=None):
    params = {"url": url}
    if event_date:
        params["timestamp"] = event_date
    try:
        r = requests.get(WAYBACK_API, params=params, timeout=TIMEOUT)
        snap = r.json().get("archived_snapshots", {}).get("closest")
        if snap and snap.get("available"):
            return snap.get("url")
    except Exception:
        pass
    return None


def fetch_html(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200 and len(r.text) > 500:
            return r.text
    except Exception:
        pass
    return None


def extract_text(html):
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = og["content"].strip()
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    body = " ".join(p for p in paras if len(p) > 40)
    return title, body


def get_article(url, event_date=None):
    """본문 확보. 반환: (status, title, body)"""
    html = fetch_html(url)
    if html:
        t, b = extract_text(html)
        if len(b) >= MIN_BODY_LEN:
            return "OK_ORIGINAL", t, b
        had_response = bool(t or b)
    else:
        had_response = False

    wb = get_wayback_url(url, event_date)
    if wb:
        h2 = fetch_html(wb)
        if h2:
            t2, b2 = extract_text(h2)
            if len(b2) >= MIN_BODY_LEN:
                return "OK_WAYBACK", t2, b2

    return ("EMPTY" if had_response else "NOTFOUND"), "", ""


# ── 2단계: LLM 검증 ──────────────────────────────────────
_client = None


def get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def verify_with_llm(title, body, code):
    """기사가 CAMEO 코드와 맞는지 LLM 판단. 반환: (verdict, reason)"""
    code_text = CAMEO_TEXT.get(str(code), f"CAMEO {code}")
    prompt = f"""다음은 GDELT가 양안(중국-대만) 군사 사건으로 분류한 기사입니다.
이 기사가 분류된 사건 유형과 실제로 일치하는지 판단하세요.

[GDELT 분류 사건 유형]
CAMEO 코드 {code}: {code_text}

[기사 제목]
{title}

[기사 본문 (일부)]
{body[:1500]}

판단 기준:
- "MATCH": 기사 내용이 양안 군사 사건이며 분류 유형과 부합
- "MISMATCH": 기사가 양안 군사 사건이 아니거나(예: 코로나, 사고, 무관한 주제)
  분류 유형과 명백히 다름
- "AMBIGUOUS": 양안 관련이긴 하나 유형이 정확히 맞는지 애매

반드시 아래 JSON 형식으로만 답하세요 (다른 텍스트 없이):
{{"verdict": "MATCH|MISMATCH|AMBIGUOUS", "reason": "한 문장 근거"}}"""

    try:
        resp = get_client().models.generate_content(
            model=GEMINI_MODEL, contents=prompt
        )
        text = resp.text.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        return data.get("verdict", "AMBIGUOUS"), data.get("reason", "")
    except Exception as e:
        return "ERROR", f"{e}"


def map_grade(status, verdict):
    """본문 상태 + LLM 판정 → 신뢰도 등급"""
    if status in ("EMPTY", "NOTFOUND"):
        return "UNVERIFIED"
    if verdict == "MATCH":
        return "HIGH" if status == "OK_ORIGINAL" else "MEDIUM"
    if verdict == "MISMATCH":
        return "LOW"
    if verdict == "AMBIGUOUS":
        return "MEDIUM"
    return "UNVERIFIED"  # ERROR 등


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=10)
    args = parser.parse_args()

    if not GEMINI_API_KEY:
        print("✗ GEMINI_API_KEY 없음"); sys.exit(1)

    df = pd.read_csv(EVENTS_CSV)
    sub = df[df["SOURCEURL"].notna()].copy()
    n = min(args.sample, len(sub))
    sample = sub.sample(n=n, random_state=42)  # 1단계와 같은 표본

    print(f"표본 {n}개로 2단계 LLM 코드 검증\n" + "=" * 60)

    grade_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNVERIFIED": 0}

    for i, (_, row) in enumerate(sample.iterrows(), 1):
        url = str(row["SOURCEURL"]).strip()
        code = row.get("EventCode", "")
        try:
            code = str(int(code))
        except Exception:
            code = str(code)
        ev_date = None
        if "SQLDATE" in row:
            try:
                ev_date = pd.to_datetime(row["SQLDATE"]).strftime("%Y%m%d")
            except Exception:
                pass

        status, title, body = get_article(url, ev_date)

        if status in ("EMPTY", "NOTFOUND"):
            verdict, reason = "-", "본문 확보 실패"
        else:
            verdict, reason = verify_with_llm(title, body, code)

        grade = map_grade(status, verdict)
        grade_counts[grade] = grade_counts.get(grade, 0) + 1

        print(f"\n[{i}/{n}] CAMEO {code} | 본문:{status} | LLM:{verdict} → 등급:{grade}")
        print(f"  URL: {url[:65]}")
        if title:
            print(f"  제목: {title[:70]}")
        print(f"  근거: {reason}")
        time.sleep(DELAY_SEC)

    print("\n" + "=" * 60)
    print("신뢰도 등급 분포:")
    for g in ("HIGH", "MEDIUM", "LOW", "UNVERIFIED"):
        print(f"  {g}: {grade_counts.get(g, 0)}/{n}")
    print("\n확인 포인트:")
    print("  · 무관 기사(도메인 바뀜·관광버스 등)가 LOW로 잡혔나?")
    print("  · 양안 군사 기사(Pelosi·Joint Sword)가 HIGH/MEDIUM인가?")


if __name__ == "__main__":
    main()