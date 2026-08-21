# 프로젝트 현황

기준일: 2026-08-21 KST

## TL;DR

연구와 설계는 완료됐고 구현은 시작 전이다. 지금 재개한다면 실제 타인 블로그 수집부터 시작하지 말고, 본인·동의자·합성 corpus로 범용 ingestion + private RAG + 평가 하네스를 먼저 만든다.

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

## 미완료

- 실제 블로그 게시글 수집
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

