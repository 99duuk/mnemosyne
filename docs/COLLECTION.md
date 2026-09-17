# 블로그 자료 수집

2026-09-16: 당분간 Mnemosyne의 우선순위는 **자료 확보와 품질 확인**이다. 페르소나/RAG/학습은 뒤로 미룬다. 대상 URL은 현재 `sofoswh`만 받았으며 같은 수집기에 다른 블로그 ID를 추가해서 사용할 수 있다.

## 실행

Node 22.13 이상이 필요하다. 현재 검증 환경은 Node 22.22.0, Playwright 1.62.1이다. `node:sqlite`는 이 버전에서 실험 기능 경고를 표시한다. Codex 데스크톱 앱은 필요하지 않다.

```sh
cd /Users/tars/Documents/workspace/mnemosyne/capture/chrome

# 카테고리 조사. 처음 지정한 블로그의 기본 범위는 전체보기다.
node collector/cli.mjs categories --blog sofoswh

# 모든 과거 페이지의 글 목록 생성. 본문 수집과 별개다.
node collector/cli.mjs discover --blog sofoswh --max-pages all

# 또는 특정 카테고리만 / 특정 카테고리 제외. ID는 선택 화면에서 확인.
node collector/cli.mjs discover --blog sofoswh --include 1,71 --max-pages all
node collector/cli.mjs discover --blog sofoswh --include 0 --exclude 14,22 --max-pages all

# 선택 화면에서 다운로드한 설정 사용
node collector/cli.mjs discover --plan ~/Downloads/sofoswh-plan.json --max-pages all
node collector/cli.mjs collect --plan ~/Downloads/sofoswh-plan.json --limit 50

# 모두 처리하거나 다음 배치로 이어가기
node collector/cli.mjs collect --blog sofoswh --limit all
node collector/cli.mjs status
```

`--max-pages` 기본 10은 한 실행에서 **새로 확인할 목록 페이지** 예산이다. `--limit` 기본 50은 한 실행의 본문 방문 예산이며 총 수집 개수 제한이 아니다. 날짜 제한도 없다. 같은 명령을 다시 실행하면 저장된 본문을 건너뛰고 이어간다. 포함·제외 설정은 블로그마다 기억하며, 전체로 돌아가려면 `--include 0 --exclude ''`을 사용한다. 다른 블로그는 `--blog 다른아이디`로 동일 순서로 실행한다. 같은 DB에서는 한 수집기만 브라우저를 사용한다.

## 카테고리와 목록의 의미

- `categories` 실행 후 데이터 폴더의 `sofoswh-planner.html`을 열면 검색 가능한 카테고리 선택 화면이 나온다. 설정 저장 버튼은 JSON을 다운로드한다. HTML은 생성 시점의 스냅샷이며 자동 수집 버튼이 아니다.
- 수집 예상 영역에 페이지당 최대 30개, 남은 목록 페이지, 본문 배치 수, 목록/본문 예상 시간을 표시한다. 방문 간격·본문 배치 크기·목록 페이지 예산을 변경하면 화면 아래 실행 명령도 바뀐다. 다운로드 JSON에는 카테고리 설정만 들어가므로 변경한 실행 옵션은 화면의 명령을 사용한다. 시간은 실측 예측이 아닌 방문 간격부터 방문당 3초 여유를 추가한 계획 범위이며 시작/재개/지연/수동 실행 대기는 별도다. 포함·제외 목록의 순회 비용을 합산하고, 확인된 기보관 글은 본문 예상에서 차감한다. 글 수를 모르면 미확인으로 표시한다.
- 상위 카테고리 목록에는 하위 글도 들어온다. 상위·하위를 같이 선택하면 상위 한 번만 순회한다.
- 제외 조건은 **제외 목록 전체를 먼저 확인**한다. 그 다음 포함 목록에서 문서 ID로 차집합을 만든다. 제외 목록이 불완전하면 본문 수집을 시작하지 않는다. 포함 목록은 부분 수집 상태에서도 확인된 글부터 처리할 수 있다.
- 전체보기 글 링크에 붙은 `categoryNo=0`은 목록 문맥이다. 그 값을 글의 실제 카테고리로 오인하지 않는다. 실제 카테고리는 본문에서 별도로 읽는다.
- 공지·추천·댓글 링크를 섞지 않고 글 목록 테이블만 읽는다. 문서 ID로 중복을 제거한다.
- 완료는 마지막 페이지 도달과 고유 문서 수/화면 표시 개수 일치를 함께 요구한다. 불일치는 `count_mismatch`로 남긴다. 페이지가 반복되거나 구조가 달라지면 멈춘다.
- 사이트의 삭제·비공개 글은 공개 목록만으로 전체 존재 여부를 알 수 없다. ‘완료’는 그때 공개 화면으로 확인한 범위다. 다른 사람의 글을 인용한 본문도 작성자 자신의 견해와 구분해 후처리해야 한다.

## 데이터 위치와 확인

기본값은 저장소 밖 `~/Library/Application Support/Mnemosyne/collection/`이다. `--dir`로 바꿀 수 있다.

| 파일 | 용도 |
|---|---|
| `collection.sqlite` | 원본 레코드, 문서 상태, 목록 체크포인트, 관측 이력 |
| `posts.jsonl` | 기존 HTML 뷰어에 넣는 현재 본문 export |
| `<blog>-planner.html` | 카테고리 선택과 목록 진행 스냅샷 |
| `<blog>-categories.json` / `<blog>-plan.json` | 카테고리 조사 결과 / 현재 설정 |
| `<blog>-selection.jsonl` | 현재 포함·제외 조건을 적용한 글 목록. 본문 파일과 별개이며 부분 조사 중일 수 있음 |
| `profile/` | 이 수집기만의 Chromium 프로필. 평소 Chrome 프로필·쿠키를 가져오지 않음 |

DataGrip에서 SQLite 데이터 소스로 `collection.sqlite`을 연다. `current_posts` 뷰에서 제목·날짜·카테고리·본문·품질 표시를 볼 수 있다. `documents`는 전체 발견 목록이라 현재 제외한 글도 들어 있다. 제외는 수집 대상 선택이며 이미 보관한 글을 삭제하지 않는다. `records`는 콘텐츠 버전, `observations`는 관측 시점, `inventories`는 카테고리별 목록 상태다. 이미지·댓글 수 같은 지표를 저자 견해의 진실성 척도로 사용하지 않는다.

```sql
SELECT blog, status, COUNT(*) FROM documents GROUP BY blog, status;
SELECT document_id, title, published_at, category, length(body), quality_flags
FROM current_posts ORDER BY published_at DESC;
```

이전 50개는 다음으로 가져올 수 있다. 원래 파일은 그대로 보존한다.

```sh
node collector/cli.mjs import --file '/path/to/old/posts.jsonl'
node collector/cli.mjs export
```

## 보존하는 내용과 아직 없는 내용

| 데이터 | 현재 처리 / 이유 |
|---|---|
| 본문 원문·제목·정규 URL·블로그 ID | 기존 extension revision 검증 유지. 원문과 zero-width 문자만 제거한 정규화본을 구분 |
| 게시일 원문·수집 시각 | 절대 날짜는 분/일 정밀도를 보존. ‘5시간 전’은 정확한 시각으로 꾸며내지 않고 관측 시각을 기준으로 5~6시간 전 범위와 `DATE_RELATIVE_RANGE`를 기록 |
| 실제 카테고리·표시 작성자·태그 | DOM에서 확인되는 값만 보존. 다른 스킨의 태그/작성자 선택자는 추가 검증 필요 |
| 순서 있는 문단·인용·표 셀·캡션 | 표와 인용을 본문 문체에 무작정 섞지 않도록 별도 `blocks` |
| 본문 링크 | 근거·후속 글 연결용. 링크된 외부 페이지까지 방문하지 않음 |
| 이미지 주소·alt·설명 / 미디어 주소 | 도표·기사 캡처의 위치를 찾기 위한 참조. 이미지 파일 보존·OCR·음성 전사는 미구현 |
| 정리한 본문 DOM 조각 | 스크립트·이벤트·삽입 문서를 제거한 HTML을 gzip BLOB과 SHA-256로 보존. 전체 응답 원본 HTML은 아님. 뷰어에서 HTML로 실행하지 않음 |
| content hash·추출기 버전·관측 이력 | 상대 날짜 표시만 달라지는 것을 새로운 내용으로 취급하지 않음. 같은 내용의 관측은 이력으로 분리 |
| 댓글·공감·조회수 | 기본 수집하지 않음. 제3자 발언 혼입과 데이터 변동이 큼 |

`stored`는 보관 성공을 의미하며 텍스트가 완전하거나 후처리가 필요 없다는 뜻이 아니다. 짧은 글, 이미지/미디어 생략, 인용, 불명확한 날짜, 이전 텍스트 전용 자료는 품질 표시를 남긴다. 20자 미만/이미지만 있는 글이나 구형 에디터 등 미지원 구조는 `review`로 남기며 빈 본문을 성공으로 기록하지 않는다. 구형 에디터 지원과 OCR은 다음 품질 개선 과제다. 모든 레코드는 여전히 `UNREVIEWED`, `rag_eligible=false`다.

### 추후 미디어 수집 과제

텍스트가 충분히 쌓인 뒤에는 미디어도 수집할 필요가 있다. 이미지·표·임베드가 글의 근거와 맥락을 이루는 경우가 있기 때문이다. 현재는 실제 파일을 받지 않고 URL·alt·캡션·위치만 보존한다. 향후에는 다음 순서로 별도 보강 작업을 한다.

1. 이미지의 lazy-load 주소를 찾아 파일 형식·크기·가로세로·SHA-256과 본문 위치를 기록한다.
2. 파일은 게시물과 분리된 `assets/`에 해시 기반으로 저장해 여러 글에 반복된 이미지가 중복 저장되지 않게 한다.
3. 표는 행·열·셀 병합·캡션을 구조로 보존하고 검색용 텍스트 표현을 별도로 만든다.
4. 외부 영상·임베드는 무조건 파일을 내려받지 않고 플랫폼·URL·제목·썸네일·위치를 먼저 보존한다.
5. 이미지 OCR은 선택 단계로 실행하고 원본 이미지, OCR 문장, 언어·신뢰도를 서로 연결한다. OCR·표·인용은 블로거의 직접 본문과 분리한다.

미디어 보강은 본문 `--refresh`와 별도 단계로 설계한다. 본문 내용 해시와 미디어 해시를 분리해 미디어가 추가되었다는 이유만으로 같은 글의 본문을 불필요하게 중복 버전으로 만들지 않는다. 현재 `--load-media`는 브라우저 리소스 로딩 허용 옵션일 뿐 실제 파일 보존 기능이 아니다.

## 속도와 재시작

- RSS의 최신 50개 제한을 버리고 공개 글 목록의 **30줄 보기**와 페이지 이동을 사용한다. 숨겨진 수집 API, 프록시, 지문 위장, CAPTCHA 해제 기능은 없다.
- 브라우저 1개/순차 방문, 목록·본문 이동 간 기본 최소 5초. 선택적 `--interval` 최솟값은 3초이며 어느 값도 차단되지 않는 속도라는 보장은 없다.
- 기본적으로 이미지·영상·폰트 요청을 생략한다. `--load-media`로 일반 리소스 로딩과 비교할 수 있다. Playwright routing 사용 시 HTTP 캐시가 비활성화되므로 실제 트래픽 절감량은 별도 측정해야 한다. 이 모드도 일반 페이지 스크립트와 여러 요청을 발생시킨다.
- 이미 확정된 본문은 방문하지 않는다. 목록은 페이지마다, 본문은 글마다 SQLite 트랜잭션으로 보존한다. DB commit/readback 성공 뒤에만 확장 프로그램의 임시 복사본을 지운다. 확장 프로그램 저장 공간에 전체 corpus를 계속 쌓지 않는다.
- 목록 재개 때 앞선 페이지를 겹쳐 확인한다. 실행 도중 글 추가/삭제로 개수가 맞지 않으면 완료로 표시하지 않는다. `discover --refresh`로 새 목록 조사를 시작할 수 있다. 기존 본문은 유지한다.
- 새로운 글만 주기적으로 확인하려면 `discover --refresh --max-pages 2` 뒤 `collect`를 실행한다. 이는 최신 일부 목록 조사다. 과거 수정/삭제의 완전한 탐지는 아니며 기존 글 수정 확인은 `collect --refresh`로 명시한다. 자동 스케줄러/삭제 전파는 아직 없다.
- 접근 응답 HTTP 401/403/429, 알려진 로그인 이동·CAPTCHA·안내 신호를 관찰하면 전체 실행을 멈추고 정지 상태를 DB에 남긴다. 재실행으로 자동 해제되지 않는다. 감지는 모든 제한 유형을 포괄하지 않는다.
- `Retry-After`가 있으면 최소 재시도 시각을 기록한다. 제한 상황을 직접 확인한 뒤 `clear-stop`을 실행해야 하며 해당 시각 이전에는 해제되지 않는다. 일반 오류도 무한 반복하지 않는다. 세 글 연속 실패 시 배치를 멈추고 개별 실패는 `review`로 보존한다. `--retry-review`는 검토 후 재시도용이다.

## 검증과 다음 순서

`npm test`는 합성 자료로 카테고리 포함/제외, 불완전 제외 목록 차단, 한 페이지 예산으로 재시작 후 진행, 문서 중복, 손상된 hash 거부, DB 재열기, 상대 날짜 변경, 표/인용/이미지 참조, 확장 staging 삭제 순서, 429 정지를 검증한다. `npm run test:browser`는 기존 확장의 저장/중복/수정/한도/재시작 검증이다.

다음은 각 블로그에서 오래된 글·표 많은 글·이미지 위주 글을 골라 추출 품질을 먼저 점검한 후, 전체 목록을 확정하고 몇 년치 본문을 배치로 보존하는 순서다. 본문이 없거나 인용 위주인 글은 총 글 개수와 별개로 집계해야 한다. 후가공에 충분한 자료인지 판단할 때는 기간·주제·직접 발언의 범위를 함께 본다.

참고: [Playwright 확장 실행](https://playwright.dev/docs/chrome-extensions), [Chrome storage](https://developer.chrome.com/docs/extensions/reference/api/storage), [Node SQLite](https://nodejs.org/download/release/v22.13.1/docs/api/sqlite.html).
