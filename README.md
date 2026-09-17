# Mnemosyne

네이버 블로그 작성자의 공개 글을 기반으로, 출처와 시점을 보존하면서 관찰 가능한 주장·판단 근거·문체를 재현하는 개인 연구 프로젝트의 대화·결정·근거·산출물 저장소다.

이 저장소의 목표는 실제 사람의 내면을 복제했다고 주장하는 것이 아니다. 권한이 확인된 자료 안에서만 답하고, 근거가 없으면 기권하는 `source-grounded writing-and-viewpoint proxy`를 장기적으로 구현하는 것이다.

## 현재 상태

연구·정책 검토·아키텍처 설계·보고서 작성에 더해, macOS의 Google Chrome 서비스에서 사용자가 이미 연 현재 글 한 개를 저장하는 capture 도구가 구현돼 있다. 이 도구는 크롤러가 아니며, 실제 사용자·대상 데이터는 이 저장소에 포함하지 않는다.

현재 구현은 제목·게시일·텍스트 본문을 Markdown·JSON·JSONL의 로컬 private store로 보존하는 경계까지만 다룬다. ingestion pipeline, RAG 애플리케이션, 평가 하네스, LoRA 학습, 미디어 수집, 서버 기능은 아직 구현하지 않았다.

## 이어서 읽는 순서

1. [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) — 현재 완료·미완료 상태
2. [`docs/CAPTURE.md`](docs/CAPTURE.md) — Chrome 현재 글 저장기의 설치·권한·제한·문제 해결
3. [`docs/DECISIONS.md`](docs/DECISIONS.md) — 확정한 결정과 금지 경계
4. [`docs/NEXT_STEPS.md`](docs/NEXT_STEPS.md) — 다음 구현 순서
5. [`research/2026-07-13/SYNTHESIS.md`](research/2026-07-13/SYNTHESIS.md) — 가장 완성도 높은 전체 연구
6. [`research/2026-07-30/SYNTHESIS.md`](research/2026-07-30/SYNTHESIS.md) — 최신 정책 재확인 및 설계 갱신
7. [`docs/CONVERSATION.md`](docs/CONVERSATION.md) — 현재 대화 전체 전사본

## 저장 구조

```text
docs/
  CONVERSATION.md        사람이 읽는 전체 대화
  CONVERSATION.jsonl     기계가 처리할 수 있는 메시지 단위 원문
  SESSION_META.json      세션·전사 범위 메타데이터
  PROJECT_STATUS.md      완료/미완료/현재 블로커
  CAPTURE.md             Chrome 현재 글 저장기 사용 경계
  DECISIONS.md           핵심 결정
  NEXT_STEPS.md          다음 실행 순서
research/
  2026-07-13/            1차 최대 포화 연구 원장
  2026-07-30/            최신 정책·설계 재확인 원장
reports/
  2026-07-13/html/       HTML 보고서와 빌드 자산
  2026-07-13/pdf/        최종 PDF 보고서
evidence/
  2026-07-13/            렌더링·텍스트·런타임 검증 증거
```

## 다른 머신에서 재개

```bash
git clone git@github.com:99duuk/mnemosyne.git
cd mnemosyne
```

`tars`와 `akinella` 어느 쪽에서도 위 저장소를 기준으로 작업한다. 기존 `/Users/tars/Documents/workspace/Kage_Bunshin`은 이전 시점의 전달본이며, 앞으로는 이 저장소를 정본으로 사용한다.

## 보안 및 권리

- 저장소는 비공개로 유지한다.
- 원시 Codex JSONL은 시스템 지침·내부 로그·인증정보가 섞일 수 있어 저장하지 않았다.
- 대화 전사본에는 사용자·어시스턴트에게 표시된 메시지만 포함한다.
- 모르는 사람의 블로그를 자동 크롤링하거나 봇 탐지·정책을 우회하는 구현은 이 저장소의 승인 범위가 아니다.
- 실제 데이터 연결 전 플랫폼 접근, 저작권, 개인정보, 정체성 공개 권한을 각각 확인한다.
