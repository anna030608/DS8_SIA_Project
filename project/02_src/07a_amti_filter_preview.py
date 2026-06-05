"""
07a_amti_filter_preview.py
----------------------------------------------------------------------
Preview which AMTI URLs a Taiwan-related keyword filter keeps vs drops.

Fetches ONLY the sitemap (one request) — no page downloads, so it's fast.
Use this to tune KEYWORDS before running the slow full ingestion.

Run locally.  pip install requests lxml  (already have these via langchain deps)
"""

import re
import requests
from urllib.parse import urlparse
from lxml import etree

SITEMAP_URL = "https://amti.csis.org/sitemap-1.xml"   # the urlset (985 entries)

# Keep a URL if its slug contains ANY of these. Lowercased, matched on the path.
# Broad on purpose: better to keep a few borderline ones than miss Taiwan pages.
KEYWORDS = [
    "taiwan",
    "strait",          # also matches "cross-strait"
    "cross-strait",
    "adiz",
    "median-line",
    "pla-navy",
    "plan-",           # PLA Navy; hyphen-guarded to avoid the word "plan"
]
# slug tokens that, if present, usually mean a DIFFERENT dispute — used only
# to report likely false-positives, NOT to auto-drop (you decide).
OTHER_HINTS = ["philippines", "vietnam", "scarborough", "spratly", "senkaku", "malaysia"]


def fetch_urls(sitemap_url: str) -> list[str]:
    r = requests.get(sitemap_url, timeout=30, headers={"User-Agent": "research-preview"})
    r.raise_for_status()
    root = etree.fromstring(r.content)
    # strip namespace, grab every <loc>
    return [loc.text.strip() for loc in root.iter() if loc.tag.endswith("loc") and loc.text]


def slug(url: str) -> str:
    return urlparse(url).path.lower()


def main() -> None:
    urls = fetch_urls(SITEMAP_URL)
    print(f"total URLs in sitemap: {len(urls)}\n")

    pat = re.compile("|".join(re.escape(k) for k in KEYWORDS))
    kept = [u for u in urls if pat.search(slug(u))]
    print(f"kept by filter: {len(kept)}  (≈ {len(kept)*10/60:.0f} min to ingest @10s/page)\n")

    # show what got kept, flagging any that smell like another dispute
    print("--- KEPT (review for false positives) ---")
    for u in sorted(kept):
        flag = " <-- maybe off-topic" if any(h in slug(u) for h in OTHER_HINTS) else ""
        print(slug(u) + flag)

    # spot-check: a sample of what got dropped, to catch false negatives
    dropped = [u for u in urls if u not in set(kept)]
    print(f"\n--- DROPPED sample ({min(30, len(dropped))} of {len(dropped)}) ---")
    for u in sorted(dropped)[:30]:
        print(slug(u))


if __name__ == "__main__":
    main()