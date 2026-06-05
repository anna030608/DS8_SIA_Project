"""
08_event_to_csis.py   (Block 1)
----------------------------------------------------------------------
Connect ONE GDELT event to ChinaPower CSIS analysis — honestly.

Given an event row (CAMEO code, coordinates, date), this:
  1. translates it into an English search query (Method A: metadata only),
  2. searches the saved ChinaPower FAISS index,
  3. returns ONE of three outcomes based on similarity score:
       DIRECT  : a CSIS article clearly covers this event
       CONTEXT : no direct article, but general analysis of this event TYPE
       NONE    : nothing relevant found  ("not found" is itself a signal)

Read-only on the index. Run locally.

Thresholds are TEMPORARY guesses — tune them after seeing real results.
"""

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# --- paths / model (must match what you ingested with) ----------------
INDEX_DIR = r"C:/Users/Jua/Desktop/DS/AIFFEL/00_AIFFELTHON/SIA_Project_Dash/project/01_data/processed"
EMBED_MODEL = "BAAI/bge-m3"

# --- thresholds (lower score = closer match). TUNE THESE later. --------
DIRECT_MAX = 0.90     # below this  -> DIRECT
CONTEXT_MAX = 1.10    # below this  -> CONTEXT;  above -> NONE

# --- your CAMEO map (15x/19x/20x). Extend with your full table. -------
CAMEO_TEXT = {
    "150": "military posturing", "151": "increased alert status",
    "152": "military exercise", "153": "increased military patrol",
    "154": "military mobilization buildup", "155": "cyber force buildup",
    "190": "use of conventional military force", "191": "blockade movement restriction",
    "192": "occupy territory", "193": "small-arms clash",
    "194": "armed clash heavy weapons tanks", "195": "use of air weapons",
    "196": "ceasefire violation",
    "200": "mass violence", "201": "mass expulsion", "202": "mass killing",
    "203": "ethnic cleansing", "204": "use of weapons of mass destruction",
}


def event_to_query(event: dict) -> str:
    """Method A: build an English search query from event metadata only."""
    code_text = CAMEO_TEXT.get(str(event["EventCode"]), "military event")
    month = str(event["SQLDATE"])[:7]                      # e.g. 2026-05
    # keep it simple: event type + Taiwan Strait context + month
    return f"{code_text} in Taiwan Strait, {month}"


def connect_event(event: dict, vs) -> dict:
    query = event_to_query(event)
    hits = vs.similarity_search_with_score(query, k=3)
    best_score = hits[0][1] if hits else 999.0

    if best_score < DIRECT_MAX:
        outcome = "DIRECT"
    elif best_score < CONTEXT_MAX:
        outcome = "CONTEXT"
    else:
        outcome = "NONE"

    return {"query": query, "outcome": outcome, "best_score": best_score, "hits": hits}


def describe(result: dict) -> None:
    """Print the honest 3-way explanation."""
    print(f"  query   : {result['query']}")
    print(f"  outcome : {result['outcome']}  (best score={result['best_score']:.3f})")

    if result["outcome"] == "NONE":
        print("  -> 관련 CSIS 분석을 찾지 못함. (대체로 소규모·일상적 사건)")
        return

    label = "직접 분석" if result["outcome"] == "DIRECT" else "유사 유형의 일반 맥락"
    print(f"  -> {label}:")
    for doc, score in result["hits"]:
        title = doc.metadata.get("title", "(no title)")
        url = doc.metadata.get("url", "")
        print(f"       [{score:.3f}] {title}")
        print(f"               {url}")


if __name__ == "__main__":
    emb = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    vs = FAISS.load_local(INDEX_DIR, emb, allow_dangerous_deserialization=True)

    # test with a few events (the real one + a couple of contrasts)
    test_events = [
        {"SQLDATE": "2026-05-10", "EventCode": 194, "ActionGeo_Lat": 24.91, "ActionGeo_Long": 118.59},
        {"SQLDATE": "2024-10-14", "EventCode": 152, "ActionGeo_Lat": 24.0, "ActionGeo_Long": 121.0},  # exercise
        {"SQLDATE": "2026-01-01", "EventCode": 191, "ActionGeo_Lat": 24.0, "ActionGeo_Long": 120.0},  # blockade
    ]

    for ev in test_events:
        print("=" * 70)
        print(f"event: {ev['SQLDATE']}  code={ev['EventCode']}")
        describe(connect_event(ev, vs))
        print()