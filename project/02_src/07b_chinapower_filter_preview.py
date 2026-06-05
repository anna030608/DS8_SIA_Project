"""
07b_chinapower_filter_preview.py
----------------------------------------------------------------------
Preview which ChinaPower URLs a Taiwan / cross-strait keyword filter keeps.

Same idea as the AMTI preview: fetch ONLY the sitemap (one request), no page
downloads, so it's fast. Use it to check the keyword set and the count BEFORE
the slow full ingestion.

Run locally.  Needs: requests, lxml  (already installed).
"""

import re
import requests
from urllib.parse import urlparse
from lxml import etree

SITEMAP_URL = "https://chinapower.csis.org/sitemap-1.xml"   # the article urlset

# Goal = China–Taiwan (cross-strait) relations, so keywords lean that way.
# Broad on purpose; we review the kept list and trim afterwards.
KEYWORDS = [
    "taiwan",
    "cross-strait",
    "strait",
    "pla",            # People's Liberation Army
    "adiz",
    "reunification",
    "one-china",
    "tsai",           # Tsai Ing-wen
    "invasion",
    "blockade",
]
# slug tokens that usually signal a DIFFERENT topic — reported, not auto-dropped.
OTHER_HINTS = ["philippines", "vietnam", "india", "japan-", "korea", "trade-war", "economy"]


def fetch_urls(sitemap_url: str) -> list[str]:
    r = requests.get(sitemap_url, timeout=30, headers={"User-Agent": "research-preview"})
    r.raise_for_status()
    root = etree.fromstring(r.content)
    return [loc.text.strip() for loc in root.iter() if loc.tag.endswith("loc") and loc.text]


def slug(url: str) -> str:
    return urlparse(url).path.lower()


def main() -> None:
    urls = fetch_urls(SITEMAP_URL)
    print(f"total URLs in sitemap: {len(urls)}\n")

    pat = re.compile("|".join(re.escape(k) for k in KEYWORDS))
    kept = sorted({u for u in urls if pat.search(slug(u))})   # set() dedups repeats
    print(f"kept by filter (deduped): {len(kept)}  (≈ {len(kept)*10/60:.0f} min to ingest @10s/page)\n")

    print("--- KEPT (review for false positives) ---")
    for u in kept:
        flag = " <-- maybe off-topic" if any(h in slug(u) for h in OTHER_HINTS) else ""
        print(slug(u) + flag)

    dropped = sorted({u for u in urls if u not in set(kept)})
    print(f"\n--- DROPPED sample ({min(30, len(dropped))} of {len(dropped)}) ---")
    for u in dropped[:30]:
        print(slug(u))


if __name__ == "__main__":
    main()