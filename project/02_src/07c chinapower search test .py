"""
07c_chinapower_search_test.py
----------------------------------------------------------------------
Read-only test: load the saved ChinaPower FAISS index and run a few
KOREAN queries against the (English) ChinaPower articles, to confirm
cross-lingual retrieval works.

Nothing is downloaded or written — this only reads the index you saved.

Run LOCALLY, from the same folder you ran the ingest in (so the relative
path matches). If the path is wrong, set INDEX_DIR to the full path.
"""

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

INDEX_DIR = r"C:\Users\Jua\Desktop\DS\AIFFEL\00_AIFFELTHON\SIA_Project_Dash\project\01_data\processed"
EMBED_MODEL = "BAAI/bge-m3"                                  # must match ingest

# A few Korean test questions tied to the project's known events.
QUERIES = [
    "중국이 대만을 봉쇄하는 시나리오",
    "조인트 소드 2024 군사 훈련",
    "제4차 대만해협 위기",
    "중국이 대만을 침공할 수 있는가",
]

TOP_K = 3   # show top 3 matches per query


def main() -> None:
    emb = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    # allow_dangerous_deserialization: needed to load a local FAISS index you made
    vs = FAISS.load_local(INDEX_DIR, emb, allow_dangerous_deserialization=True)
    print(f"index loaded.\n")

    for q in QUERIES:
        print("=" * 70)
        print(f"질문: {q}")
        # returns (Document, score); lower score = closer match for L2 distance
        results = vs.similarity_search_with_score(q, k=TOP_K)
        for rank, (doc, score) in enumerate(results, 1):
            title = doc.metadata.get("title", "(no title)")
            url = doc.metadata.get("url", "")
            snippet = doc.page_content[:160].replace("\n", " ")
            print(f"\n  [{rank}] score={score:.3f}")
            print(f"      title : {title}")
            print(f"      url   : {url}")
            print(f"      text  : {snippet}...")
        print()


if __name__ == "__main__":
    main()