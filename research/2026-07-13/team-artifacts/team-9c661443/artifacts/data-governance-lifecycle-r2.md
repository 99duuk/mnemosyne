# Reversible data lifecycle for an authorized Naver Blog persona corpus

Research date: 2026-07-13 (Asia/Seoul)  
Scope: governance architecture, not a legal opinion. Korean binding rules are separated from regulator/standards/research recommendations. Applicability still depends on the controller, the data, the exact authorization, and any sector-specific retention law.

## TL;DR

The safest production design is not “scrape, embed, and remember consent.” It is an item-versioned control plane that defaults every acquisition to quarantine, keeps personal-data authority separate from copyright/persona authority, records complete raw→normalized→chunk→embedding→profile→dataset→model lineage, and enforces a two-phase deletion: immediate logical denial followed by physical purge and independent verification. A minimal content-free tombstone prevents accidental re-ingestion; every restore must replay tombstones and rights revocations before data is exposed.

For a small, identifiable persona corpus, prefer retrieval/profile composition over weight training. If weights are trained, a source deletion must invalidate the exact dataset snapshot and trigger a documented retire/retrain/unlearn decision. Approximate machine unlearning is not deletion proof: peer-reviewed counter-evidence shows incomplete removal and leakage through cached computations.

## 1. Binding Korean requirements vs recommendations

### Binding or directly enforceable when PIPA applies

| Requirement | Production consequence | Primary source |
|---|---|---|
| A controller needs a lawful ground for collection/use and must stay within its purpose/scope. Sensitive and unique-identifying information has stricter separate grounds. | Do not encode authority as one Boolean. Version personal-data basis, sensitive-data basis, copyright/license, and persona/publication permission independently. | PIPA [Art. 15](https://law.go.kr/LSW/lsLinkCommonInfo.do?ancYnChk=&chrClsCd=010202&lsJoLnkSeq=1020398481), [Art. 23](https://www.law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1027416043), [Art. 24](https://www.law.go.kr/lsLinkCommonInfo.do?ancYnChk=&chrClsCd=010202&lsJoLnkSeq=1020398533) |
| Data that becomes unnecessary because the period expired, the purpose ended, or the pseudonymous-processing period ended must be destroyed without delay; destruction must prevent restoration/reproduction. A statutory hold must be separated from ordinary data. | Rights expiry must invalidate descendants. Legal-hold data is isolated and unavailable to retrieval/training. Deletion verification must test recoverability, not only database flags. | PIPA [Art. 21](https://www.law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=900078981) |
| A data subject may request correction/deletion and receive the outcome; deletion must prevent restoration/reproduction, subject to an express statutory-collection exception. | Run a case-based, auditable deletion workflow with exceptions and outcome notice. | PIPA [Art. 36](https://law.go.kr/LSW/lsSideInfoP.do?docCls=jo&joBrNo=00&joNo=0036&lsiSeq=270351&urlMode=lsScJoRltInfoR) |
| A data subject may request processing suspension and withdraw consent, with statutory exceptions. | Logical denial must be immediate and independent of slower physical deletion. | PIPA [Art. 37](https://www.law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=900079171) |
| Processor entrustment requires written controls, scope limits, safeguards, disclosure, and controller supervision; current rules extend relevant duties to processors and require subprocessing visibility/flow-down. | Maintain processor/subprocessor bindings and deletion acknowledgements; prohibit secondary training. | PIPA [Art. 26](https://www.law.go.kr/법령/개인정보보호법/제26조) |
| Technical, managerial, and physical safeguards include internal planning and access-log controls. | Protect the control plane, deletion evidence, and access logs against tampering/loss. | PIPA [Art. 29](https://www.law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=900079357) |
| Under the current PIPC Safety Measures Standard, access logs are generally retained for at least one year and for at least two years in specified higher-risk/scale cases; review method/cadence and follow-up must be defined, and logs protected. | Set the statutory access-log class separately from governance-event retention. Do not infer that all audit content must be stored for two years. | PIPC Notice 2026-9, effective 2026-07-01, [Art. 8](https://www.law.go.kr/LSW/admRulSideInfoP.do?admRulSeq=2100000281400&chrClsCd=010201&dashNo=&docCls=jo&joBrNo=00&joNo=0008&urlMode=admRulScJoRltInfoR) |

The statutory term “processing” is broad—collection, generation, linkage, storage, possession, editing, retrieval, output, correction, restoration, use, provision, disclosure, and destruction—so embeddings, profiles, evaluations, and export caches are not outside governance merely because they are derived. See the PIPC [Standard Personal Information Protection Guideline](https://www.law.go.kr/LSW/admRulInfoP.do?admRulSeq=2100000257592&chrClsCd=010201).

### Strong recommendations, not independently binding Korean law

* PIPC's [2025 Generative AI personal-information guide](https://pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS217&mCode=G010030020&nttId=11439) organizes lifecycle controls, lawful-basis/source checks, preprocessing, filtering, rights support, governance, and machine unlearning. Individual statements may explain binding PIPA duties, but the guide is not itself a blanket statutory mandate.
* PIPC's [AI Privacy Risk Management Model](https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS074&mCode=C020010000&nttId=10870) expressly presents a voluntary lifecycle risk model; not every listed safeguard is mandatory.
* [W3C PROV-O](https://www.w3.org/TR/prov-o/), [OpenLineage](https://github.com/OpenLineage/OpenLineage/blob/main/spec/OpenLineage.md), and [NIST AI RMF](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/) are useful implementation patterns, not Korean legal requirements.
* The exact TTLs, source-transition rules, HMAC tombstone format, RAG-first choice, and verification tests below are production recommendations.

## 2. Authority and provenance model

“Authorized” must resolve to four independently versioned questions:

1. May this personal data be collected and used for this purpose?
2. May sensitive/unique-identifying data be processed separately?
3. May the text/media be copied, transformed, embedded, or trained on?
4. May the resulting persona be exposed, to whom, through which channels, and for how long?

A source author's consent cannot automatically authorize a quoted third party's personal data. Public visibility is an acquisition fact, not a perpetual license or consent.

```sql
create table rights_basis_version (
  rights_basis_version_id uuid primary key,
  subject_id uuid not null,
  basis_domain text not null check (basis_domain in
    ('personal_data','sensitive_data','unique_identifier','copyright','persona_publication')),
  basis_type text not null check (basis_type in
    ('consent','contract','statute','legitimate_interest','license','none')),
  purpose_codes text[] not null,
  operation_scope text[] not null, -- collect, normalize, embed, retrieve, profile, train, publish, export
  audience_scope text[] not null,
  source_selector jsonb not null, -- blog/post/range/version constraints
  effective_from timestamptz not null,
  effective_until timestamptz,
  withdrawn_at timestamptz,
  status text not null check (status in
    ('draft','active','suspended','withdrawn','expired','disputed')),
  evidence_uri text not null,
  evidence_sha256 char(64) not null,
  supersedes_id uuid references rights_basis_version,
  verified_by uuid not null,
  verified_at timestamptz not null,
  policy_version text not null
);
```

The control plane stores source versions and artifact edges; content lives in separately encrypted, deletable stores. “Immutable” below means append-only/version-preserving while authorized and retained; it never overrides erasure, retention expiry, key destruction, or rights revocation.

```sql
create table source_item_version (
  source_item_version_id uuid primary key,
  corpus_id uuid not null,
  source_item_id uuid not null,
  platform text not null check (platform = 'naver_blog'),
  owner_subject_id uuid not null,
  platform_post_no bigint not null,
  canonical_url text not null,
  url_aliases text[] not null default '{}',
  visibility text not null check (visibility in
    ('public','neighbor','mutual_neighbor','private','missing','deleted','unknown')),
  observed_at timestamptz not null,
  source_updated_at timestamptz,
  content_sha256 char(64) not null,
  third_party_class text not null check (third_party_class in
    ('none','quoted','comment','correspondence','depicted','mixed','unknown')),
  sensitivity text not null check (sensitivity in
    ('none','personal','sensitive','unique_identifier','minor','mixed','unknown')),
  governance_state text not null,
  retention_policy_id uuid not null,
  unique (platform, owner_subject_id, platform_post_no, content_sha256)
);

create table source_right (
  source_item_version_id uuid references source_item_version,
  rights_basis_version_id uuid references rights_basis_version,
  primary key (source_item_version_id, rights_basis_version_id)
);

create table artifact (
  artifact_id uuid primary key,
  artifact_type text not null check (artifact_type in
    ('raw','normalized','chunk','embedding','profile','dataset_snapshot',
     'model','evaluation','cache','export')),
  encrypted_location text,
  content_sha256 char(64),
  schema_version text not null,
  transform_or_model_version text,
  produced_by_run_id uuid not null,
  governance_state text not null,
  created_at timestamptz not null,
  retention_until timestamptz,
  invalidated_at timestamptz,
  deletion_case_id uuid
);

create table artifact_edge (
  parent_artifact_id uuid references artifact,
  child_artifact_id uuid references artifact,
  relation text not null check (relation in
    ('derived_from','quoted_from','revision_of','embedded_from','profiled_from',
     'trained_on','evaluated_with','exported_from')),
  primary key (parent_artifact_id, child_artifact_id, relation)
);
```

`artifact_edge` permits a recursive invalidation query. The semantics map cleanly to W3C PROV's `Entity`, `Activity`, `Agent`, `wasDerivedFrom`, `wasRevisionOf`, and invalidation. Pipeline executions additionally emit OpenLineage START and COMPLETE/FAIL/ABORT events, with input/output dataset facets and a custom governance facet containing rights-basis IDs and policy version.

URL is not an identity key. Naver states that changing a blog ID changes URLs and that redirects may eventually stop while content persists ([Naver URL-ID change help](https://help.naver.com/service/5593/bookmark/21122)). Use owner/platform identity plus `post_no`, retain URL aliases, and version by content hash.

## 3. Quarantine and normalization

Every item enters an encrypted quarantine bucket and is ineligible for search, profile construction, or training until policy evaluation completes.

```text
ingest -> malware/media scan -> source/rights resolution -> span classification
       -> [third-party | sensitive | unique ID | minor | unknown] -> QUARANTINED
       -> reviewer: ALLOW | REDACT | SUBSTITUTE | EXCLUDE | REQUEST_AUTHORITY
       -> normalized text + offset map + redaction manifest -> AUTHORIZED
```

Required span classes include quoted people, comments, correspondence, faces/voices, contact details, minors, political/religious/union views, health/sexual data, biometrics, and unique identifiers. Normalized artifacts contain only allowed spans. A redaction manifest records source offsets, classifier/reviewer version, decision, and reason code—but never copies the sensitive span into immutable logs.

Public Naver posts can be public, neighbor-only, mutual-neighbor-only, or private ([visibility help](https://help.naver.com/service/5593/contents/15541?lang=ko&osType=PC)); a whole blog can effectively become private by changing all categories ([category help](https://help.naver.com/service/5593/contents/15289?lang=ko&osType=PC)). Therefore source visibility must be polled at item level. Visibility is not identical to legal authority, but PUBLIC→PRIVATE is a high-confidence product stop signal: immediately remove descendants from serving and hold them pending authority confirmation.

## 4. State machines

Keep source state, authority state, artifact state, and deletion-case state separate. One overloaded status cannot describe an item that is source-deleted, legally retained, and operationally blocked.

```text
Artifact governance
DISCOVERED -> QUARANTINED -> REVIEWED -> AUTHORIZED -> ACTIVE
                    |             |          |
                    +----------> EXCLUDED    +-> RESTRICTED
ACTIVE|RESTRICTED -> SUSPENDED -> DELETE_PENDING -> PURGING
PURGING -> VERIFYING -> DELETED -> TOMBSTONED
                     \-> PARTIAL_FAILURE -> PURGING
DELETE_PENDING -> LEGAL_HOLD_SEPARATED -> DELETE_PENDING (when hold expires)
```

Invariants:

* Only `ACTIVE` artifacts may serve or build descendants.
* `SUSPENDED` is synchronous and blocks reads; physical purge may be asynchronous.
* A parent invalidation recursively makes every descendant non-active before any purge begins.
* `LEGAL_HOLD_SEPARATED` is physically/logically isolated and unavailable to retrieval, profile, training, evaluation, or export.
* `TOMBSTONED` never returns to active. A newly authorized acquisition receives a new item/version and must not silently reuse old authority.

```text
Source observations
PUBLIC -> PRIVATE | MISSING | DELETED
PRIVATE -> PUBLIC (does not auto-reactivate; authority review required)
MISSING -> PUBLIC (same) | DELETED (confirmed policy)

Deletion case
OPEN -> IDENTITY_VERIFIED -> SERVING_BLOCKED -> SCOPE_RESOLVED
     -> DISPATCHED -> VERIFYING -> COMPLETE
                              \-> PARTIAL_FAILURE -> RETRYING -> VERIFYING
                              \-> MANUAL_ESCALATION
```

Naver reset makes a blog unavailable/private during a 24-hour or seven-day hold and then deletes reset content irrecoverably, while comments the author left on other blogs remain ([Naver reset help](https://help.naver.com/service/5593/contents/889?lang=ko&osType=PC)). Treat temporary disappearance as `MISSING`, not immediate deletion; confirm according to a documented cadence. Independently authored third-party-location comments require distinct source items.

## 5. Retention policy

The following periods are recommended defaults, not statutory periods, except the access-log row:

| Class | Default | Trigger/condition |
|---|---:|---|
| Quarantine raw | 30 days maximum after review; shorter if rejected | Remove immediately after exclusion unless incident evidence is necessary and separately authorized. |
| Active raw/normalized/chunk/embedding/profile | Earliest of authority expiry, purpose completion, or item retention TTL | All descendants inherit the shortest parent/right TTL. |
| Exports | 7 days | Revoke signed URL immediately on suspension; encrypt per recipient. |
| Output/retrieval caches | Hours to 7 days | Index by source/artifact IDs so cascade deletion is deterministic. |
| Access logs | ≥1 year, or ≥2 years in PIPC Notice 2026-9 categories | Binding classification must be assessed for the deployment. |
| Governance/deletion evidence | Proposed 5 years, periodically reviewed | Store content-free hashes/events only; document purpose and necessity. This is not a universal Korean statutory period. |
| Backups | Shortest operationally feasible cycle | Deleted content must not be service-restorable; replay tombstones before exposure, expire encrypted backup generations, and use key destruction where designed. |

Do not promise instantaneous byte erasure from every immutable backup if the architecture cannot prove it. Instead minimize backup lifetime, isolate backups, prevent operational use, delete keys/generations on schedule, and verify through restore drills. Because PIPA Art. 21 requires non-restorability, obtain deployment-specific Korean legal review for any residual backup design.

## 6. Deletion, processor propagation, and re-ingestion prevention

Deletion is an idempotent saga keyed by `deletion_case_id`:

1. Verify requester identity and authority without collecting excessive new data.
2. Create case and immutable, content-free scope snapshot.
3. Immediately block retrieval, profile use, exports, caches, and build jobs.
4. Recursively resolve all raw→model descendants and rights versions.
5. Split any express statutory retention into `LEGAL_HOLD_SEPARATED` with reason/expiry.
6. Purge primary raw/normalized stores, chunks, vector IDs and metadata, profiles, caches, evaluation fixtures, exports, and dataset materializations.
7. Invalidate affected dataset snapshots and model releases.
8. Execute model decision: no action only after evidence of no relevant model retention/inference risk; otherwise validated exact unlearning, retirement, or retraining without the item.
9. Send processor/subprocessor requests through a transactional outbox; collect machine-verifiable acknowledgements.
10. Register a minimal tombstone, schedule backup expiry/key destruction, and replay it on every restore.
11. Run independent verification; complete only when all required checks pass or disclose a lawful, isolated exception.
12. Notify the requester of outcome, exceptions, residual schedule, and appeal/contact path.

```sql
create table processor_binding (
  processor_binding_id uuid primary key,
  processor_name text not null,
  subprocessor_path text[] not null,
  artifact_types text[] not null,
  region text not null,
  contract_version text not null,
  delete_endpoint text not null,
  deletion_sla interval not null,
  backup_semantics text not null,
  secondary_training_allowed boolean not null default false,
  acknowledgement_evidence_type text not null
);

create table processor_deletion (
  deletion_case_id uuid not null,
  processor_binding_id uuid references processor_binding,
  idempotency_key text not null,
  processor_request_id text,
  sent_at timestamptz,
  due_at timestamptz not null,
  acknowledged_at timestamptz,
  status text not null check (status in
    ('pending','sent','acknowledged','verified','failed','expired','escalated')),
  evidence_sha256 char(64),
  retries integer not null default 0,
  last_error_code text,
  primary key (deletion_case_id, processor_binding_id)
);
```

The processor contract should explicitly cover deletion/return at end of service, subprocessor flow-down, backup handling and restore replay, no secondary model training, deletion SLA/evidence, export, auditability, and incident notification. An API `200` is not verification; require an artefact-count result, signed receipt or equivalent evidence, and periodically sample/audit it.

A tombstone contains no post text or raw URL:

```json
{
  "tombstone_id": "uuid",
  "source_locator_hmac": "HMAC(rotating-separate-key, owner-id || post-no)",
  "last_content_sha256": "sha256",
  "deletion_case_id": "uuid",
  "reason_code": "CONSENT_WITHDRAWN",
  "effective_at": "RFC3339",
  "policy_version": "2026-07",
  "expires_at": null
}
```

The HMAC key is access-separated and rotated under a documented policy. A tombstone can itself remain personal data if linkability persists; minimize it, restrict access, assess it under PIPA, and do not label it “anonymous” by assumption.

## 7. Verification matrix and failure recovery

| Store/control | Positive deletion evidence | Failure action |
|---|---|---|
| Relational/content DB | zero rows by artifact/source IDs; no content in history tables | block tenant/corpus serving; retry transactionally |
| Object/version store | object and versions absent or cryptographically inaccessible; lifecycle rule evidence | quarantine bucket/prefix; destroy scoped key or wait isolated expiry per declared policy |
| Vector index | exact vector IDs absent plus metadata-filter check | block/rebuild namespace or collection |
| Retrieval behavior | semantic canary/paraphrase queries return no deleted passages | keep corpus suspended; rebuild index/cache |
| Profile | fields and supporting evidence edges absent | regenerate profile from authorized sources only |
| Dataset snapshot | manifest invalidated; source/right version absent from next snapshot | stop promotion and downstream builds |
| Model | extraction/membership/canary tests; retrain/unlearn provenance and comparison report | retire deployment; retrain from clean snapshot |
| Processor | acknowledgment plus artifact count/evidence hash; sampled audit | mark `PARTIAL_FAILURE`, retry, escalate contract/legal |
| Backup | timed restore drill followed by tombstone replay yields no service-visible item | block restore release; fix restore gate |
| Export | link revoked, blob gone, retrieval log retained minimally | revoke recipient key/link; incident path if uncontrolled copy |

Implementation reliability controls:

* Transactional outbox for purge/processor commands, at-least-once delivery, idempotency keys, exponential retry, dead-letter queue, and deadline escalation.
* Append-only governance events with a hash chain or WORM storage; mutable operational details live outside the immutable event.
* Crash recovery resumes from the case state and records every transition; no “best effort” shell script.
* A restore gate first replays tombstones, withdrawn/expired rights, and invalidated datasets; only then rebuilds serving indexes.
* False-positive verification or missing acknowledgement leaves the corpus suspended. Failure never degrades to active.

```sql
create table governance_event (
  event_id uuid primary key,
  prior_event_sha256 char(64),
  event_sha256 char(64) not null,
  event_type text not null,
  occurred_at timestamptz not null,
  actor_type text not null,
  actor_id uuid,
  corpus_id uuid,
  source_item_id uuid,
  artifact_id uuid,
  deletion_case_id uuid,
  rights_basis_version_id uuid,
  policy_version text not null,
  request_id text not null,
  outcome text not null,
  reason_code text not null,
  evidence_sha256 char(64)
);
```

Never write raw posts, sensitive spans, prompts, model outputs, tokens, or requester identity evidence into immutable events. Hashes are evidence pointers, not proof of successful deletion by themselves.

## 8. Export design

An owner export is a short-lived encrypted package with:

* manifest JSONL: item/version IDs, source locator, timestamps, visibility observations, rights-basis version IDs, and hashes;
* allowed source content and media, preserving redaction decisions;
* artifact/lineage graph in PROV JSON-LD or equivalent;
* profile fields and each supporting item edge;
* deletion/retention state and processor classes, without other individuals' protected details;
* signed manifest or Merkle root, one-time link, expiry, and minimal download log.

Do not export internal reviewer notes, other subjects' identity evidence, secrets, processor credentials, or an audit log containing unrelated people. Third-party content should be redacted, segregated, or withheld under a documented rule.

## 9. Models and counter-evidence

The lineage must be complete even when model weights cannot be traced to exact sentences. A persona corpus is small and identifiable, making individual-item influence and extractability more plausible than in a huge generic corpus. Prefer runtime retrieval/profile assembly because an item can be denied and purged without changing shared weights.

If training is unavoidable, record the immutable dataset manifest, exact rights-basis versions, code/container/model seed/checkpoint, and evaluation set. Partition training (for example, SISA-style sharding) to reduce retraining cost, but do not promise exact removal without a validated guarantee.

Counter-search results:

* The peer-reviewed survey [Machine Unlearning: A Comprehensive Survey](https://doi.org/10.1145/3749987) distinguishes exact guarantees from approximate approaches and describes sharding/slicing strategies.
* ICML 2023 [Forget Unlearning: Towards True Data-Deletion](https://proceedings.mlr.press/v202/chourasia23a.html) shows that cached partial computations and adaptive releases can undermine deletion guarantees; even retraining claims need a precise threat model.
* ICLR 2025 [Machine Unlearning Fails to Remove Data Poisoning Attacks](https://proceedings.iclr.cc/paper_files/paper/2025/hash/7e810b2c75d69be186cadd2fe3febeab-Abstract-Conference.html) finds prominent approximate methods can fail and argues they are not ready as a universal deletion mechanism.
* As a non-Korean comparative authority, EDPB [Opinion 28/2024](https://www.edpb.europa.eu/documents/opinion-of-the-board-art-64/opinion-282024-on-certain-data-protection-aspects-related-to_en) treats model anonymity case by case and asks whether identification/extraction is very unlikely. It does not bind Korea, but rebuts the claim that weights are automatically anonymous.
* As a non-Korean comparative counterpoint, the UK ICO's [AI rights guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/artificial-intelligence/guidance-on-ai-and-data-protection/how-do-we-ensure-individual-rights-in-our-ai-systems/?search=synthetic) says erasing training data is generally feasible and model erasure depends on whether personal data remains in/inferable from the model. It rebuts the opposite overclaim that every deletion always requires deleting every model.

Decision rule: if the deployed model can reproduce, permit inference about, or remains materially influenced by the deleted persona item—or the controller cannot demonstrate otherwise—retire it from serving and retrain from an authorized snapshot. Approximate unlearning is acceptable only under a predefined, independently tested guarantee and fallback retirement path.

## 10. Distinct research queries completed

1. `site:law.go.kr 개인정보 보호법 제21조 파기 복구 재생 불가능`
2. `site:law.go.kr 개인정보 보호법 제36조 정정 삭제 처리정지`
3. `site:law.go.kr 개인정보 보호법 제37조 동의 철회 처리정지`
4. `site:law.go.kr 개인정보의 안전성 확보조치 기준 접속기록 1년 2년 2026`
5. `site:law.go.kr 개인정보 보호법 제26조 업무위탁 재위탁 파기`
6. `site:law.go.kr 개인정보 보호법 제29조 안전조치 접속기록`
7. `site:pipc.go.kr 생성형 인공지능 개인정보 처리 안내서 2025`
8. `site:pipc.go.kr 인공지능 개인정보보호 자율점검 위험관리 모델 2024`
9. `site:help.naver.com 블로그 공개 비공개 이웃 서로이웃`
10. `site:help.naver.com 블로그 초기화 삭제 복구 불가`
11. `site:help.naver.com 블로그 아이디 변경 URL 리다이렉트`
12. `W3C PROV-O Recommendation invalidation derivation provenance`
13. `OpenLineage specification run event dataset facets failure abort`
14. `NIST AI RMF data provenance third party data deletion`
15. `machine unlearning exact deletion retraining failure peer reviewed`
16. `EDPB Opinion 28/2024 AI models anonymity extraction personal data`
17. `ICO AI right to erasure training data model personal data`
18. `site:law.go.kr 개인정보 보호법 제15조 2026 개인정보 수집 이용 정당한 이익`
19. `site:law.go.kr 개인정보 보호법 제23조 민감정보 처리 제한 2026`
20. `site:law.go.kr 개인정보 보호법 제24조 고유식별정보 처리 제한 2026`

## Risks and rejected shortcuts

* **“Public post means reusable forever.”** Wrong. Public visibility does not by itself resolve personal-data purpose, copyright, third-party rights, sensitive information, or persona publication.
* **“Private/404 automatically proves a statutory deletion request.”** Wrong. It is an operational stop/quarantine signal; legal effect depends on authority and facts. Confirm deletion without continuing to serve.
* **“Delete the source row and keep embeddings.”** Wrong. Embeddings/profile/cache/model inputs are derived artifacts requiring lineage and a risk-based deletion decision.
* **“Weights and embeddings are anonymous.”** Unsupported. Treat them as potentially personal/derived until a documented assessment proves otherwise.
* **“Approximate unlearning proves deletion.”** Rejected by peer-reviewed counter-evidence. Use retirement/retraining fallback.
* **“Immutable audit means retain raw evidence forever.”** Wrong and creates a new retention problem. Immutable events should be content-free.
* **“A successful processor API response completes deletion.”** Wrong. Require acknowledgment, evidence, and periodic verification.
* **“Backups make compliance impossible.”** False dichotomy. Short cycles, isolation, crypto-erasure where appropriate, tombstone replay, and restore gates can make deletion operationally enforceable; exact legal sufficiency still needs fact-specific review.

## EXPAND

LEAD: Validate the current PIPC Notice 2026-9 applicability class against projected subject count and whether the corpus stores sensitive/unique-identifying information.  
WHY: This changes the binding access-log minimum from one year to two years and affects internal review controls.  
ANGLE: Produce a deployment-specific compliance matrix, not a universal TTL.

LEAD: Prototype a clean-room deletion drill that removes one canary post through DB, object store, vector index, profile, cache, processor, backup restore, and model extraction tests.  
WHY: Schemas do not prove non-restorability; Art. 21 and Art. 36 make recovery resistance central.  
ANGLE: Measure time-to-serving-block, time-to-physical-purge, false-negative rate, and processor acknowledgement latency.

LEAD: Commission Korean counsel review of the exact authorization instrument and backup/model residual policy.  
WHY: Personal-data grounds, copyright license, persona publicity, sensitive-data consent, and statutory holds are independent and fact-dependent.  
ANGLE: Convert the reviewed scope into machine-enforced `rights_basis_version` operations/audiences/expiry.

## CLAIMS

CLAIM: PIPA requires destruction without delay when personal data becomes unnecessary and requires destruction that prevents restoration/reproduction; legal-retention data must be separated.  
STATUS: Binding Korean requirement when PIPA applies.  
RISK: “Without delay” and acceptable backup residual handling require fact-specific interpretation; do not promise unproved instant byte erasure.  
SOURCES: PIPA Art. 21; Art. 36.  
COUNTER: Operational deletion flags or hashing alone do not establish non-restorability.  
PRIMARY: https://www.law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=900078981

CLAIM: Processor deletion must be contractually controlled, propagated, supervised, and evidenced; a controller cannot outsource accountability.  
STATUS: Binding Korean core requirement plus recommended acknowledgement protocol.  
RISK: Contract scope and current re-entrustment text must be checked for each processor chain.  
SOURCES: PIPA Art. 26.  
COUNTER: HTTP success is not statutory proof of complete deletion.  
PRIMARY: https://www.law.go.kr/법령/개인정보보호법/제26조

CLAIM: Current PIPC Safety Measures Standard requires at least one year of access-log retention, with at least two years for specified scale/risk classes.  
STATUS: Binding administrative standard where applicable, current as researched 2026-07-13.  
RISK: Do not apply the two-year class without checking subject count/data category, and do not confuse access logs with all governance evidence.  
SOURCES: PIPC Notice 2026-9 Art. 8.  
COUNTER: A longer content-bearing immutable audit log can violate minimization/retention principles.  
PRIMARY: https://www.law.go.kr/LSW/admRulSideInfoP.do?admRulSeq=2100000281400&chrClsCd=010201&dashNo=&docCls=jo&joBrNo=00&joNo=0008&urlMode=admRulScJoRltInfoR

CLAIM: Naver visibility/deletion/URL transitions require item-level observation and stable non-URL identity, but they do not alone determine legal erasure.  
STATUS: Verified platform behavior; product-governance recommendation.  
RISK: Treating a transient reset hold as permanent deletion or a returned URL as automatic reauthorization can corrupt lifecycle state.  
SOURCES: Naver visibility, reset, and ID-change help.  
COUNTER: Source state and legal authority are separate state machines.  
PRIMARY: https://help.naver.com/service/5593/contents/15541?lang=ko&osType=PC

CLAIM: Approximate machine unlearning must not be used as the sole deletion proof.  
STATUS: Strong peer-reviewed counter-evidence and engineering recommendation, not a Korean statutory formula.  
RISK: A small identifiable persona corpus increases influence/extraction concern; failed removal can create privacy and authorization exposure.  
SOURCES: ICML 2023 Chourasia et al.; ICLR 2025 Pawelczyk et al.; ACM TIST survey.  
COUNTER: Not every source deletion necessarily requires destroying every model if no personal data remains/inference is possible, but that conclusion requires evidence.  
PRIMARY: https://proceedings.mlr.press/v202/chourasia23a.html
