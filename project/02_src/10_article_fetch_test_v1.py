"""
10_article_fetch_test.py  (1단계: 기사 본문 가져오기 — 표본 테스트)
----------------------------------------------------------------------
각 사건의 SOURCEURL에서 기사 제목·본문을 확보한다.
  1순위: 원본 URL 직접 시도 (살아있으면 사용)
  2순위: 원본이 죽었으면 웨이백 머신 보존본 시도
  3순위: 둘 다 없으면 'UNVERIFIED'

이 스크립트는 표본(기본 10개)으로 "본문 추출이 제대로 되는지" 확인용.
전체 배치는 추출 품질 확인 후 별도로 진행.

사용:
  python 10_article_fetch_test.py
  python 10_article_fetch_test.py --sample 15
"""

import sys
import time
import argparse
import requests
import pandas as pd
from bs4 import BeautifulSoup

EVENTS_CSV = "project/01_data/processed/events_filtered.csv"
WAYBACK_API = "http://archive.org/wayback/available"
DELAY_SEC = 1.0
TIMEOUT = 15
HEADERS = {"User-Agent": "Mozilla/5.0 (research; contact: team)"}
MIN_BODY_LEN = 200   # 본문이 이보다 짧으면 추출 실패로 간주


def get_wayback_url(url, event_date=None):
    """웨이백 보존본 URL 반환 (없으면 None)"""
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
    """URL에서 HTML 가져오기. (성공 시 html, 실패 시 None)"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200 and len(r.text) > 500:
            return r.text
    except Exception:
        pass
    return None


def extract_text(html):
    """HTML에서 제목 + 본문 추출 (간단 버전)"""
    soup = BeautifulSoup(html, "html.parser")
    # 제목: <title> 또는 og:title
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        title = og["content"].strip()
    # 본문: <p> 태그들을 모음 (간단 휴리스틱)
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    paras = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    body = " ".join(p for p in paras if len(p) > 40)  # 짧은 조각 제외
    return title, body


def process_one(url, event_date=None):
    """한 URL 처리: 원본 → 웨이백 순. 반환: dict"""
    # 1순위: 원본
    html = fetch_html(url)
    source = "original"
    used_url = url

    # 2순위: 웨이백
    if html is None:
        wb = get_wayback_url(url, event_date)
        if wb:
            html = fetch_html(wb)
            source = "wayback"
            used_url = wb

    # 3순위: 실패
    if html is None:
        return {"source": "none", "title": "", "body": "", "used_url": "",
                "ok": False}

    title, body = extract_text(html)
    ok = len(body) >= MIN_BODY_LEN
    return {"source": source, "title": title, "body": body,
            "used_url": used_url, "ok": ok}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=10)
    args = parser.parse_args()

    df = pd.read_csv(EVENTS_CSV)
    if "SOURCEURL" not in df.columns:
        print("✗ SOURCEURL 컬럼 없음")
        sys.exit(1)

    sub = df[df["SOURCEURL"].notna()].copy()
    n = min(args.sample, len(sub))
    sample = sub.sample(n=n, random_state=42)

    print(f"표본 {n}개로 기사 본문 추출 테스트\n" + "=" * 60)

    counts = {"original": 0, "wayback": 0, "none": 0}
    ok_count = 0

    for i, (_, row) in enumerate(sample.iterrows(), 1):
        url = str(row["SOURCEURL"]).strip()
        ev_date = None
        if "SQLDATE" in row:
            try:
                ev_date = pd.to_datetime(row["SQLDATE"]).strftime("%Y%m%d")
            except Exception:
                pass

        res = process_one(url, ev_date)
        counts[res["source"]] += 1
        if res["ok"]:
            ok_count += 1

        print(f"\n[{i}/{n}] 출처: {res['source']} | 본문추출: {'성공' if res['ok'] else '실패/부족'}")
        print(f"  원본 URL: {url[:70]}")
        if res["source"] != "none":
            print(f"  제목: {res['title'][:80]}")
            print(f"  본문 길이: {len(res['body'])}자")
            print(f"  본문 앞부분: {res['body'][:150]}...")
        time.sleep(DELAY_SEC)

    print("\n" + "=" * 60)
    print("결과 요약:")
    print(f"  원본에서 직접 확보: {counts['original']}/{n}")
    print(f"  웨이백에서 복원:    {counts['wayback']}/{n}")
    print(f"  확보 실패(UNVERIFIED): {counts['none']}/{n}")
    print(f"  본문 추출 성공(200자+): {ok_count}/{n}")
    print("\n다음 단계 가이드:")
    print("  본문 추출 성공률이 높으면 → 2단계(LLM 코드 검증)로")
    print("  제목/본문이 엉뚱하거나 짧으면 → 추출 로직(extract_text) 보완 필요")


if __name__ == "__main__":
    main()