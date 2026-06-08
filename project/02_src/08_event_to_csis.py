"""
08_event_to_csis.py   (Block 1 — final: time-aware outcome)
----------------------------------------------------------------------
Connect ONE GDELT event to ChinaPower CSIS analysis — honestly.

Query (light Method 2): EventCode text + distinctive actor + QuadClass cue
                        + "Taiwan Strait" + month.

Outcome rule (score + time):
  - score >= CONTEXT_MAX            -> NONE
  - score <  DIRECT_MAX  AND        -> DIRECT
        (no pub_date  OR  |event - pub_date| <= MAX_MONTHS)
  - score <  DIRECT_MAX  but time gap > MAX_MONTHS -> demoted to CONTEXT
        (analysis exists but is from a different period — "general context")
  - DIRECT_MAX <= score < CONTEXT_MAX -> CONTEXT

Time is DISPLAYED for every hit; pub_date missing -> judged by score only.

Read-only on the index. Reads events_filtered.csv. Run locally.
"""

import pandas as pd
from datetime import datetime
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

BASE = r"C:/Users/Jua/Desktop/DS/AIFFEL/00_AIFFELTHON/SIA_Project_Dash/project"
EVENTS_CSV = BASE + "/01_data/processed/events_filtered.csv"
INDEX_DIR = BASE + "/01_data/processed"
EMBED_MODEL = "BAAI/bge-m3"

DIRECT_MAX = 0.90
CONTEXT_MAX = 1.10
MAX_MONTHS = 12          # within 12 months of the event -> can stay DIRECT
USE_ACTOR = True
USE_QUAD = True

GENERIC_ACTORS = {
    "CHINA", "TAIWAN", "CHINESE", "TAIWANESE",
    "BEIJING", "TAIPEI", "", "NAN",
}

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


def distinctive(name):
    if name is None:
        return None
    s = str(name).strip().upper()
    return s.title() if s and s not in GENERIC_ACTORS else None


def event_to_query(ev: dict) -> str:
    parts = [CAMEO_TEXT.get(str(ev["EventCode"]), "military event")]
    if USE_ACTOR:
        for col in ("Actor1Name", "Actor2Name"):
            d = distinctive(ev.get(col))
            if d:
                parts.append(d)
    if USE_QUAD and int(ev.get("QuadClass", 0)) == 4:
        parts.append("armed physical clash")
    parts.append("Taiwan Strait")
    parts.append(str(ev["SQLDATE"])[:7])
    return ", ".join(parts)


def months_gap(event_date: str, pub_date):
    """Signed months between event and pub_date. None if no/invalid date."""
    if not pub_date or str(pub_date) in ("None", "nan"):
        return None
    try:
        ev = datetime.fromisoformat(str(event_date)[:10])
        pub = datetime.fromisoformat(str(pub_date)[:10])
    except ValueError:
        return None
    return (pub - ev).days // 30


def time_note(gap):
    if gap is None:
        return "발행일 정보 없음"
    m = abs(gap)
    if gap >= 0:
        return f"분석은 사건 {m}개월 후 발행" if m else "분석은 사건 직후 발행"
    return f"분석은 사건 {m}개월 전 발행"


def connect_event(ev: dict, vs) -> dict:
    query = event_to_query(ev)
    hits = vs.similarity_search_with_score(query, k=5)

    seen, uniq = set(), []
    for doc, score in hits:
        url = doc.metadata.get("url")
        if url not in seen:
            seen.add(url)
            uniq.append((doc, score))
    uniq = uniq[:3]

    if not uniq:
        return {"query": query, "outcome": "NONE", "hits": [], "reason": ""}

    best_doc, best_score = uniq[0]
    gap = months_gap(ev["SQLDATE"], best_doc.metadata.get("pub_date"))

    reason = ""
    if best_score >= CONTEXT_MAX:
        outcome = "NONE"
    elif best_score < DIRECT_MAX:
        if gap is not None and abs(gap) > MAX_MONTHS:
            outcome = "CONTEXT"
            reason = f"(점수는 가까우나 발행 시점이 {abs(gap)}개월 차이 → 일반 맥락으로 분류)"
        else:
            outcome = "DIRECT"
    else:
        outcome = "CONTEXT"

    return {"query": query, "outcome": outcome, "best": best_score,
            "hits": uniq, "reason": reason}


def describe(ev: dict, r: dict) -> None:
    print(f"event {ev['SQLDATE']}  code={ev['EventCode']}  quad={ev.get('QuadClass')}")
    print(f"  query   : {r['query']}")
    line = f"  outcome : {r['outcome']}"
    if r.get("best") is not None:
        line += f"  (best={r['best']:.3f})"
    print(line)
    if r["reason"]:
        print(f"            {r['reason']}")
    if r["outcome"] == "NONE":
        print("  -> 관련 CSIS 분석을 찾지 못함. (대체로 소규모·일상적 사건)")
        return
    label = "직접 분석" if r["outcome"] == "DIRECT" else "유사 유형의 일반 맥락"
    print(f"  -> {label}:")
    for doc, score in r["hits"]:
        note = time_note(months_gap(ev["SQLDATE"], doc.metadata.get("pub_date")))
        print(f"       [{score:.3f}] {doc.metadata.get('title', '(no title)')}")
        print(f"               ({note})")


if __name__ == "__main__":
    emb = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    vs = FAISS.load_local(INDEX_DIR, emb, allow_dangerous_deserialization=True)
    df = pd.read_csv(EVENTS_CSV)

    sample = df.sample(min(8, len(df)), random_state=0).to_dict("records")
    for ev in sample:
        print("=" * 70)
        describe(ev, connect_event(ev, vs))
        print()