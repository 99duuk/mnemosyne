# 다음 실행 순서

## 0. 작업 환경 복구

`tars`에서 이어갈 경우:

```bash
git clone git@github.com:99duuk/mnemosyne.git
cd mnemosyne
```

원격 로그인이 필요하면 macOS의 `시스템 설정 → 일반 → 공유 → 원격 로그인`과 현재 IP를 확인한다.

## 1. 구현용 저장소 구조 추가

연구 문서와 제품 코드를 분리한다.

```text
apps/
  api/
  web/
packages/
  ingestion/
  corpus/
  retrieval/
  evaluation/
fixtures/
  synthetic/
```

첫 corpus는 본인 글 또는 명시적으로 허가된 합성 자료로 만든다.

## 2. Canonical schema

다음 엔티티부터 구현한다.

- `source_item_version`
- `rights_basis_version`
- `artifact`
- `artifact_edge`
- `deletion_case`
- `evaluation_run`

원본 → 정규화본 → 청크 → 임베딩 → 프로필 → 캐시 → adapter 관계를 추적할 수 있어야 한다.

## 3. Ingestion MVP

- PDF/Markdown/HTML 입력
- SHA-256 계산
- 문서 identity와 revision 생성
- 제목·게시일·URL 추출
- 문단/문장 span 보존
- 댓글·인용·미디어·민감정보 quarantine
- JSONL export

PDF는 원본을 보존하고 Markdown을 파생물로 취급한다.

## 4. Retrieval MVP

1. 한국어 lexical baseline
2. dense embedding 후보 비교
3. hybrid + reciprocal-rank fusion
4. optional reranker
5. 검색 전 `rights + lifecycle + author + as_of` 필터

golden set에서 lexical/dense/hybrid ablation을 실행한 뒤 선택한다.

## 5. Answer pipeline

- 질문의 시점·화자·모드 파싱
- supporting/counterevidence 동시 검색
- atomic answer plan
- 3인칭·날짜 포함 답변
- claim/span/citation/time/identity 검증
- 실패 사유가 있는 기권

기권 코드는 `NO_EVIDENCE`, `TEMPORAL_AMBIGUITY`, `CONFLICT`, `RIGHTS_BLOCK`, `QUOTE_MISMATCH`, `POLICY_BLOCK`으로 시작한다.

## 6. Evaluation harness

문서·주제·시기 단위로 train/dev/test를 분리한다. 최소 평가군:

- source-documented answer
- unsupported premise
- historical/current/latest-observed
- contradiction
- direct quote
- third-party privacy
- corpus prompt injection
- deleted/private source
- identity confusion
- unseen-topic style

## 7. 삭제·복원 검증

synthetic canary 문서 하나를 철회하고 DB, raw/normalized data, lexical/vector index, profile, cache, evaluation fixture, backup restore에서 제거되는지 확인한다.

## 8. 선택적 LoRA

RAG·권리·삭제·정체성 gate가 모두 통과하고, 반복되는 style-only gap이 남을 때만 shadow mode로 비교한다. adapter는 base model에 merge하지 않는다.

## 9. 아직 결정이 필요한 입력

- 실제 구현 언어와 프레임워크
- tars의 unified memory 용량
- local-only 또는 hosted model 사용 여부
- 첫 합법적 test corpus
- private CLI, local web UI, 또는 API 중 첫 인터페이스

