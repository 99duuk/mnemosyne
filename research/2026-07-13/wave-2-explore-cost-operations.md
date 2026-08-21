# Wave 2 - Cost and Operations Model

Observer: `root`  
Observed at: 2026-07-13  
Scope: vendor-neutral sizing formulas. Exact model/API prices are intentionally not frozen because they change; substitute current contracted prices during implementation.

## Cost model

Let:

- `D`: eligible documents, `S`: eligible source characters, `C`: chunks, `E`: embedding dimensions and bytes/element.
- `Q`: persona queries/month, `Tin/Tout`: average generation input/output tokens.
- `R`: reranker calls/query, `V`: verifier calls/query, `A`: fraction answered rather than abstained.
- `Pb_embed`, `P_in`, `P_out`, `P_rerank`, `P_verify`: current contracted unit prices.

```text
initial_embedding_cost = total_embedding_tokens * Pb_embed
vector_payload_bytes   = C * E * bytes_per_element
vector_storage_budget  = vector_payload_bytes * index_overhead_factor
monthly_generation     = Q * (Tin * P_in + Tout * P_out)
monthly_rerank         = Q * R * P_rerank
monthly_verification   = Q * V * P_verify
monthly_total          = storage + generation + rerank + verification + logging + backup + operations
```

Measure index overhead and rebuild time on the selected stack; do not assume the vector payload is total storage. Keep generation, retrieval and verification costs separate so stricter gates are visible.

## Recommended deployment stages

| Stage | Scale/feature | Required evidence before promotion |
|---|---|---|
| 0 authority | no serving | signed rights matrix, owner inventory, Naver endpoint decision |
| 1 offline analyst | local authorized corpus; lexical baseline | corpus set/freshness report, source spans, quote tests |
| 2 private RAG | hybrid retrieval, third-person only | time-held-out retrieval and citation gates |
| 3 disclosed simulation | optional style renderer, no tools | semantic-drift, identity comprehension and consent gates |
| 4 optional adapter | isolated target adapter only | statistically significant style benefit with no factual/privacy regression; retirement drill |
| 5 public service | monitored, rate-limited, complaint/takedown path | counsel signoff, processor/delete drill, public confusion test |

## SLOs and recovery targets

Do not assign universal latency targets before model/hardware measurement. Define and record:

- p50/p95/p99 for route, lexical, dense, rerank, generation, verification and end-to-end.
- retrieval/answer cache hit rate segmented by consent/index/time generation.
- time-to-serving-block for revocation; time-to-primary-purge; time-to-processor-ack; time-to-backup-expiry.
- index shadow-build duration and rollback time.
- cost per answered query and per abstained query.
- incident counts for unsupported claim, false quote, deleted-source hit, prompt injection and identity confusion.

## Capacity and failure choices

- For a single blog, begin with PostgreSQL plus lexical search and pgvector or an equivalent single control plane; a distributed vector platform is justified only by measured scale/latency, not fashion.
- Keep immutable corpus generations and build shadow indexes. Promote only after row/hash/filter/golden-query verification; rollback by alias switch.
- Batch embeddings per new immutable revision. A deleted/changed item invalidates dependent chunks/profile/cache without re-embedding the whole corpus unless the chosen index cannot guarantee deletion.
- Exact-quote and simple source lookup routes can skip dense retrieval and generation.
- Rerank and independent verification are quality tiers selected by query risk, not globally mandatory calls.
- Capacity planning includes owner-driven ingestion and deletion/rebuild labor; API inference is not the dominant risk cost for a small corpus.

## MVP effort estimate

Effort is scenario-dependent, so use work packages rather than false calendar precision:

1. Authority/inventory and item rights review.
2. PDF/original-package ingestion, mapping and manual quarantine UI.
3. Evidence schema, lexical baseline and citation renderer.
4. Korean hybrid retrieval, temporal claim/profile layer and evaluator.
5. Deletion/restore/processor saga and monitoring.
6. Optional disclosed style renderer/adaptor and public release controls.

The rights and manual-review workload scales with items, quotes and media; the retrieval workload scales with eligible chunks; adapter work is optional and starts only after the analyst baseline passes.

## CLAIMS

- C46: For one blog, operational correctness and rights review dominate architecture complexity; start with the smallest measurable retrieval stack.
- C47: Cost must be reported per stage and per answered/abstained query, including verification and deletion/rebuild operations.
- C48: Public deployment and optional tuning are promotion stages, not MVP defaults.
