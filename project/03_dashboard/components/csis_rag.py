"""
components/csis_rag.py
----------------------------------------------------------------------
Block 1 as an importable module for the chatbot.

Exposes:
    search_csis(event: dict) -> dict
        event needs: SQLDATE, EventCode, QuadClass, Actor1Name, Actor2Name
        returns: {outcome, best, reason, hits:[{title,url,score,time_note}]}

The FAISS index + bge-m3 model are loaded ONCE (lazily, on first call),
not per request, so the Dash app stays responsive.

Outcome rule: DIRECT / CONTEXT / NONE by similarity, with DIRECT demoted
to CONTEXT when the article's pub_date differs from the event by > 12 months.
"""

import os
from datetime import datetime

# --- config ----------------------------------------------------------
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project/
INDEX_DIR = os.path.join(_BASE, "01_data", "processed")   # where index.faiss lives
EMBED_MODEL = "BAAI/bge-m3"

DIRECT_MAX = 0.90
CONTEXT_MAX = 1.10
MAX_MONTHS = 12

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

# --- lazy singletons (loaded once) -----------------------------------
_vs = None


def _get_store():
    """Load FAISS index + embeddings once, on first use."""
    global _vs
    if _vs is None:
        from langchain_community.vectorstores import FAISS
        from langchain_huggingface import HuggingFaceEmbeddings
        emb = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
        _vs = FAISS.load_local(INDEX_DIR, emb, allow_dangerous_deserialization=True)
    return _vs


def _distinctive(name):
    if name is None:
        return None
    s = str(name).strip().upper()
    return s.title() if s and s not in GENERIC_ACTORS else None


def _event_to_query(ev: dict) -> str:
    parts = [CAMEO_TEXT.get(str(ev.get("EventCode")), "military event")]
    for col in ("Actor1Name", "Actor2Name"):
        d = _distinctive(ev.get(col))
        if d:
            parts.append(d)
    if int(ev.get("QuadClass", 0) or 0) == 4:
        parts.append("armed physical clash")
    parts.append("Taiwan Strait")
    parts.append(str(ev.get("SQLDATE", ""))[:7])
    return ", ".join(parts)


def _months_gap(event_date, pub_date):
    if not pub_date or str(pub_date) in ("None", "nan"):
        return None
    try:
        ev = datetime.fromisoformat(str(event_date)[:10])
        pub = datetime.fromisoformat(str(pub_date)[:10])
    except ValueError:
        return None
    return (pub - ev).days // 30


def _time_note(gap):
    if gap is None:
        return "발행일 정보 없음"
    m = abs(gap)
    if gap >= 0:
        return f"사건 {m}개월 후 발행" if m else "사건 직후 발행"
    return f"사건 {m}개월 전 발행"


def search_csis(event: dict) -> dict:
    """Connect one event to ChinaPower CSIS analysis (honest 3-way outcome)."""
    try:
        vs = _get_store()
    except Exception as e:
        return {"outcome": "ERROR", "reason": f"인덱스 로드 실패: {e}", "hits": []}

    query = _event_to_query(event)
    raw = vs.similarity_search_with_score(query, k=5)

    seen, uniq = set(), []
    for doc, score in raw:
        url = doc.metadata.get("url")
        if url not in seen:
            seen.add(url)
            uniq.append((doc, score))
    uniq = uniq[:3]

    if not uniq:
        return {"outcome": "NONE", "best": None, "reason": "", "hits": []}

    best_doc, best_score = uniq[0]
    gap = _months_gap(event.get("SQLDATE"), best_doc.metadata.get("pub_date"))

    reason = ""
    if best_score >= CONTEXT_MAX:
        outcome = "NONE"
    elif best_score < DIRECT_MAX:
        if gap is not None and abs(gap) > MAX_MONTHS:
            outcome = "CONTEXT"
            reason = f"점수는 가까우나 발행 시점이 {abs(gap)}개월 차이"
        else:
            outcome = "DIRECT"
    else:
        outcome = "CONTEXT"

    hits = [
        {
            "title": d.metadata.get("title", "(no title)"),
            "url": d.metadata.get("url", ""),
            "score": round(float(s), 3),
            "time_note": _time_note(_months_gap(event.get("SQLDATE"), d.metadata.get("pub_date"))),
            "excerpt": d.page_content[:300].replace("\n", " "),
        }
        for d, s in uniq
    ]
    return {"outcome": outcome, "best": round(float(best_score), 3),
            "reason": reason, "query": query, "hits": hits}