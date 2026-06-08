"""
07e_chinapower_expanded_preview.py
----------------------------------------------------------------------
Preview ChinaPower with a BROADER keyword set, before re-ingesting.
Fast (sitemap only, no page downloads). Marks which matches are NEW
(beyond the original 16) and flags likely off-topic ones, so we can
decide which expanded keywords are worth keeping.

Needs: requests, lxml.
"""

import re
import requests
from urllib.parse import urlparse
from lxml import etree

SITEMAP_URL = "https://chinapower.csis.org/sitemap-1.xml"

# original (the 16-result set)
BASE_KEYWORDS = [
    "taiwan", "cross-strait", "strait", "pla", "adiz",
    "reunification", "one-china", "tsai", "invasion", "blockade",
]
# expansion candidates (review which actually help)
EXTRA_KEYWORDS = [
    "china-military", "military-exercise", "pla-navy", "pla-air", "missile",
    "coercion", "gray-zone", "quarantine", "lai", "william-lai",
    "defense", "deterrence",
]
# tokens that usually mean a different topic (reported, not auto-dropped)
OTHER_HINTS = ["economy", "trade", "debt", "currency", "covid", "demographic",
               "energy", "belt-and-road", "corruption", "philippines", "vietnam"]


def fetch_urls(u):
    r = requests.get(u, timeout=30, headers={"User-Agent": "research-preview"})
    r.raise_for_status()
    root = etree.fromstring(r.content)
    return [loc.text.strip() for loc in root.iter() if loc.tag.endswith("loc") and loc.text]


def slug(u):
    return urlparse(u).path.lower()


def matches(urls, keywords):
    pat = re.compile("|".join(re.escape(k) for k in keywords))
    return {u for u in urls if pat.search(slug(u))}


def main():
    urls = fetch_urls(SITEMAP_URL)
    print(f"total URLs: {len(urls)}\n")

    base = matches(urls, BASE_KEYWORDS)
    full = matches(urls, BASE_KEYWORDS + EXTRA_KEYWORDS)
    new = full - base

    print(f"original keywords : {len(base)} matches")
    print(f"expanded keywords : {len(full)} matches  (+{len(new)} new)")
    print(f"estimated ingest  : ~{len(full)*10/60:.0f} min\n")

    print("--- NEW matches from expansion (review these) ---")
    for u in sorted(new):
        flag = " <-- maybe off-topic" if any(h in slug(u) for h in OTHER_HINTS) else ""
        print(slug(u) + flag)


if __name__ == "__main__":
    main()