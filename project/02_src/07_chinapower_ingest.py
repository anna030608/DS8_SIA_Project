"""
07_chinapower_ingest.py  (final: expanded keywords + real pub_date)
----------------------------------------------------------------------
ChinaPower -> FAISS ingestion, cross-strait layer.

Two additions over the previous working version:
  1. expanded keyword set (16 -> 18 matches: + military-diplomacy, missiles)
  2. extract the REAL publication date from each page's
     <meta property="article:published_time"> and store it as pub_date,
     so the Block-1 time window displays correctly.

URL extraction (direct, proven) + WebBaseLoader page fetch + 10s delay.
Run LOCALLY. ~18 pages @10s -> ~3 minutes.

Install (if needed): requests, beautifulsoup4 (already have these).
"""

import re
import time
import requests
from urllib.parse import urlparse
from lxml import etree
from bs4 import BeautifulSoup

from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# ---------------------------------------------------------------------
BASE = r"C:/Users/Jua/Desktop/DS/AIFFEL/00_AIFFELTHON/SIA_Project_Dash/project"
SITEMAP_URL = "https://chinapower.csis.org/sitemap-1.xml"
OUT_DIR = BASE + "/01_data/processed"
EMBED_MODEL = "BAAI/bge-m3"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
CRAWL_DELAY = 10

# expanded set (the +2 new matches confirmed by the preview)
KEYWORDS = [
    "taiwan", "cross-strait", "strait", "pla", "adiz",
    "reunification", "one-china", "tsai", "invasion", "blockade",
    "china-military", "conventional-missiles",
]


def get_filtered_urls() -> list[str]:
    r = requests.get(SITEMAP_URL, timeout=30, headers={"User-Agent": "research-ingest"})
    r.raise_for_status()
    root = etree.fromstring(r.content)
    all_urls = [loc.text.strip() for loc in root.iter()
                if loc.tag.endswith("loc") and loc.text]
    pat = re.compile("|".join(re.escape(k) for k in KEYWORDS))
    return sorted({u for u in all_urls if pat.search(urlparse(u).path.lower())})


def fetch_pub_date(html: str):
    """Pull article:published_time from the page HTML, if present."""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("meta", property="article:published_time")
    if tag and tag.get("content"):
        return tag["content"][:10]      # YYYY-MM-DD
    return None


def main() -> None:
    t0 = time.time()
    urls = get_filtered_urls()
    print(f"matched {len(urls)} URLs")
    if not urls:
        print("0 URLs -> check SITEMAP_URL / KEYWORDS.")
        return

    docs = []
    for i, url in enumerate(urls, 1):
        print(f"  [{i}/{len(urls)}] {urlparse(url).path}")
        try:
            # one request: get raw HTML for date, and let WebBaseLoader parse text
            raw = requests.get(url, timeout=30, headers={"User-Agent": "research-ingest"})
            pub_date = fetch_pub_date(raw.text)

            page = WebBaseLoader(url).load()
            for d in page:
                d.metadata["url"] = url
                d.metadata["source"] = "ChinaPower/CSIS"
                d.metadata["pub_date"] = pub_date          # <-- the fix
            docs.extend(page)
            if pub_date is None:
                print("      (발행일 태그 없음)")
        except Exception as e:
            print(f"      skipped ({e})")
        if i < len(urls):
            time.sleep(CRAWL_DELAY)

    print(f"loaded {len(docs)} docs")
    if not docs:
        return

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(docs)
    print(f"{len(chunks)} chunks")

    emb = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    vs = FAISS.from_documents(chunks, emb)
    vs.save_local(OUT_DIR)
    print(f"saved -> {OUT_DIR}  ({time.time() - t0:.0f}s total)")


if __name__ == "__main__":
    main()