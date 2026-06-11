"""
12_reliability_batch.py  (3단계: 신뢰도 검증 전체 배치)
----------------------------------------------------------------------
사건별로 본문 확보(원본→웨이백) + LLM 코드 검증 → 신뢰도 등급을 산출해
CSV에 저장한다. 긴 작업이므로 다음 안전장치를 갖춤:

  ① 웨이백 재시도 (archive.org 불안정 대비)
  ② 중간 저장 / 재개 — 이미 처리한 사건은 건너뜀 (끊겨도 이어서)
  ③ 상위 사건 우선 (priority_score 내림차순)
  ④ --limit 로 1회 실행 호출 수 제한 (무료 한도 보호, 며칠 분할 가능)

사용:
  python 12_reliability_batch.py --limit 100      # 이번에 100건만
  python 12_reliability_batch.py --limit 100      # 다시 = 다음 100건 (이어서)
  python 12_reliability_batch.py --limit 0        # 제한 없이 전부

출력: project/01_data/processed/event_reliability.csv
  컬럼: GLOBALEVENTID(또는 행키), status, verdict, grade, title, reason, used_url
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
OUT_CSV = "project/01_data/processed/event_reliability.csv"
WAYBACK_API = "http://archive.org/wayback/available"
DELAY_SEC = 2.0          # archive.org 예의상 간격 (표본보다 늘림)
WAYBACK_RETRY = 2        # 웨이백 재시도 횟수
TIMEOUT = 15
HEADERS = {"User-Agent": "Mozilla/5.0 (research; contact: team)"}
MIN_BODY_LEN = 200
GEMINI_MODEL = "gemini-2.5-flash-lite"

CAMEO_TEXT = {
    "150": "군사 태세(military posturing)", "151": "경계 수준 강화(increase alert status)",
    "152": "군사력 증강(military exercise/buildup)", "153": "군사 순찰 증가(increase military patrol)",
    "154": "군사 동원·증강(mobilization/buildup)", "190": "재래식 무력 사용(use conventional force)",
    "191": "봉쇄·이동제한(blockade/restrict movement)", "192": "영토 점령(occupy territory)",
    "193": "소형화기 충돌(small-arms clash)", "194": "중화기 무력충돌(armed clash, heavy weapons)",
    "195": "공중무기 사용(air weapons)", "196": "정전 위반(ceasefire violation)",
    "200": "대규모 폭력(mass violence)", "201": "대규모 추방(mass expulsion)",
    "202": "대량 살상(mass killing)",
}


def get_wayback_url(url, event_date=None):
    params = {"url": url}
    if event_date:
        params["timestamp"] = event_date
    for attempt in range(WAYBACK_RETRY + 1):
        try:
            r = requests.get(WAYBACK_API, params=params, timeout=TIMEOUT)
            snap = r.json().get("archived_snapshots", {}).get("closest")
            if snap and snap.get("available"):
                return snap.get("url")
            return None  # 응답은 정상인데 보존본 없음 → 재시도 무의미
        except Exception:
            if attempt < WAYBACK_RETRY:
                time.sleep(2)
                continue
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
    html = fetch_html(url)
    had_response = False
    if html:
        t, b = extract_text(html)
        if len(b) >= MIN_BODY_LEN:
            return "OK_ORIGINAL", t, b, url
        had_response = bool(t or b)
    wb = get_wayback_url(url, event_date)
    if wb:
        h2 = fetch_html(wb)
        if h2:
            t2, b2 = extract_text(h2)
            if len(b2) >= MIN_BODY_LEN:
                return "OK_WAYBACK", t2, b2, wb
    return ("EMPTY" if had_response else "NOTFOUND"), "", "", ""


_client = None


def get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def verify_with_llm(title, body, code):
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
- "MATCH": 기사가 양안 군사 사건이며 분류 유형과 부합
- "MISMATCH": 기사가 양안 군사 사건이 아니거나 분류 유형과 명백히 다름
- "AMBIGUOUS": 양안 관련이긴 하나 유형이 정확히 맞는지 애매

반드시 아래 JSON 형식으로만 답하세요 (다른 텍스트 없이):
{{"verdict": "MATCH|MISMATCH|AMBIGUOUS", "reason": "한 문장 근거"}}"""
    for attempt in range(3):
        try:
            resp = get_client().models.generate_content(
                model=GEMINI_MODEL, contents=prompt
            )
            text = resp.text.strip().replace("```json", "").replace("```", "").strip()
            data = json.loads(text)
            return data.get("verdict", "AMBIGUOUS"), data.get("reason", "")
        except Exception as e:
            if "503" in str(e) and attempt < 2:
                time.sleep(3)
                continue
            return "ERROR", f"{e}"


def map_grade(status, verdict):
    if status in ("EMPTY", "NOTFOUND"):
        return "UNVERIFIED"
    if verdict == "MATCH":
        return "HIGH" if status == "OK_ORIGINAL" else "MEDIUM"
    if verdict == "MISMATCH":
        return "LOW"
    if verdict == "AMBIGUOUS":
        return "MEDIUM"
    return "UNVERIFIED"


def make_key(row):
    """사건 식별키: GLOBALEVENTID 있으면 그것, 없으면 날짜+좌표+코드"""
    if "GLOBALEVENTID" in row and pd.notna(row["GLOBALEVENTID"]):
        return str(int(row["GLOBALEVENTID"]))
    return f"{row['SQLDATE']}_{row['ActionGeo_Lat']}_{row['ActionGeo_Long']}_{row['EventCode']}"


def load_done_keys():
    """이미 처리한 사건 키 (재개용)"""
    if os.path.exists(OUT_CSV):
        try:
            done = pd.read_csv(OUT_CSV, dtype={"event_key": str})
            return set(done["event_key"].astype(str)), done
        except Exception:
            pass
    return set(), pd.DataFrame()


def append_result(record):
    """결과 1건을 즉시 CSV에 append (끊겨도 안전)"""
    df_one = pd.DataFrame([record])
    header = not os.path.exists(OUT_CSV)
    df_one.to_csv(OUT_CSV, mode="a", header=header, index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100,
                        help="이번 실행에서 처리할 최대 건수 (0=무제한)")
    args = parser.parse_args()

    if not GEMINI_API_KEY:
        print("✗ GEMINI_API_KEY 없음"); sys.exit(1)

    df = pd.read_csv(EVENTS_CSV)
    df = df[df["SOURCEURL"].notna()].copy()
    # 상위 사건 우선
    if "priority_score" in df.columns:
        df = df.sort_values("priority_score", ascending=False)

    done_keys, _ = load_done_keys()
    print(f"전체 대상: {len(df)} | 이미 처리: {len(done_keys)} | "
          f"이번 한도: {'무제한' if args.limit == 0 else args.limit}")
    print("=" * 60)

    processed = 0
    grade_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNVERIFIED": 0}

    for _, row in df.iterrows():
        key = make_key(row)
        if key in done_keys:
            continue
        if args.limit and processed >= args.limit:
            break

        url = str(row["SOURCEURL"]).strip()
        code = row.get("EventCode", "")
        try:
            code = str(int(code))
        except Exception:
            code = str(code)
        ev_date = None
        try:
            ev_date = pd.to_datetime(row["SQLDATE"]).strftime("%Y%m%d")
        except Exception:
            pass

        status, title, body, used = get_article(url, ev_date)
        if status in ("EMPTY", "NOTFOUND"):
            verdict, reason = "-", "본문 확보 실패"
        else:
            verdict, reason = verify_with_llm(title, body, code)
        grade = map_grade(status, verdict)
        grade_counts[grade] = grade_counts.get(grade, 0) + 1

        append_result({
            "event_key": key, "SQLDATE": row.get("SQLDATE"),
            "EventCode": code, "status": status, "verdict": verdict,
            "grade": grade, "title": title[:200], "reason": reason[:300],
            "used_url": used[:300], "source_url": url[:300],
        })

        processed += 1
        print(f"[{processed}] {grade:10s} | {status:11s} | {verdict:10s} | {title[:45]}")
        time.sleep(DELAY_SEC)

    print("=" * 60)
    print(f"이번 실행 처리: {processed}건")
    print("이번 실행 등급 분포:")
    for g in ("HIGH", "MEDIUM", "LOW", "UNVERIFIED"):
        print(f"  {g}: {grade_counts.get(g, 0)}")
    print(f"\n누적 결과 저장: {OUT_CSV}")
    print("한도에 걸렸으면 같은 명령을 다시 실행하면 이어서 처리됩니다.")


if __name__ == "__main__":
    main()