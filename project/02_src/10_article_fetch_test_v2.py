"""
10_article_fetch_test_v2.py  (1단계 개선판: 기사 본문 가져오기)
----------------------------------------------------------------------
보완점:
  보완1) 원본이 200 응답이어도 "본문이 짧으면(MSN 등 JS 사이트)" 실패로 간주
         → 웨이백 머신을 시도. (이전엔 원본 200이면 무조건 성공 처리해 웨이백 안 거침)
  보완2) 결과를 상태로 명확히 분류:
         OK_ORIGINAL / OK_WAYBACK / EMPTY(JS 등 본문없음) / NOTFOUND(원본·웨이백 다 실패)

사용:
  python 10_article_fetch_test_v2.py
  python 10_article_fetch_test_v2.py --sample 15
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
MIN_BODY_LEN = 200   # 이보다 짧으면 추출 실패(빈 본문)로 간주


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


def try_extract(url):
    """URL 하나에서 (title, body) 추출 시도. 실패 시 ('', '')"""
    html = fetch_html(url)
    if html is None:
        return "", ""
    return extract_text(html)


def process_one(url, event_date=None):
    """
    원본 → (본문 부족하면) 웨이백 순.
    반환 status: OK_ORIGINAL / OK_WAYBACK / EMPTY / NOTFOUND
    """
    # 1) 원본 시도
    title, body = try_extract(url)
    if len(body) >= MIN_BODY_LEN:
        return {"status": "OK_ORIGINAL", "title": title, "body": body, "used_url": url}

    # 원본이 비었거나 부족 → 웨이백 시도 (보완1)
    original_had_response = bool(title or body)  # 응답은 왔으나 본문이 부족했는지
    wb = get_wayback_url(url, event_date)
    if wb:
        wt, wb_body = try_extract(wb)
        if len(wb_body) >= MIN_BODY_LEN:
            return {"status": "OK_WAYBACK", "title": wt, "body": wb_body, "used_url": wb}

    # 둘 다 본문 확보 실패
    if original_had_response:
        # 원본 응답은 왔지만 본문이 안 잡힘 (JS 렌더링 등) (보완2)
        return {"status": "EMPTY", "title": title, "body": body, "used_url": url}
    return {"status": "NOTFOUND", "title": "", "body": "", "used_url": ""}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=10)
    args = parser.parse_args()

    df = pd.read_csv(EVENTS_CSV)
    if "SOURCEURL" not in df.columns:
        print("✗ SOURCEURL 컬럼 없음"); sys.exit(1)

    sub = df[df["SOURCEURL"].notna()].copy()
    n = min(args.sample, len(sub))
    sample = sub.sample(n=n, random_state=42)  # 이전과 같은 표본(비교 위해)

    print(f"표본 {n}개로 기사 본문 추출 테스트 (개선판)\n" + "=" * 60)

    counts = {"OK_ORIGINAL": 0, "OK_WAYBACK": 0, "EMPTY": 0, "NOTFOUND": 0}

    for i, (_, row) in enumerate(sample.iterrows(), 1):
        url = str(row["SOURCEURL"]).strip()
        ev_date = None
        if "SQLDATE" in row:
            try:
                ev_date = pd.to_datetime(row["SQLDATE"]).strftime("%Y%m%d")
            except Exception:
                pass

        res = process_one(url, ev_date)
        counts[res["status"]] += 1

        ok = res["status"].startswith("OK")
        print(f"\n[{i}/{n}] 상태: {res['status']} | {'✓' if ok else '✗'}")
        print(f"  원본 URL: {url[:70]}")
        if ok:
            print(f"  제목: {res['title'][:80]}")
            print(f"  본문 길이: {len(res['body'])}자")
            print(f"  본문 앞부분: {res['body'][:150]}...")
        time.sleep(DELAY_SEC)

    print("\n" + "=" * 60)
    print("결과 요약:")
    print(f"  OK_ORIGINAL (원본 본문 확보): {counts['OK_ORIGINAL']}/{n}")
    print(f"  OK_WAYBACK  (웨이백 복원):    {counts['OK_WAYBACK']}/{n}")
    print(f"  EMPTY       (응답왔으나 본문없음, JS 등): {counts['EMPTY']}/{n}")
    print(f"  NOTFOUND    (원본·웨이백 다 실패):       {counts['NOTFOUND']}/{n}")
    total_ok = counts['OK_ORIGINAL'] + counts['OK_WAYBACK']
    print(f"\n  본문 확보 성공: {total_ok}/{n}  ({total_ok/n*100:.0f}%)")
    print("\n신뢰도 등급 매핑 (다음 단계):")
    print("  OK_ORIGINAL/OK_WAYBACK → 2단계 LLM 검증 대상 (HIGH/MEDIUM/LOW 판정)")
    print("  EMPTY / NOTFOUND       → UNVERIFIED (본문 확보 불가)")


if __name__ == "__main__":
    main()