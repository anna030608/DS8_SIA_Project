1. 프로젝트 개요 (Project Overview)
프로젝트명: 양안관계 OSINT-GEOINT 기반 위성 촬영 의사결정 지원 시스템

참여 기업: SIA

핵심 가치: 뉴스(OSINT)에서 포착된 이상 징후를 위성 관측(GEOINT) 계획으로 자동 번역하여, 제한된 위성 자산의 운용 효율을 극대화함.

2. 페르소나 및 타겟 (Persona & Target)
타겟 지역: 양안 관계 (중국-대만 대협 중심)

페르소나: SIA 양안관계 분석 전담팀. 고가의 위성 영상 구매를 위해 수치적 근거와 촬영 성공 가능성(기상, 궤도)을 빠르게 판단해야 하는 분석관.

3. 핵심 모델링 및 세부 목표 (Core Modeling Goals)
3.1. OSINT 기반 이상 징후 자동 탐지
군사 이벤트 필터링: GDELT 데이터를 활용, China/Taiwan 관련 CAMEO 코드 및 Goldstein Scale 기반 1차 필터링 후, 이동 객체(차량, 선박 등) 중심의 2차 필터링 수행.

임베딩 기반 이벤트 통합: 동일 사건의 중복 보도를 제거하기 위해 뉴스 제목/요약/지역명을 벡터화(OpenAI Embedding 등)하고 Cosine Similarity 기반으로 클러스터링하여 '이벤트 단위'로 재구성.

시계열 스파이크 탐지: 기사량(Volume)의 급증과 정서(Tone)의 급격한 변화를 결합하여 이상 징후(Spike) 정의.

3.2. GEOINT 지리 정보 정교화 및 위성 매칭
지리 신뢰성 검증: GDELT 좌표와 지역명을 PiP(Point-in-Polygon) 및 Geocoding으로 교차 검증하여 신뢰도 레벨(Level 1~3) 부여.

공간 클러스터링 및 ROI 생성: 흩어진 이벤트를 위성 센서 규격(Swath, 약 10~15km)을 반영한 DBSCAN(반경 5km 설정)으로 묶어 최적의 촬영 관심지역(ROI) 도출.

위성 스케줄링 및 전략: TLE(궤도 데이터)와 기상 API(구름량)를 결합하여 촬영 가능 시간대(Window) 산출 및 EO(광학)/SAR(레이더) 센서 추천.

3.3. 의사결정 지원 스코어링 (Priority Scoring)
Priority Score 산출: (뉴스 확산성 + 이벤트 위중도 + 정서 변화) × (위성 관측 가치 및 촬영 성공 가능성)을 결합하여 분석관에게 우선순위 제안.

4. 기술 스택 (Tech Stack)
Language: Python 3.10+

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
└── docker-compose.yml      # 준실시간 아키텍처 환경 구성

6. 개발 규칙 및 주의사항 (Development Rules)
준실시간성 유지: 실제 스트리밍 대신 최근 1~3일 데이터를 신규 유입으로 가정하는 배치 파이프라인 구조 설계.

공간 데이터 우선: 모든 뉴스 데이터는 위성 타겟팅을 위해 정밀한 좌표 보정(Geocoding) 단계를 거칠 것.

자원 제약 고려: 위성 촬영은 고비용 작업이므로 '이동 객체 식별 가능성'이 높은 이벤트에 가중치를 부여할 것.

에러 핸들링: 외부 API(OpenAI, Weather) 호출 실패 시 시스템 중단을 방지하기 위한 대체 로직(Fallback) 필수.

7. 주요 마일스톤 (Milestones)
Phase 2 (현재): GDELT 데이터 수집 및 시계열 패턴 분석 (스파이크 임계값 설정).

Phase 3: 임베딩 기반 이벤트 통합 로직 및 스코어링 모델 구축.

Phase 4/5: 위성 궤도 계산기 및 기상 반영 촬영 전략 통합.

Phase 6: 최종 인터랙티브 의사결정 대시보드 배포.