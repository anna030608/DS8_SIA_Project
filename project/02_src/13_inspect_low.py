"""
13_inspect_low.py  (LOW 판정 표본 검증)
----------------------------------------------------------------------
신뢰도 검증 결과(event_reliability.csv)에서 LOW로 판정된 사건을 뽑아
제목·LLM 근거·원본 URL을 보여준다. 사람이 눈으로 "정말 오분류인지" 확인용.

발표에서 "LOW의 N%가 타당했다"고 말할 근거를 만드는 단계.

사용:
  python 13_inspect_low.py                # LOW 20개 표본
  python 13_inspect_low.py --n 30
  python 13_inspect_low.py --grade UNVERIFIED   # 다른 등급도 확인 가능
"""

import argparse
import pandas as pd

REL_CSV = "project/01_data/processed/event_reliability.csv"

CAMEO_TEXT = {
    "150": "군사 태세", "151": "경계 수준 강화", "152": "군사력 증강",
    "153": "군사 순찰 증가", "154": "군사 동원·증강", "190": "재래식 무력 사용",
    "191": "봉쇄·이동제한", "192": "영토 점령", "193": "소형화기 충돌",
    "194": "중화기 무력충돌", "195": "공중무기 사용", "196": "정전 위반",
    "200": "대규모 폭력", "201": "대규모 추방", "202": "대량 살상",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=20, help="표본 수")
    parser.add_argument("--grade", default="LOW", help="확인할 등급 (기본 LOW)")
    args = parser.parse_args()

    df = pd.read_csv(REL_CSV)

    # 전체 등급 분포 먼저
    print("전체 등급 분포:")
    print(df["grade"].value_counts().to_string())
    print(f"  합계: {len(df)}건")
    print("=" * 70)

    sub = df[df["grade"] == args.grade]
    if len(sub) == 0:
        print(f"'{args.grade}' 등급 없음"); return

    n = min(args.n, len(sub))
    sample = sub.sample(n=n, random_state=1)

    print(f"\n[{args.grade}] 판정 표본 {n}개 (전체 {len(sub)}개 중)\n" + "=" * 70)

    for i, (_, r) in enumerate(sample.iterrows(), 1):
        code = str(r.get("EventCode", ""))
        code_text = CAMEO_TEXT.get(code, "")
        print(f"\n[{i}] GDELT 분류: CAMEO {code} ({code_text}) | 날짜: {r.get('SQLDATE','')}")
        print(f"    제목: {str(r.get('title',''))[:90]}")
        print(f"    LLM 근거: {str(r.get('reason',''))[:200]}")
        print(f"    원본 URL: {str(r.get('source_url',''))[:80]}")

    print("\n" + "=" * 70)
    print("확인 방법:")
    print("  각 항목에서 'GDELT 분류'와 '제목/근거'를 비교하세요.")
    print("  · 제목이 분류와 명백히 무관(코로나·사고·일반뉴스) → LLM 판정 타당(진짜 오분류)")
    print("  · 제목이 사실 군사 관련인데 LOW로 잡힘 → LLM 오판 (드물길 기대)")

if __name__ == "__main__":
    main()