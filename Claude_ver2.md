Last updated: 2026-05-04

기존 Claude.md 파일에 완성된 기획서의 내용을 반영하여 수정 및 업데이트한 내용입니다. 프로젝트의 핵심 목표와 비즈니스 임팩트, 기술 스택을 최신화했습니다.

1. 프로젝트 개요 (Project Overview)
과업명 및 프로젝트명: 양안관계 OSINT-GEOINT 기반 위성 촬영 의사결정 지원 시스템

참여 기업: SI Analytics (SIA)

핵심 목표 및 가치:

양안관계(대만-중국)의 군사적 긴장 상태를 실시간 모니터링하기 위해 공개출처정보(OSINT)에서 이상 징후를 포착하고, 이를 위성 자산(GEOINT)의 촬영 계획으로 자동 번역하여 제한된 위성 자산의 운용 효율을 극대화합니다.

GDELT 뉴스 수집부터 위성 촬영 전략 제안까지 단일 시스템 내에서 자동 연동되는 OSINT-GEOINT 통합 체계를 구축합니다.

기상/궤도 사전 분석을 통해 촬영 실패율을 최소화하고, 분석관이 선제적이고 고부가가치 전략 분석에 집중할 수 있는 환경을 만듭니다.

2. 페르소나 및 타겟 (Persona & Target)
타겟 지역: 양안 관계 (중국-대만 해협 중심)

페르소나: SIA 양안관계 분석 전담팀. 고가의 위성 영상 구매를 위해 수치적 근거와 촬영 성공 가능성(기상, 궤도)을 빠르게 판단해야 하는 분석관.

3. 핵심 모델링 및 세부 목표 (Core Modeling Goals)
3.1. OSINT 기반 이상 징후 자동 탐지
군사 이벤트 필터링: GDELT 데이터를 활용하여 China/Taiwan 관련 CAMEO 코드 및 Goldstein Scale 기반 1차 필터링 후, 이동 객체(차량, 선박 등) 중심의 2차 필터링을 수행합니다.

임베딩 기반 이벤트 통합: 동일 사건의 중복 보도를 제거하기 위해 뉴스 제목/요약/지역명을 벡터화(OpenAI Embedding 등)하고 Cosine Similarity 기반으로 클러스터링하여 '이벤트 단위'로 재구성합니다.

시계열 스파이크 탐지: 기사량(Volume)의 급증과 정서(Tone)의 급격한 변화를 결합하여 이상 징후(Spike)를 정의하고, 중요도 스코어링과 결합합니다.

3.2. GEOINT 연동 및 촬영 계획 최적화
좌표 유효성 및 정제: GDELT의 ActionGeo_Lat/Long 결측값 확인 및 지리 정보 신뢰도를 검증합니다.

관심 지역(ROI) 생성: DBSCAN을 활용해 공간 클러스터링을 수행하고, 고해상도 위성 관측 폭(Swath)에 맞춰 ROI를 구성합니다.

위성 촬영 분석: SGP4 알고리즘을 사용한 TLE 기반 궤도 전파 및 위성 촬영 가능 시간대(Window)를 산출하고, 구름 커버리지를 고려하여 최적 센서(EO 또는 SAR)를 추천합니다.

3.3. 의사결정 지원 스코어링 (Priority Scoring)
Priority Score 산출: (뉴스 확산성 + 이벤트 위중도 + 정서 변화) × (위성 관측 가치 및 촬영 성공 가능성)을 결합하여 분석관에게 우선순위를 제안합니다.

4. 기술 스택 (Tech Stack)
Language: Python 3.11+

Data: GDELT 1.0 (News), CelesTrak (TLE), OpenWeather (Cloud Cover)

Analysis: Pandas, Scikit-learn (DBSCAN), OpenAI API (Embedding), Skyfield/PyEphem (Orbit)

Visualization: Streamlit (Interactive Dashboard), Folium/Kepler.gl (Map)

5. 디렉토리 구조 (Directory Structure)
Plaintext
/project-root
├── data/                   # GDELT, TLE raw data
├── src/
│   ├── osint/              # 뉴스 필터링, 임베딩 클러스터링, 스파이크 탐지
│   ├── geoint/             # 좌표 정제, DBSCAN ROI 생성, 위성 궤도 계산
│   ├── scoring/            # Priority Scoring 로직 및 센서 선택 규칙
│   └── dashboard/          # Streamlit 기반 인터랙티브 시각화
├── notebooks/              # EDA 및 모델 실험 (2025-26 스파이크 분석)
├── Claude.md               # 프로젝트 가이드 (본 파일)
├── requirements.txt        # 의존성 목록
└── docker-compose.yml      # 준실시간 아키텍처 지원
