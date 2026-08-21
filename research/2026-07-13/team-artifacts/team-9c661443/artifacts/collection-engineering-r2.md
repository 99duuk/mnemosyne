# Non-bypass NAVER Blog acquisition design

Research valid at: 2026-07-13 (Asia/Seoul). This is an engineering design, not a conclusion that copyright, privacy, or platform permission exists. Every network adapter is deny-by-default and requires its own recorded policy approval.

## 1. Executive decision

Use an owner-mediated, offline export as the authoritative corpus lane:

1. The blog owner creates NAVER's built-in PDF backups in the account UI and supplies a signed inventory manifest plus any separately owned original media.
2. The system ingests those local files without logging in to NAVER, rendering NAVER pages, calling undocumented endpoints, or defeating access controls.
3. RSS is disabled. NAVER's help center says RSS is supported over HTTPS and HTTP/1.1+, but `rss.blog.naver.com/robots.txt` currently says `User-agent: * / Disallow: /`. In addition, the main and mobile blog robots files explicitly state that bot access for AI training and RAG is prohibited. This unresolved first-party contradiction is a stop condition, not permission to choose the more convenient source.
4. The Search API is disabled for corpus acquisition. It is a query-result API, not an owner-post enumeration/export API; it returns title, URL, passage, blogger fields, and date, has a 1,000-result window, and its terms restrict unauthorized copying, storage, processing, and repeated automation outside the approved application scope. It can be enabled only as an ephemeral public-search witness after NAVER confirms the registered reconciliation use. It is never a completeness oracle or a source of training text.
5. Absence from RSS, Search API, or a public page never means deletion. Only an owner-signed inventory transition creates a deletion/private tombstone.

This design deliberately does not include authenticated browser automation, CAPTCHA handling, IP rotation, internal/mobile API calls, DOM scraping, or direct media URL harvesting.

### Exact acquisition decision tree

```text
START
  |
  +-- Does the account owner provide current, purpose-specific consent?
  |      +-- no -> STOP; acquire nothing
  |      +-- yes
  |
  +-- Can the owner create a signed row-complete inventory + NAVER PDF backup?
  |      +-- yes -> ingest offline owner package (PRIMARY PATH)
  |      |           |
  |      |           +-- Need original media omitted/downscaled by PDF?
  |      |                  +-- owner supplies local originals + ownership evidence -> quarantine/review
  |      |                  +-- otherwise -> record asset gap; do not fetch media URLs
  |      |
  |      +-- no -> counts/PDF only may be ingested as PARTIAL/UNKNOWN;
  |                 do not claim completeness and request owner manifest correction
  |
  +-- Need incremental updates?
  |      +-- owner signed inventory/change ledger + delta PDF -> revision/tombstone diff
  |      +-- no modification evidence -> freshness UNKNOWN; periodic full owner audit
  |
  +-- Considering Search API as public witness?
  |      +-- no active written approval for registered purpose/frequency/storage -> DISABLED
  |      +-- approved -> ephemeral ID-only witness within scope/limits; never corpus/completeness source
  |
  +-- Considering RSS as public witness?
  |      +-- no written resolution of RSS-help/robots/AI-RAG conflict -> DISABLED
  |      +-- approved -> conditional feed-only polling; never follow post/media links;
  |                     never infer deletion from absence
  |
  +-- Considering live Blog pages, undocumented APIs, login automation,
          CAPTCHA handling, proxy/IP rotation, or robots/access-control bypass?
         +-- yes -> STOP; prohibited path
         +-- no -> continue only on the approved branch above
```

## 2. Evidence-backed constraints

### Owner export

NAVER's official backup help says the owner can save blog posts as PDF. It also says:

- only directly authored posts are saved; memo, scrap, and disciplined posts are excluded;
- some attachments are not represented (story photo, Flash, music player, files, polls, schedules), while maps and video are thumbnails;
- layout is partly preserved, but font size and alignment are normalized and large images are resized;
- maximum 100 posts and 500 MB per PDF, a 3 GB total allocation (also stated as the maximum generated per day), and 20 generated PDFs.

Consequences:

- PDF is authoritative for the selected textual snapshot, not a lossless account export;
- comments are not promised by the backup documentation and must be treated as absent;
- asset completeness and semantic-component fidelity need separate metrics from post inventory coverage;
- an inventory manifest is mandatory because a PDF batch alone does not prove that every account post was selected;
- if 20 PDFs/3 GB is insufficient, split work across supported owner-operated batches/days. Do not automate the UI. If the UI will not create another batch, stop and use support rather than workaround behavior.

### SmartEditor variants

- NAVER says SmartEditor ONE is the current default and SmartEditor 2.0 ended in November 2022.
- A first-party 2017 notice documents the historical SmartEditor 3.0 transition for the former writing API.
- SmartEditor ONE supports many semantic components (text styles, headings, quotes, images, video, place, links, files, schedules, tables, equations), but the official PDF path flattens or omits some of them.
- The official SmartEditor2 OSS repository shows that the legacy editor had WYSIWYG, HTML, and text modes and a plugin architecture. This is historical format evidence, not a supported parser for current Blog pages.

Therefore the ingestion contract is editor-agnostic. It never relies on live CSS classes or internal JSON. `source_editor_hint` can be `one`, `se3`, `se2`, `older`, or `unknown`, but an inferred hint is never used as identity or a rights decision.

### Search API

Official limits and shape:

- HTTPS GET with registered client ID/secret;
- `display` maximum 100;
- `start` maximum 1,000;
- `sort=sim|date`;
- 25,000 calls/day across the Search API for the client;
- results contain total/start/display and items with title, link, description passage, blogger name/link, and post date.

It has no documented `blog_id`, account enumeration, modified timestamp, deleted/private-post, full-body, or cursor-after-1,000 capability. Search results are also not a faithful public inventory: NAVER's help says new/modified posts can take up to 24 hours to appear and exposure is not guaranteed. The API `total` is a search total, not an export count.

The current API terms state that API-acquired data must not be copied/stored/cached/processed outside the allowed purpose; one app has one client ID; multiple IDs cannot be used to expand quota/extract data; result copyright remains with NAVER or the original rightsholder; search results must be independently displayed without alteration. A 2025 amendment notice further says access is client-ID scoped and pre-approval is required for automated, periodic/repetitive use outside granted purpose/frequency. The 25,000 daily quota is a ceiling, not permission to build a corpus.

### RSS/robots contradiction

First-party observations on 2026-07-13T10:57:49Z:

| URL | Observation | SHA-256 of fetched robots text |
|---|---|---|
| `https://blog.naver.com/robots.txt` | explicit English prohibition on bot access for AI training/RAG; named AI agents disallowed | `b0a0a5a0aa415af00955e98be932403dc9d99fcb7626b45fcd169b97e1c113b4` |
| `https://m.blog.naver.com/robots.txt` | same explicit prohibition; named AI agents disallowed | `979cea518bc8905333bb407fb58db4d445d591d182399e1593d6781e32acf3be` |
| `https://rss.blog.naver.com/robots.txt` | `User-agent: *` then `Disallow: /` | `2dff46c43bf5ed9611b25434c4e2110a574470d722e70dff1e2d99ba4289a2f5` |

Yet the official RSS notice instructs subscribers to use `https://rss.blog.naver.com/...` over HTTP/1.1+ and says HTTP/1.0 stopped working on 2025-12-04. Another official help page says disabling a post's external-send setting prevents it from appearing in RSS.

Resolution: this proves RSS exists for subscription but does not resolve whether automated AI-corpus acquisition is allowed. For this use, `RSS_ENABLED=false` until NAVER supplies written, purpose-specific authorization that addresses the robots rule and storage/training. Owner consent alone cannot waive NAVER's endpoint rules. If authorization is later granted, retain the approval record and restrict the adapter to that account/purpose.

## 3. Acquisition contract

### Required owner package

Each delivery is a signed directory (or encrypted equivalent):

```text
delivery-<owner>-<snapshot-time>/
  delivery.json                 # owner, consent, purpose, timestamps, counts
  inventory.csv                 # one row per known post/lifecycle record
  batches/
    batch-0001.pdf
    batch-0001.manifest.csv     # selected rows in PDF order, if known
  media/                        # optional owner-held originals only
  media.csv                     # post ID, local path, type, ownership assertion
  changes.csv                   # optional owner change ledger since prior snapshot
  SHA256SUMS
  SIGNATURE
```

Minimum `inventory.csv` fields:

```csv
provider,owner_subject_id,blog_id_alias,log_no,title,published_at,modified_at,category_path,visibility,lifecycle_state,authorship,export_batch,export_ordinal
```

Rules:

- `log_no` is required for a completeness claim. If it is unavailable, the row remains provisional and the run cannot report canonical completeness.
- `modified_at` may be blank if the owner UI does not provide it. In that case edited-old-post detection is `unknown` unless `changes.csv` or a full re-export supplies evidence.
- `lifecycle_state` is `active|private|deleted|excluded_by_owner|unavailable_by_export_design`.
- `authorship` is `owner_original|coauthored|scrap|memo|unknown`; only `owner_original` is eligible by default.
- Counts/screenshots without row IDs can validate a partition count but cannot prove set equality.
- Inventory preparation is performed by the owner in supported UI workflows. The system does not log in on the owner's behalf.

### Canonical identity

Parse supported URL forms only from owner-provided PDF annotations/manifest data:

- `https://blog.naver.com/<blogId>/<logNo>`
- `https://m.blog.naver.com/<blogId>/<logNo>`
- `.../PostView.naver?blogId=<blogId>&logNo=<logNo>`

Strip tracking parameters. Do not dereference URLs.

Canonical key:

```text
document_id = UUIDv5(NAVER_BLOG_NAMESPACE,
                     "naver_blog:" + owner_subject_id + ":" + decimal(log_no))
```

`blog_id` is an alias, not identity. NAVER officially says an eligible owner can change the Blog ID once; post numbers and relationships remain while old links are guaranteed to redirect for only three months and may later stop. Preserve aliases with validity intervals. If `log_no` is absent, issue a `provisional_document_id` from owner + normalized title + publication time + artifact fingerprint; never merge it automatically with a canonical record.

## 4. Deployable relational schema (PostgreSQL 16)

```sql
create type acquisition_channel as enum ('owner_pdf','owner_media','owner_manifest','rss','search_api');
create type lifecycle_state as enum ('active','private','deleted','excluded_by_owner','unavailable_by_export_design');
create type quarantine_state as enum ('eligible','quarantined','rejected');
create type block_origin as enum ('owner_original','explicit_quote','suspected_quote','third_party_comment','media_ocr','platform_ui','unknown');

create table owner_subject (
  owner_subject_id uuid primary key,
  provider text not null check (provider = 'naver_blog'),
  consent_record_uri text not null,
  consent_scope jsonb not null,
  consent_version text not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);

create table account_alias (
  owner_subject_id uuid not null references owner_subject,
  blog_id text not null,
  valid_from timestamptz,
  valid_to timestamptz,
  evidence_artifact_id uuid,
  primary key (owner_subject_id, blog_id)
);

create table policy_approval (
  approval_id uuid primary key,
  channel acquisition_channel not null,
  owner_subject_id uuid references owner_subject,
  purpose text not null,
  scope jsonb not null,
  issuer text not null,
  evidence_uri text not null,
  valid_from timestamptz not null,
  valid_to timestamptz,
  revoked_at timestamptz,
  constraint_hash char(64) not null
);

create table inventory_snapshot (
  snapshot_id uuid primary key,
  owner_subject_id uuid not null references owner_subject,
  effective_at timestamptz not null,
  manifest_sha256 char(64) not null,
  owner_signature_uri text not null,
  declared_total integer not null check (declared_total >= 0),
  identity_complete boolean not null,
  modification_time_complete boolean not null,
  unique (owner_subject_id, effective_at)
);

create table document (
  document_id uuid primary key,
  owner_subject_id uuid not null references owner_subject,
  provider_post_id numeric(20,0),
  id_confidence text not null check (id_confidence in ('canonical','provisional')),
  first_seen_at timestamptz not null,
  unique nulls not distinct (owner_subject_id, provider_post_id)
);

create table inventory_item (
  snapshot_id uuid not null references inventory_snapshot,
  document_id uuid not null references document,
  title text not null,
  published_at timestamptz,
  modified_at timestamptz,
  category_path text,
  visibility text not null,
  lifecycle lifecycle_state not null,
  authorship text not null,
  source_row_sha256 char(64) not null,
  primary key (snapshot_id, document_id)
);

create table source_artifact (
  artifact_id uuid primary key,
  owner_subject_id uuid not null references owner_subject,
  channel acquisition_channel not null,
  captured_at timestamptz not null,
  source_uri text,
  local_object_uri text not null,
  media_type text not null,
  byte_length bigint not null check (byte_length >= 0),
  sha256 char(64) not null unique,
  owner_signature_verified boolean not null,
  immutable boolean not null default true
);

create table artifact_member (
  artifact_id uuid not null references source_artifact,
  document_id uuid not null references document,
  export_ordinal integer,
  page_start integer,
  page_end integer,
  mapping_confidence numeric(4,3) not null check (mapping_confidence between 0 and 1),
  mapping_method text not null,
  primary key (artifact_id, document_id)
);

create table document_revision (
  revision_id uuid primary key,
  document_id uuid not null references document,
  artifact_id uuid not null references source_artifact,
  parser_version text not null,
  source_editor_hint text not null,
  normalized_sha256 char(64) not null,
  source_fidelity jsonb not null,
  published_at timestamptz,
  captured_at timestamptz not null,
  supersedes_revision_id uuid references document_revision,
  quarantine quarantine_state not null,
  unique (document_id, artifact_id, parser_version)
);

create table content_block (
  block_id uuid primary key,
  revision_id uuid not null references document_revision on delete cascade,
  ordinal integer not null,
  block_type text not null,
  text_content text,
  page_no integer,
  bbox jsonb,
  origin block_origin not null,
  origin_confidence numeric(4,3) not null check (origin_confidence between 0 and 1),
  quarantine quarantine_state not null,
  rights_decision_id uuid,
  normalized_sha256 char(64),
  unique (revision_id, ordinal)
);

create table media_asset (
  media_id uuid primary key,
  document_id uuid not null references document,
  artifact_id uuid references source_artifact,
  media_kind text not null,
  representation text not null check (representation in ('owner_original','pdf_embedded','thumbnail','placeholder','omitted')),
  sha256 char(64),
  perceptual_hash text,
  ownership_assertion text,
  quarantine quarantine_state not null,
  metadata jsonb not null
);

create table rights_decision (
  rights_decision_id uuid primary key,
  subject_type text not null,
  subject_id uuid not null,
  decision quarantine_state not null,
  rationale text not null,
  evidence_uris jsonb not null,
  reviewer text not null,
  decided_at timestamptz not null
);

create table sync_run (
  run_id uuid primary key,
  owner_subject_id uuid not null references owner_subject,
  channel acquisition_channel not null,
  approval_id uuid references policy_approval,
  idempotency_key text not null unique,
  started_at timestamptz not null,
  finished_at timestamptz,
  checkpoint jsonb not null,
  status text not null,
  metrics jsonb not null
);

create table tombstone (
  owner_subject_id uuid not null references owner_subject,
  document_id uuid not null references document,
  effective_at timestamptz not null,
  new_state lifecycle_state not null,
  evidence_snapshot_id uuid not null references inventory_snapshot,
  applied_downstream_at timestamptz,
  primary key (owner_subject_id, document_id, effective_at)
);

create table failure_queue (
  failure_id uuid primary key,
  run_id uuid not null references sync_run,
  stage text not null,
  artifact_id uuid references source_artifact,
  document_id uuid references document,
  error_class text not null,
  retryable boolean not null,
  attempt integer not null,
  next_attempt_at timestamptz,
  diagnostic jsonb not null,
  resolved_at timestamptz
);
```

Add object-store retention/crypto controls outside PostgreSQL. Raw artifacts are append-only and version-preserving while authorized and retained; this does not override erasure, retention expiry, key destruction, or rights revocation. Revocation/deletion first propagates ineligibility/tombstones and then performs controlled physical erasure or crypto-erasure; content-free lineage may remain under governance policy.

## 5. Pipeline

```text
OWNER UI -> signed PDF/manifest/media package
              |
              v
        checksum/signature gate
              |
       immutable raw object store
              |
      PDF preflight + ID resolver
        |                  |
        | low confidence   +-> mapping quarantine/manual review
        v
  page/layout extraction -> component normalization
        |                       |
        |                       +-> quote/comment/media OCR quarantine
        v
  revision/content hashes -> exact/near-duplicate clustering
        |
  inventory set reconciliation -> completeness vector/report
        |
  eligible revision view -> downstream index/training
```

Stages and hard gates:

1. **Policy/consent gate.** Confirm active owner consent and delivery purpose. Network channels additionally require an unexpired `policy_approval`. `owner_pdf` never inherits permission from `rss`/`search_api` or vice versa.
2. **Package preflight.** Verify signature and every SHA-256, MIME sniffing, size, PDF page readability, encryption state, and declared batch membership. Never trust file names.
3. **Immutable staging.** Put by content hash; create `source_artifact` transactionally. Duplicate hash makes the run idempotent.
4. **Segmentation/mapping.** Prefer explicit batch manifest and PDF hyperlink annotations. `pdfplumber` provides page coordinates and hyperlink annotations; use it as a pinned extractor, but require mapping confidence 1.0 for canonical publish. Header/title/date heuristics can suggest mappings, not finalize them.
5. **Text extraction.** Extract characters with positions, de-duplicate overprinted glyphs, retain page/bounding-box evidence, and compare normalized output with rendered pages. OCR only owner-supplied scanned pages locally; OCR text has its own confidence and never silently replaces native text.
6. **Component normalization.** Map headings/paragraphs/lists/tables/quotes/images/video/map/file/schedule/equation/placeholders into blocks. Preserve unknown components as `unknown`; do not discard them.
7. **Origin/rights classification.** Quarantine all explicit/suspected quotations, comments, platform chrome, unknown origin, and media OCR. Owner confirmation can establish authorship evidence but must not be treated as platform permission or third-party rights.
8. **Revisioning/dedup.** Create a new immutable revision when normalized content changes. Never overwrite earlier text or collapse source-distinct posts automatically.
9. **Inventory diff.** Reconcile expected IDs with imported IDs and prior snapshot. Only owner evidence changes lifecycle state.
10. **Publish.** Expose only `active + owner_original + eligible` blocks from a consent-valid revision. Downstream stores consume tombstone events and acknowledge deletion.

## 6. Quote, comment, and media quarantine

### Quotes

PDF can destroy editor semantics. Classify per block:

- `explicit_quote`: owner manifest/component evidence, visible quote styling/border/indentation plus attribution, or a clear quoted source marker;
- `suspected_quote`: long cited passage, attribution language, visually distinct inset, or uncertainty caused by flattened layout;
- `owner_original`: only after evidence and no quote signal;
- `unknown`: extraction/mapping ambiguity.

Both quote classes and `unknown` are excluded by default. Store page/bbox and the evidence that triggered classification. Do not use Internet similarity search against NAVER pages to resolve quotation ownership. Manual review can use owner-provided source records.

### Comments

Comments are a separate third-party dataset, not author prose. The official PDF export does not promise them. Do not scrape them. If an owner later supplies an approved export, store them in a separate quarantined collection with commenter identity minimized; do not merge with the post or infer the owner's views from them. Even owner-authored replies remain excluded unless the surrounding third-party conversation and purpose have separately cleared governance review.

### Media

- PDF embedded image: preserve exactly as rendered and label `pdf_embedded`, not original.
- Map/video thumbnail: preserve only the PDF representation; do not call the linked service or media CDN.
- Omitted attachment: create an expected placeholder from owner manifest; asset coverage remains incomplete.
- Owner-supplied original: hash, malware-scan, map to a post, and retain ownership evidence.
- OCR/captions: isolate as `media_ocr`/metadata and quarantine; screenshots often contain third-party text.
- Faces, location, EXIF, signatures, and other sensitive content require the governance/security review; they are not automatically made training-eligible by owner possession.

## 7. Deduplication and revision policy

Apply in this order:

1. **Artifact exact:** same byte SHA-256 -> one raw artifact, many delivery references if necessary.
2. **Source identity exact:** same owner + `log_no` -> same document, multiple revisions.
3. **Revision exact:** SHA-256 of canonical block stream (Unicode NFKC, normalized line endings/whitespace, platform headers/footers excluded but punctuation retained) -> same normalized revision.
4. **Near duplicate:** Korean-aware character 5-gram MinHash plus sentence embedding similarity generates a review cluster only. It never deletes or merges automatically.
5. **Media:** cryptographic hash for exact bytes; perceptual hash only for candidate grouping.

Do not collapse two post IDs merely because they have identical text: reposts have distinct lifecycle/provenance. For downstream training, choose at most one cluster representative only after rights and revision precedence, while all source records stay in lineage.

## 8. Completeness algorithm

Completeness is a vector, not one percentage.

Let:

- `E_t`: all canonical IDs in owner-signed inventory snapshot `t` whose lifecycle is in the requested scope;
- `P_t`: canonical IDs mapped from owner PDFs for snapshot `t`;
- `F_t`: IDs with a fresh revision (`captured_at >= modified_at`), where modified time is known;
- `A_t`: IDs whose expected media/assets are present at requested fidelity;
- `R_t`: IDs with at least one eligible owner-original block after quarantine;
- `U_t`: unresolved/provisional mappings;
- `X_t`: imported IDs absent from `E_t`.

Report:

```text
inventory_coverage = |E_t intersect P_t| / |E_t|
freshness_coverage = |F_t| / |{e in E_t : modified_at is known}|
asset_coverage     = fulfilled_expected_assets / expected_assets
eligibility_coverage = |R_t| / |E_t|
missing_ids        = E_t - P_t
extra_ids          = P_t - E_t
unresolved_ids     = U_t
```

Guard conditions:

- If `identity_complete=false`, `inventory_coverage` is **UNKNOWN**, even when counts happen to match.
- If the denominator is zero, report `NOT_APPLICABLE`, not 100%.
- If any imported artifact has an unresolved member mapping, declared-scope completeness cannot pass.
- If `modified_at` is incomplete and no owner change ledger/full re-export exists, edited-old-post freshness is `UNKNOWN`.
- Text inventory can be complete while asset or semantic fidelity is incomplete; never average dimensions.
- API/RSS witness IDs may produce `public_witness_seen`, never enter `E_t` and never reduce `missing_ids`.

Partition proof:

1. Owner partitions inventory by visibility x category x time range using mutually exclusive predicates.
2. Check row uniqueness and `sum(partition rows) = declared_total`.
3. For each PDF batch, require selected canonical IDs and `count <= 100`; verify its manifest hash/signature.
4. Set-equal the union of in-scope PDF IDs with in-scope expected IDs.
5. Generate sorted `(document_id, latest_revision_hash, lifecycle)` leaves and store a snapshot Merkle root for repeatable audits.

Status:

- `COMPLETE_RELATIVE_TO_OWNER_DECLARED_SCOPE_AT_CUTOFF`: set equality against the signed inventory version, zero unresolved mappings, freshness established for every declared in-scope row, all submitted artifacts verified. This does not establish that deleted, private, historically omitted, never-declared, or platform-excluded items are absent.
- `CONTENT_COMPLETE_ASSET_INCOMPLETE`: set/freshness complete but PDF cannot supply all expected assets.
- `PARTIAL`: known missing/extra/stale rows.
- `UNKNOWN`: no row-complete inventory, provisional IDs, or unverifiable edit times.

## 9. Incremental synchronization

There is no documented official read API for the owner's complete Blog inventory or modified timestamps. Incremental sync is therefore owner-driven:

```text
I_prev = previous signed inventory
I_now  = current signed inventory

new_ids       = ids(I_now) - ids(I_prev)
removed_ids   = ids(I_prev) - ids(I_now)  # candidate only
state_changes = same IDs with changed lifecycle/visibility/category
changed_ids   = same IDs with newer modified_at OR listed in owner changes.csv
```

- Export `new_ids + changed_ids` to PDFs and ingest as new revisions.
- Convert `removed_ids` to tombstones only when the current signed inventory explicitly labels them deleted/private/excluded. Mere disappearance is an unresolved discrepancy.
- If modified timestamps are unavailable, require the owner to maintain `changes.csv` and perform periodic full re-export/hash audit. No RSS/API algorithm can guarantee old-edit detection.
- A practical cadence is event-driven for edits/deletions plus a quarterly full owner audit; cadence is an operational choice, not an official NAVER guarantee.
- Keep revisions by capture time. A public-to-private transition blocks every downstream representation immediately but preserves restricted lineage until governed erasure.

## 10. Network adapters if later approved

Both adapters ship disabled:

```text
NAVER_RSS_ENABLED=false
NAVER_SEARCH_API_ENABLED=false
NAVER_POLICY_APPROVAL_ID=
```

Startup fails closed unless approval is active, purpose/account match, and the operator acknowledges the current constraint hash.

### Search API witness (not acquisition)

- registered application/client only; secret in a vault;
- never multiple client IDs for quota expansion;
- transient response only; no passage/title corpus storage unless written authorization expressly permits it;
- filter `bloggerlink` to the owner alias in memory and compare only canonical IDs that can be parsed without dereferencing;
- internal conservative limiter after approval: 0.2 request/s, burst 1, default daily 1,000, non-configurable absolute stop at 24,000 to leave headroom below the official 25,000 ceiling;
- page with `display=100`, but stop before any request would exceed the documented 1,000-result window;
- honor `Retry-After`; exponential backoff with full jitter for 429/5xx; no retries for 400/401/403; trip circuit breaker after five consecutive transient failures;
- retain only operational request metadata/aggregate witness result if allowed, never client secret or raw response in logs.

The 0.2 request/s and 1,000/day defaults are conservative engineering controls, not published NAVER QPS limits. Written approval controls if stricter.

### RSS witness

Only after written resolution of the robots contradiction:

- HTTPS and HTTP/1.1+;
- an identified, purpose-specific user agent and contact;
- one account feed, no crawling linked posts or media;
- conditional GET with ETag/Last-Modified when supplied, using a SHA-pinned feed parser;
- initial engineering interval 6 hours, adaptive slower when unchanged; approval can impose a different minimum;
- sanitize embedded markup, reject unsafe schemes, isolate malformed (`bozo`) entries, cap response bytes/items, and never render HTML;
- stop immediately on 401/403/410, robots/policy change, approval expiry, or owner revocation;
- feed absence never causes deletion.

## 11. Failure recovery

| Failure | Classification | Recovery |
|---|---|---|
| Signature/checksum mismatch | permanent/security | quarantine whole delivery; require owner re-delivery |
| PDF encrypted/corrupt | permanent until new file | preserve artifact, dead-letter, request supported re-export |
| Font/text extraction low confidence | reviewable | render page, local OCR fallback, compare, manual mapping; never silently publish |
| Missing `log_no`/ambiguous segmentation | reviewable | provisional ID and mapping quarantine; request owner manifest correction |
| Parser crash | retryable once fixed | checkpoint by artifact/page, pin parser version, reprocess same raw object idempotently |
| API 429/5xx after approval | transient | Retry-After/full jitter/circuit breaker; no concurrency escalation |
| API 400/401/403 | permanent/config/policy | stop adapter; do not bypass or rotate credentials |
| RSS robots/policy change | policy | disable adapter and require new approval |
| Inventory/PDF mismatch | data | publish unaffected canonical rows only if policy allows; completeness remains PARTIAL/UNKNOWN |
| Downstream tombstone not acknowledged | critical | block new release; retry event and audit every consumer |

Every stage writes a checkpoint only after its database transaction and object-store write commit. Replays use the same idempotency key. Parser upgrades create new revisions/blocks from the same immutable artifact, so recovery never needs to reacquire content. Diagnostics contain hashes/IDs and bounded error details, not full post text, credentials, or owner PII.

## 12. Deployment acceptance tests

1. A delivery with a bad signature produces zero published revisions.
2. The same delivery run twice produces no duplicate artifact/document/revision.
3. Blog ID alias change maps the same `log_no` to the same document.
4. Two different `log_no` values with identical text remain two documents and one near-duplicate cluster.
5. A PDF whose manifest says 101 posts is rejected before parsing.
6. Explicit quote and media OCR blocks never enter the eligible view.
7. A missing RSS/API witness never creates a tombstone.
8. A signed owner transition to private emits a tombstone and blocks all downstream variants.
9. Unknown `modified_at` causes freshness `UNKNOWN`, not 100%.
10. RSS/API startup without an active channel-specific approval fails closed.
11. API paging never requests a range beyond the documented 1,000-window and never crosses the local daily cap.
12. After replaying tombstones and rights revocations, restore reproduces the active authorized snapshot hashes and Merkle root; deleted content remains absent or cryptographically inaccessible. A content-free historical root may remain for audit.

## 13. Sources and pinned OSS

Primary first-party sources:

1. NAVER Blog backup limits/omissions: https://help.naver.com/service/5593/contents/15293?lang=ko&osType=PC
2. NAVER PDF creation workflow: https://help.naver.com/service/5593/contents/15295?lang=ko&osType=PC
3. Blog ID change, post number continuity, three-month redirect guarantee: https://help.naver.com/service/5593/contents/21122
4. Current editor and SE2 end date: https://help.naver.com/service/5593/contents/4332?lang=ko&osType=COMMONOS
5. SmartEditor ONE component catalog: https://help.naver.com/service/5593/category/3128?lang=ko
6. ONE unsupported features, including HTML authoring: https://help.naver.com/service/5593/contents/15545?lang=ko&osType=PC
7. Historical SmartEditor 3.0 API transition: https://developers.naver.com/notice/article/7712
8. Search API official guide: https://developers.naver.com/docs/serviceapi/search/blog/blog.md
9. Search API daily quota: https://help.naver.com/service/30015/contents/17309?lang=ko&osType=COMMONOS
10. Current API terms: https://developers.naver.com/products/terms/
11. 2025 API automation/access-scope amendment: https://developers.naver.com/notice/article/21979
12. Former Blog writing API ended 2020-05-06 (not an acquisition API): https://developers.naver.com/notice/article/7527
13. Public search exposure not guaranteed; updates can take 24h: https://help.naver.com/service/5593/contents/9564?lang=ko
14. External-send off removes a post from RSS: https://help.naver.com/service/5593/contents/15408
15. Official RSS HTTPS/HTTP version notice: https://help.naver.com/notice/noticeView.help?lang=ko&noticeNo=27243&page=1&serviceNo=5593
16. Main robots: https://blog.naver.com/robots.txt
17. Mobile robots: https://m.blog.naver.com/robots.txt
18. RSS robots: https://rss.blog.naver.com/robots.txt

SHA-pinned OSS evidence/implementation references:

1. First-party Search API guide at observed commit `1bfd8dd6fd90fdd33d7045cfc9d555d69eb58a67`: https://github.com/naver/naver-openapi-guide/blob/1bfd8dd6fd90fdd33d7045cfc9d555d69eb58a67/ko/service-apis/search/blog/blog.md
2. First-party historical SmartEditor2 modes/plugin architecture at `cf6070f1cd68a3ce35852e4b46e005b7b80978cd`: https://github.com/naver/smarteditor2/blob/cf6070f1cd68a3ce35852e4b46e005b7b80978cd/README.md
3. `pdfplumber` hyperlink annotations, positioned text, crop, and duplicate-character extraction at `4c64b92d5caccd71c645e98e0fabb0c4dba7ff45`: https://github.com/jsvine/pdfplumber/blob/4c64b92d5caccd71c645e98e0fabb0c4dba7ff45/README.md
4. `feedparser` ETag/Last-Modified and malformed-feed state at `19de31027e0879a896d649c7cc668b2b4cf3c783` (use only if RSS authorization is obtained): https://github.com/kurtmckee/feedparser/blob/19de31027e0879a896d649c7cc668b2b4cf3c783/feedparser/http.py and https://github.com/kurtmckee/feedparser/blob/19de31027e0879a896d649c7cc668b2b4cf3c783/feedparser/api.py

## EXPAND

- LEAD: Obtain purpose-specific written NAVER clarification on whether account-owner-authorized RSS polling for AI/RAG is permitted despite `rss.blog.naver.com/robots.txt` and the explicit Blog AI-training/RAG prohibition. Until then the lane remains disabled.
- LEAD: Run a small owner-generated PDF fixture through the proposed extractor to verify whether canonical URLs/log numbers survive as hyperlink annotations, how multi-post boundaries appear, and which ONE/legacy quote/media components retain layout. This cannot be proven from help documentation alone.
- LEAD: Confirm with the owner UI whether the 20-PDF statement is simultaneous storage or a creation-period limit and whether management views expose modified timestamps/exportable canonical IDs. Do not infer undocumented behavior.
- LEAD: Have governance/law owners specify retention, deletion SLA, coauthor/quote/media consent, and whether owner-authored comment replies can ever leave quarantine.
- DEAD END: Search API as complete account enumeration. It lacks an owner filter, full body, modification/deletion state, and access beyond the 1,000-result window; search exposure is not guaranteed.
- DEAD END: Former Blog writing API as a read/export path. It was a publishing API and ended in 2020.
- DEAD END: Live SmartEditor DOM/internal API parser. It is undocumented, violates the non-bypass constraint, is unstable across variants, and is unnecessary for owner PDF ingestion.

## CLAIMS

- CLAIM: Owner-created NAVER PDF backup is the only supported default acquisition channel identified here that avoids automated access to NAVER endpoints. - RISK: normal - SOURCES: help.naver.com backup/PDF workflow - COUNTER: PDF is lossy and cannot alone prove complete selection - PRIMARY: NAVER Help
- CLAIM: PDF backup is not a lossless corpus export: it excludes memo/scrap/disciplinary posts, omits several attachment types, thumbnails maps/videos, and has 100-post/500MB/3GB-day/20-PDF limits. - RISK: normal - SOURCES: help.naver.com - COUNTER: none in first-party sources found - PRIMARY: NAVER Help
- CLAIM: RSS automation for AI/RAG is unresolved and must be disabled by default because first-party RSS availability guidance conflicts with current robots disallow/prohibition text. - RISK: high - SOURCES: help.naver.com, blog.naver.com, m.blog.naver.com, rss.blog.naver.com - COUNTER: official RSS help demonstrates intended subscription, but does not expressly authorize AI corpus storage/training - PRIMARY: NAVER Help and three NAVER robots files
- CLAIM: Search API cannot prove account completeness and should not be used as corpus acquisition without express approved scope. - RISK: high - SOURCES: developers.naver.com, help.naver.com - COUNTER: it can return up to the first 1,000 matching search results and may serve as a transient public witness - PRIMARY: NAVER Developers guide/terms
- CLAIM: Blog ID is not a stable canonical document key; owner subject plus post number is the appropriate internal key. - RISK: normal - SOURCES: help.naver.com Blog ID change guide - COUNTER: post-number global uniqueness is not claimed, so owner subject remains in the key - PRIMARY: NAVER Help
- CLAIM: No documented official complete read/export API with modification/deletion state was found; reliable incremental sync is owner-inventory/change-ledger driven. - RISK: high - SOURCES: NAVER Search API guide, PDF help, ended writing API notice - COUNTER: undocumented internal endpoints are intentionally out of scope and cannot be treated as approved interfaces - PRIMARY: NAVER official sources
