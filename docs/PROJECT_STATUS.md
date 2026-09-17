# 프로젝트 현황

기준일: 2026-08-28 KST

## 2026-09-16 재시작 추가 상태

- **현재 우선순위는 수집기다.** `capture/chrome/collector/`에 전체/포함/제외 카테고리 계획, 공개 목록 30줄 순회, 목록 재개·본문 중복 방문 생략, SQLite 보관, 카테고리 선택 HTML을 구현했다. 실행법은 [COLLECTION.md](COLLECTION.md).
- 실환경에서 전체보기 포함 68개 항목(일반 카테고리 67개), 화면 표시 공개 글 3,648개를 관측했다. 전체 목록은 4페이지/120개까지만 조사했다. 9월 러닝 카테고리 4개 목록 완료, 포함 4개/제외 후 116개 선택, 재수집 예약 방문 0개를 확인했다. 전체 기본값으로 복원했다.
- 저장 위치는 `~/Library/Application Support/Mnemosyne/collection/`이다. 기존 50개를 이전하고 새 본문 2개를 저장해 52개 보관, 68개 대기다. 52개 revision 및 2개 HTML archive hash 검증을 통과했다. 새 자료는 카테고리·문단/인용/표·링크/이미지 참조와 정리한 본문 DOM을 추가 보관한다. 기존 50개는 `LEGACY_TEXT_ONLY`로 구분한다.
- `npm test` 10개와 기존 확장 브라우저 통합 검증을 통과했다. 실제 화면에서 포함·제외·다운로드를 확인했다. 수년치 전체 수집, 구형 에디터 지원, 이미지 보존/OCR, 모든 글의 정확한 절대 시각 확보, 장기 운영의 차단·완전성 검증은 아직 완료하지 않았다.

- 신규 계획은 [PERSONA_RAG_PLAN.md](PERSONA_RAG_PLAN.md)에 있다. 사용자는 자료 확보를 최우선으로 지정했다.
- 별도 MV3 확장 프로그램과 Playwright Chromium으로 실제 공개 글 두 개의 자동 저장, 재방문 중복, 지원 텍스트 일치, 브라우저 재시작 후 보존을 확인했다.
- 데스크톱 앱을 사용하지 않으므로 Chrome for Codex 연결은 제품 경로에서 제외한다. 기존 macOS Service 저장기의 실환경 성공을 확인한 결과도 아니다.
- 코드·실행 안내는 `capture/chrome/`, 검증 범위와 한계는 [CHROME_CAPTURE_TEST.md](CHROME_CAPTURE_TEST.md)에 있다. 실제 원문은 저장소 밖에 보존하며, 전체 수집과 RAG 연결은 수행하지 않았다.
- RSS 최신 50개를 순차 방문하는 별도 실행을 완료했다. 50개 저장·본문 일치·revision 검증을 통과했고, 접근 감시상 문서 응답은 모두 HTTP 200이었다. 결과는 저장소 밖 `~/Library/Application Support/Mnemosyne/browser-test/live50-3XjsG8/`에 있다. 이는 해당 시점 최신 50개 처리 결과이며 블로그 전체 완전성이나 향후 무차단을 보장하지 않는다.
- 아래 내용은 기존 2026-08-28 상태 기록이다.

## TL;DR

연구와 설계에 더해, Google Chrome에서 사용자가 이미 연 현재 글 한 개를 로컬 private store에 저장하는 macOS capture 도구가 구현됐다. 이는 권한 있는 자료의 입력 경계일 뿐 corpus ingestion, RAG, 평가, 학습 또는 서버는 구현하지 않았다. 실제 타인 블로그 수집부터 시작하지 말고, 본인·동의자·합성 corpus로 다음 단계를 진행한다.

## 완료

- 현재 Codex 대화의 사용자·어시스턴트 표시 메시지 전사
- NAVER 약관·공식 도움말·robots·검색 API 경계 조사
- 한국 저작권·개인정보·정체성/사칭 위험 조사
- owner PDF backup과 데이터 이전 기능의 차이 확인
- corpus provenance, 버전, 삭제·철회 lifecycle 설계
- source-grounded RAG 우선 아키텍처 결정
- 선택적 LoRA 진입 조건 결정
- 인용·근거성·시간성·충돌·기권·정체성 평가 항목 설계
- HTML/PDF 보고서 및 렌더링 증거 생성
- 이전 자료를 `tars:/Users/tars/Documents/workspace/Kage_Bunshin`으로 전달하고 당시 SHA-256 검증
- macOS Google Chrome Service 기반의 현재 탭 1개 capture 구현: URL·제목·게시일·텍스트 본문을 검증하고, Markdown·JSON·JSONL private store에 저장
- 동일 문서의 같은 revision은 `DUPLICATE`로 처리하고, 내용이 달라진 revision은 이전 revision을 연결해 `REVISED`로 저장

## 미완료

- 실제 corpus의 권리·개인정보 검토
- PDF/HTML/Markdown ingestion 구현
- 원본/청크/임베딩 lineage 데이터베이스 구현
- 한국어 lexical+dense hybrid retrieval 구현
- 인용·시점·화자 verifier 구현
- private RAG 사용자 인터페이스 구현
- 자동·수동 평가 하네스 구현
- 삭제·복원 drill
- M3 Pro 실제 메모리·모델별 성능 benchmark
- 선택적 style adapter/LoRA 실험

## 현재 capture 경계

- Google Chrome용 macOS Service가 현재 활성 탭 하나만 대상으로 한다. 자동 URL 발견, 탭 생성, 다음 글 이동, 목록 순회, 재시도 큐는 없다.
- 지원 범위는 사용자가 권한 있게 열어 둔 현대식 `https://blog.naver.com/...` 게시글의 텍스트 추출이다. 이미지·표·임베드·오디오·비디오는 보존하지 않고 경고로 기록될 수 있다.
- 기본 저장소는 `/Users/tars/Library/Application Support/Mnemosyne`이며, 각 revision의 `post.md`와 `record.json`, 전체 export인 `posts.jsonl`을 가진다. 데이터는 기본적으로 권한 검토 전 `UNREVIEWED` 상태다.
- 설치, 권한, static doctor, 오류 코드와 권리 경계는 [`CAPTURE.md`](CAPTURE.md)에 따른다. 이 도구가 브라우저의 공개 열람을 복제·AI 이용·개인정보 처리 권한으로 바꾸지는 않는다.

## 확인된 기술·정책 경계

- 공개 열람은 자동수집·AI 재사용 허가와 동일하지 않다.
- NAVER 공식 정책은 명시적 허가, 준수하는 API 사용, 허용된 안내/robots 범위 밖 자동수집을 제한한다.
- NAVER Blog 소유자는 직접 작성한 글을 PDF로 백업할 수 있지만, 이는 손실 가능성이 있는 owner-facing 기능이며 제3자 전체 export API가 아니다.
- 사람이 페이지를 열고 단축키를 누르는 방식도 권리·약관 문제를 자동 해소하지 않는다.
- 블로그 글만으로 실제 사람과 동일한 사고, 현재 신념, 미래 행동을 검증할 수 없다.

## 머신 상태

- `akinella`: 현재 이 저장소를 생성한 머신.
- `tars`: 과거 전달본이 `/Users/tars/Documents/workspace/Kage_Bunshin`에 존재했으며 당시 해시 검증을 통과했다.
- 2026-08-21 확인에서는 `tars`의 `192.168.0.95:22` SSH 연결이 타임아웃이었다. 네트워크/원격 로그인 상태를 복구한 뒤 이 저장소를 clone하면 된다.
