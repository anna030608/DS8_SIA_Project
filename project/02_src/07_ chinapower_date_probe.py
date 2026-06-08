"""
07d_chinapower_date_probe.py
----------------------------------------------------------------------
Check WHERE the publication date lives in a ChinaPower article's HTML,
so we can extract it reliably during re-ingestion.

Fetches ONE page, prints date-related meta/time tags. Read-only.

Needs: requests, beautifulsoup4 (already installed).
"""

import requests
from bs4 import BeautifulSoup

# a known cross-strait article (has a clear date)
URL = "https://chinapower.csis.org/china-taiwan-joint-sword-2024b-coast-guard/"

r = requests.get(URL, timeout=30, headers={"User-Agent": "research-probe"})
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")

print("=== <meta> tags mentioning date/time/published ===")
for m in soup.find_all("meta"):
    key = (m.get("property") or m.get("name") or "").lower()
    if any(w in key for w in ("date", "time", "publish", "modified")):
        print(f"  {m.get('property') or m.get('name')} = {m.get('content')}")

print("\n=== <time> tags ===")
for t in soup.find_all("time"):
    print(f"  datetime={t.get('datetime')}  text={t.get_text(strip=True)[:60]}")

print("\n(위에서 'article:published_time' 또는 datetime 값이 보이면 그걸 쓰면 됩니다)")