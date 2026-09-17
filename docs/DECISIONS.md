# 핵심 결정

## D-01. 제품 정의

“특정인의 사고를 똑같이하는 분신”을 검증 가능한 목표로 사용하지 않는다. 제품은 다음으로 정의한다.

> 권한이 확인된 기록에서 관찰되는 과거 주장, 판단 근거, 문체와 시간에 따른 변화를 출처·날짜와 함께 답하는 분석 프록시

## D-02. 모르는 사람의 블로그

대상자와 모르는 사이이며 허가나 원본을 받을 수 없다면, 해당 블로그 전체를 자동수집해 실명 persona를 만드는 경로는 진행하지 않는다. 허가 없는 자동 크롤링, CAPTCHA/봇 차단 회피, 쿠키 우회, IP 회전은 구현 범위 밖이다.

## D-03. 사람이 직접 저장하는 방식

Safari 읽기 모드, PDF 저장, Share Sheet, Shortcuts, 단축키는 사용자 공수를 줄이는 기술적 수단이다. 해당 동작이 플랫폼 접근 권한, 저작권 이용 허락, 개인정보 처리 근거, persona 공개 권한을 새로 만들지는 않는다.

## D-04. 입력 corpus

우선순위는 다음과 같다.

1. 작성자가 직접 제공한 Markdown/HTML/text 및 원본 미디어
2. 작성자가 NAVER 관리 화면에서 생성한 공식 PDF backup
3. 정확한 endpoint·빈도·저장·AI 목적을 포함한 플랫폼 서면 허가

각 문서는 URL, 제목, 게시·수집 시점, 원본 해시, 권리 근거, 허용 목적, 공개 상태, 제3자 콘텐츠 상태를 가진다.

## D-05. 완전성

“모든 글”을 세계 전체에 대해 증명한다고 표현하지 않는다. 소유자가 선언한 inventory가 있다면 다음 상태만 주장한다.

`COMPLETE_RELATIVE_TO_OWNER_DECLARED_SCOPE_AT_CUTOFF`

해시와 Merkle root는 제출된 집합의 고정성만 증명하며 누락된 글이 없다는 사실까지 증명하지 않는다.

## D-06. RAG 우선

- 사실, 날짜별 입장, 인용, 삭제 가능한 지식: versioned corpus + RAG
- 반복 가능한 응답 규칙: system prompt + few-shot
- 평가로 확인된 순수 문체 gap: 선택적 unmerged LoRA
- raw blog 전체 next-token 학습: 기본 제외

## D-07. 출력 화자

기본 출력은 3인칭·과거시점 귀속형이다.

> “작성자는 2024년 3월 2일 게시글에서 X라고 썼다.”

실제 인물처럼 “나는 X라고 믿는다”고 말하는 공개 실명 1인칭 모드는 별도 명시적 권한과 혼동 방지 검증 전까지 차단한다.

## D-08. 시간성

- `historical(as_of=T)`: T까지 존재한 증거만 사용
- `latest_observed`: 가장 최근 확인된 글과 날짜를 명시
- `current`: freshness window 안에서 재확인된 경우만 사용
- 확인할 수 없으면 현재 생각을 추론하지 않고 `unknown` 처리

## D-09. 평가

출시 전에 다음을 각각 검사한다.

- atomic claim support
- citation correctness/completeness
- direct quote exact match
- temporal consistency
- conflicting evidence preservation
- abstention/calibration
- unseen-topic style fidelity와 의미 보존
- identity disclosure와 사칭 방지
- prompt injection
- revoked/private document retrieval 차단
- deletion/rebuild drill

## D-10. 외부 행동

MVP persona에는 이메일, 게시, 결제, 계정 변경, 계약, 메시지 전송 도구를 연결하지 않는다. 문서 분석과 근거 기반 답변까지만 허용한다.
# 2026-09-16 추가 결정: 수집 우선

- 사용자 최신 지시에 따라 분신/RAG는 보류하고 약 3개 블로그의 수년치 자료 확보를 우선한다. 기존 소량 검증 범위를 공개 자료 수집기 개발로 확대했다.
- 기본 범위는 전체 카테고리다. 상위 카테고리는 하위를 포함하며 제외가 우선한다. 본문 수집 전에 제외 목록의 완전성을 확인한다.
- RSS 최신 50개에 의존하지 않고 공개 목록 UI의 30줄 보기·페이지 이동을 사용한다. 표시 개수와 고유 ID 수가 맞아야 목록 완료로 기록한다.
- 별도 Chromium+기존 확장을 유지하며 SQLite를 정식 보관소로 삼는다. 확장 저장은 글별 임시 저장으로 사용하고 DB 확정 후 정리한다. 데스크톱 앱은 필요하지 않다.
- 본문 원문, 구조·근거 링크·미디어 참조, 날짜 정밀도, 추출 버전과 관측 이력을 분리한다. 구형 에디터/이미지 전용 글을 빈 본문 성공으로 처리하지 않는다.
- 기본 5초 간격과 순차 실행을 사용하되 차단되지 않는 속도라고 주장하지 않는다. 제한 신호는 전체 정지하며 우회하지 않는다. 상세 운영 범위는 [COLLECTION.md](COLLECTION.md).
- 미디어 수집 필요성을 후속 과제로 기록한다. 현재는 이미지·표·임베드의 참조 정보만 보존하고, 이후 파일·표 구조·OCR을 별도 계층으로 추가한다. 본문 내용 해시와 미디어 해시는 분리한다.
