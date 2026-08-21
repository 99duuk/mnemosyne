# Wave 1 - Collection Engineering

Observer: `/root/collection_engineering_r2`  
Observed at: 2026-07-13  
Full artifact: `.omo/teams/team-9c661443/artifacts/collection-engineering-r2.md`

## Decision

The deployable default is an owner-mediated offline package: signed row-complete inventory, owner-created Naver PDF batches, optional separately owned original media, checksums and a delivery signature. No service login, undocumented endpoint, live-page parser, CAPTCHA workflow, proxy rotation or media URL harvesting is included.

RSS and Search API adapters ship disabled. RSS needs written purpose-specific resolution of the official-help versus robots/AI-RAG conflict. Search API is query/snippet discovery with a 1,000-result window and no account export semantics; it can never be the corpus or completeness oracle.

## Required engineering invariants

- Canonical document identity is owner subject plus provider post number; blog ID is a time-bounded alias because Naver documents ID changes.
- Raw owner artifacts are immutable and content-hashed. Parser upgrades create new derived revisions rather than rewriting source lineage.
- Quotes, comments, OCR, unknown-origin blocks and media are quarantined by default. PDF flattening is not evidence of authorship.
- Completeness is a vector: inventory coverage, freshness, asset coverage, eligible-text coverage and unresolved mappings. Equal counts do not prove set equality.
- A `COMPLETE` claim requires signed row identity, set equality, zero unresolved mappings, freshness evidence and verified artifacts. Unknown edit times yield `UNKNOWN`, not 100%.
- Deletion/private transitions come only from signed owner evidence; disappearance from search, RSS or a public URL never creates a tombstone.
- Incremental synchronization is owner-driven through a signed inventory/change ledger and delta PDF; periodic full re-export checks edited older posts.
- Downstream publication uses only consent-valid, active, owner-original, rights-eligible blocks and requires tombstone acknowledgments.

## Proposed lineage core

The full artifact specifies PostgreSQL entities for owner/consent, aliases, channel approval, inventory snapshots/items, documents/revisions/blocks, immutable artifacts, media, rights decisions, sync checkpoints, tombstones and failure queues. The minimum source record carried to every chunk is:

`owner_subject_id, document_id, revision_id, block_id, source_artifact_hash, publication/capture time, origin, rights_decision, consent_version, lifecycle, parser_version`.

## Verification evidence

- 13 key first-party URLs returned HTTP 200 during the worker run.
- Live robots hashes were recorded for main, mobile and RSS hosts.
- Four OSS implementation references were pinned by commit: Naver OpenAPI guide, SmartEditor2, pdfplumber and feedparser.
- The full artifact includes 12 deployment acceptance tests covering signatures, idempotency, alias change, duplicates, batch size, quarantine, tombstones, unknown freshness, fail-closed network adapters, API window/cap and deterministic restore.

## EXPAND

- LEAD: Run one owner-generated PDF fixture to test surviving hyperlinks, post boundaries and flattened components - WHY: help documentation cannot establish exact PDF internals - ANGLE: authorized local fixture.
- LEAD: Clarify whether the 20-PDF limit is simultaneous storage or creation-period behavior and whether owner UI exposes modified times - WHY: completeness/freshness status changes - ANGLE: owner UI or Naver support.
- LEAD: Set governance retention/deletion SLA and coauthor/media/comment policy - WHY: acquisition lineage needs downstream decisions - ANGLE: governance lane.
- DEAD END: Search API as complete account enumeration.
- DEAD END: former writing API as read/export.
- DEAD END: live SmartEditor DOM/internal API parser.

## CLAIMS

- C26: Owner-mediated offline export is the default non-bypass acquisition path, but PDF remains lossy and needs a signed inventory.
- C27: Corpus completeness is a set-and-freshness proof, not a count or search-total assertion.
- C28: Reliable incremental sync is owner-change-ledger driven in the absence of a documented complete read/export API.
- C29: Quotes, comments, media/OCR and unknown-origin material must remain separate and quarantined until item-level clearance.
- C30: Network adapters must fail closed and stay disabled unless channel-specific platform approval is active.
