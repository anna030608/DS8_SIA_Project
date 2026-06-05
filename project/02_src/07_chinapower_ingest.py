"""
07_chinapower_ingest.py  (robust version)
----------------------------------------------------------------------
ChinaPower (chinapower.csis.org) -> FAISS ingestion, cross-strait layer.

Why this version: LangChain's SitemapLoader returned 0 docs on ChinaPower's
sitemap, even though direct XML parsing (the 07b preview) found 16 URLs fine.
So we do the part that works ourselves — extract + filter URLs directly —
and only hand the page-fetching to LangChain. The 10s crawl-delay is enforced
manually here.

Run LOCALLY.  ~16 pages @10s  ->  ~3 minutes.

Install (if not done):
  pip install langchain-community langchain-text-splitters \
              langchain-huggingface sentence-transformers \
              faiss-cpu lxml beautifulsoup4 requests
"""

import re
import time
import requests
from urllib.parse import urlparse
from lxml import etree

from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------
SITEMAP_URL = "https://chinapower.csis.org/sitemap-1.xml"

# Validated cross-strait filter (07b preview -> 16 clean matches).
KEYWORDS = [
    "taiwan", "cross-strait", "strait", "pla", "adiz",
    "reunification", "one-china", "tsai", "invasion", "blockade",
]

OUT_DIR = "01_data/processed/chinapower_faiss"
EMBED_MODEL = "BAAI/bge-m3"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
CRAWL_DELAY = 10            # seconds between page requests (robots.txt)


# ---------------------------------------------------------------------
# Step 1: get the article URLs ourselves (the part that's proven to work)
# ---------------------------------------------------------------------
def get_filtered_urls() -> list[str]:
    r = requests.get(SITEMAP_URL, timeout=30, headers={"User-Agent": "research-ingest"})
    r.raise_for_status()
    root = etree.fromstring(r.content)
    all_urls = [loc.text.strip() for loc in root.iter()
                if loc.tag.endswith("loc") and loc.text]

    pat = re.compile("|".join(re.escape(k) for k in KEYWORDS))
    # dedup while keeping only matching slugs
    kept = sorted({u for u in all_urls if pat.search(urlparse(u).path.lower())})
    return kept


def main() -> None:
    t0 = time.time()

    urls = get_filtered_urls()
    print(f"matched {len(urls)} URLs")
    if not urls:
        print("0 URLs -> check SITEMAP_URL / KEYWORDS.")
        return

    # --- Step 2: fetch each page, honoring the 10s crawl-delay ---
    docs = []
    for i, url in enumerate(urls, 1):
        print(f"  [{i}/{len(urls)}] {urlparse(url).path}")
        try:
            page = WebBaseLoader(url).load()    # returns a list with one Document
            for d in page:
                d.metadata["url"] = url
                d.metadata["source"] = "ChinaPower/CSIS"
            docs.extend(page)
        except Exception as e:
            print(f"      skipped ({e})")
        if i < len(urls):
            time.sleep(CRAWL_DELAY)

    print(f"loaded {len(docs)} docs")
    if not docs:
        return

    # --- Step 3: chunk ---
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )
    chunks = splitter.split_documents(docs)
    print(f"{len(chunks)} chunks")

    # --- Step 4: embed + save ---
    emb = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    vs = FAISS.from_documents(chunks, emb)
    vs.save_local(OUT_DIR)
    print(f"saved -> {OUT_DIR}  ({time.time() - t0:.0f}s total)")


if __name__ == "__main__":
    main()