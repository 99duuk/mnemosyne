# Chrome 현재 글 저장기

이 도구는 macOS Service로 Google Chrome의 **현재 활성 탭 하나**에서 제목, 표시된 게시일, 텍스트 본문, URL을 추출해 로컬에 보관한다. 서비스는 Chrome에만 등록되며, 탭이나 URL이 추출 중 바뀌면 저장하지 않는다.

지원 입력은 사용자가 권한 있게 직접 연 현대식 `https://blog.naver.com/...` 게시글이다. URL 발견, 새 탭 열기, 다음 글 이동, 목록 순회, 크롤링은 하지 않는다.

## 저장되는 것과 저장되지 않는 것

기본 root는 다음과 같다.

```text
/Users/tars/Library/Application Support/Mnemosyne
```

각 글 revision은 다음 private store에 저장된다.

```text
captures/<blog-id>/<post-id>/revisions/<revision-id>/
  post.md
  record.json
posts.jsonl
```

`post.md`는 사람이 읽는 Markdown이고, `record.json`은 해당 revision의 메타데이터, `posts.jsonl`은 canonical export다. 같은 URL identity와 제목·게시일·본문이 같은 revision은 `DUPLICATE`로 다시 저장하지 않고 export만 다시 맞춘다. 같은 글의 내용이 달라진 revision은 이전 revision을 `supersedes_revision_id`로 연결해 `REVISED`로 저장한다.

이미지, 표, 임베드, 오디오, 비디오는 보관하지 않는다. 페이지에 있으면 omission 경고가 metadata에 기록될 수 있다. 이 도구는 PDF/HTML ingestion, RAG, 모델 학습, 미디어 저장, 서버 또는 동기화를 제공하지 않는다.

## 설치와 사용

저장소 root에서 실행한다. 경로는 예시이므로 자신의 clone 위치를 사용한다.

```bash
cd /absolute/path/to/mnemosyne
/usr/bin/env PYTHONPATH=capture /opt/homebrew/bin/python3 -m mnemosyne_capture install
```

이 명령은 `Mnemosyne Capture` macOS Service와 실행 runtime을 설치하거나, 이미 설치돼 있으면 안전하게 다시 게시한다. 소스를 갱신한 뒤 Service/runtime을 다시 설치할 때도 같은 명령을 실행한다.

그 다음에는 다음 순서만 수행한다.

1. Google Chrome에서 권한 있는 현대식 `https://blog.naver.com/...` 게시글을 직접 연다.
2. macOS Services에서 `Mnemosyne Capture`를 실행한다. 단축키는 이 저장소가 지정하지 않으므로 필요하면 macOS 설정에서 사용자가 지정한다.
3. 결과 JSON의 `code`를 확인한다. `CAPTURED`, `REVISED`, `DUPLICATE`는 저장 완료다. `CAPTURED_EXPORT_STALE`은 revision은 저장됐지만 `posts.jsonl` export가 최신이 아니라는 뜻이므로 성공으로 취급하지 않는다.

사용자 기본 root 대신 격리된 저장소를 명시하려면 absolute placeholder path를 쓴다.

```bash
/usr/bin/env PYTHONPATH=capture /opt/homebrew/bin/python3 -m mnemosyne_capture \
  --data-root /absolute/path/to/Mnemosyne capture
```

## Chrome 및 macOS 권한

Chrome에서 해당 탭의 JavaScript 실행을 허용해야 한다. Chrome의 Developer 메뉴에서 JavaScript-from-Apple-Events 관련 설정이 보이면 이를 활성화한다. macOS가 Automation 권한을 요청하면, 요청한 automation 프로세스가 Google Chrome을 제어하도록 허용한다. 이미 거부했다면 macOS **Privacy & Security → Automation**에서 해당 권한을 다시 허용한 뒤 Service를 다시 실행한다.

권한은 capture 도구의 범위를 넓히지 않는다. 현재 글을 수동으로 연 뒤 Service를 실행해도 플랫폼 접근, 저작권 이용, 개인정보 처리, AI 이용 또는 공개·사칭 권한이 새로 생기지 않는다. 사용자에게 그 게시글을 열고 보관할 권한이 있을 때만 사용한다.

## Static doctor

다음은 Chrome을 제어하거나 글을 읽지 않는 read-only static 검사다.

```bash
/usr/bin/env PYTHONPATH=capture /opt/homebrew/bin/python3 -m mnemosyne_capture --json doctor
```

정상 설치와 canonical store라면 exit status `0` 및 JSON의 `"code":"READY"`, `"ok":true`를 기대한다. 설치 누락, runtime/service 불일치, private-store mode 문제, stale `posts.jsonl`, 남은 staging은 `NOT_READY`와 non-zero exit status로 보고된다. 이 명령은 live capture가 아니므로 Chrome 권한이나 열린 탭의 성공을 증명하지 않는다.

`CAPTURED_EXPORT_STALE` 또는 doctor의 `EXPORT_STALE` 뒤에는 export를 다시 만든다.

```bash
/usr/bin/env PYTHONPATH=capture /opt/homebrew/bin/python3 -m mnemosyne_capture export
```

Service/runtime 검사가 실패하면 먼저 같은 `install` 명령으로 다시 게시하고, static doctor를 다시 확인한다.

## 문제 해결

| 결과 | 조치 |
| --- | --- |
| `APPLE_EVENTS_DENIED` | macOS Automation에서 Google Chrome 제어를 허용한 뒤 다시 실행한다. |
| `JAVASCRIPT_DISABLED` | Chrome의 JavaScript-from-Apple-Events Developer 설정을 활성화하고 다시 실행한다. |
| `TAB_CHANGED` | 실행 중 탭 전환·URL 변경·새로고침을 하지 말고, 동일한 현재 탭에서 다시 실행한다. |
| `UNSUPPORTED_HOST` | 지원되는 `https://blog.naver.com/...` 게시글을 현재 탭에 연다. |
| `UNSUPPORTED_PAGE` | 현대식 지원 markup이 아닌 페이지이거나 제목·날짜·본문 검증이 실패했다. 다른 페이지로 대체하거나 수동 원본 경로를 사용한다. |
| `CAPTURED_EXPORT_STALE` | revision은 저장됐지만 export는 최신이 아니다. `export`를 실행하고 static doctor에서 `READY`를 확인한다. |
| `RUNTIME_TAMPERED` 또는 workflow/runtime 검사 실패 | 파일을 수동 편집하지 말고 `install`을 다시 실행한 뒤 static doctor를 확인한다. |

일부 진단 JSON에는 `NO_SAFARI_TAB`, `SAFARI_NOT_FRONTMOST`, `SAFARI_READY`처럼 `SAFARI_*`가 남아 있다. 이는 호환성 식별자일 뿐이며, 현재 Service가 다른 브라우저를 대상으로 한다는 뜻이 아니다. 이런 코드가 나오면 Google Chrome이 실행 중이고 대상 글이 현재 활성 탭에 있는지 확인한 뒤 다시 실행한다.

## 테스트 fixture와 live 데이터

테스트의 synthetic fixture는 브라우저를 제어하지 않는 구현 검사용 입력이다. fixture의 통과는 live Chrome capture, 실제 접근 권한, 실제 게시글의 추출 성공을 입증하지 않는다. 이 문서는 live capture를 실행하거나 사용자 데이터·URL·제목·본문을 기록한 결과가 아니다.
