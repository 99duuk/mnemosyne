# Wave 2 - Evidence-Grounded Korean Persona RAG

Observer: `/root/collection_engineering_r2` on bounded RAG follow-up  
Observed at: 2026-07-13  
Full artifact: `.omo/teams/team-9c661443/artifacts/rag-architecture-r2.md`

## Architecture decision

Build two explicitly different products on one evidence layer:

1. Default source-attributed analyst: third-person, dated, claim-level citations, silent/conflict abstention.
2. Optional privately tested first-person role-play: a separately authorized identity act, not a semantics-neutral style transformation. Public output remains dated third person; automated drift tests cannot prove equivalence or current-endorsement safety.

RAG provides mutable evidence, not persona fidelity. RAGTruth, outdated-information and persona-consistency research show retrieved context can still yield unsupported, contradicted or temporally wrong output.

## Retrieval and generation invariants

- Preserve original NFC spans/offsets for quotes and separate NFKC search fields. Do not merge comments, quotes, OCR or platform chrome into author prose.
- Index linked sentence/claim children, paragraph citation parents and document routing metadata.
- Filter owner, consent, lifecycle, rights, origin, time and serving generation before ranking.
- Benchmark Korean lexical Nori/Kiwi-aware BM25 and KURE/BGE dense channels, fuse by RRF and optionally rerank. Dense-only superiority is not assumed.
- Claims are append-only temporal versions connected by supports, contradiction-candidate, superseded-by and qualifies relations.
- Latest-observed, historical and trajectory routes have separate time filters. Missing `valid_to` does not prove a current belief; without recent explicit reaffirmation return `unknown_current`. Same-time unresolved contradiction returns both sides and abstains.
- Retrieval packs contain immutable evidence IDs and spans. Generation first creates an atomic supported plan, then prose, then re-verifies atomic claims.
- Direct quotes must exactly match one source span. Exactness does not itself grant copyright permission.
- Profile memory is a derived view with support and counterevidence; chat/session output never updates the target profile.
- Corpus content is untrusted data and the persona generator has no tools or secrets.

## Empirical evidence

A minimal local Korean fixture with opposite 2021-2023 and 2024-current work preferences showed:

- lexical similarity tied without time constraints;
- pre-ranking `as_of` filtering selected only the historically eligible claim;
- current filtering selected only the newer claim;
- an exact substring quote passed and an altered quote failed.

This confirms only deterministic temporal eligibility and exact quote matching, not dense quality, NLI or persona fidelity.

## Sources

- RAGTruth: https://aclanthology.org/2024.acl-long.585/
- Outdated information in RAG: https://aclanthology.org/2025.acl-long.301/
- ALCE: https://arxiv.org/abs/2305.14627
- FActScore: https://arxiv.org/abs/2305.14251
- RAGChecker: https://arxiv.org/abs/2408.08067
- Self-RAG: https://arxiv.org/abs/2310.11511
- Nori official reference: https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-tokenizer
- BGE-M3: https://arxiv.org/abs/2402.03216
- OWASP prompt injection: https://genai.owasp.org/llmrisk/llm01-prompt-injection/

## EXPAND

- LEAD: Build authorized Korean golden queries for changed stances, dialect/spacing, quotes and unknowns - WHY: public benchmarks do not measure this author - ANGLE: human annotation and channel ablation.
- LEAD: Benchmark KURE/BGE dense/sparse and reranker on target hardware - WHY: published scores do not establish in-domain filtered recall or latency - ANGLE: recall/nDCG/p95/memory/rebuild.
- LEAD: Calibrate Korean claim/NLI and contradiction labels - WHY: hedging, sarcasm, quotation and temporal change cause false contradiction - ANGLE: reviewed pairs.
- LEAD: Test style semantic drift - WHY: first-person transformation can strengthen or invent claims - ANGLE: analyst/simulation paired atomic diff.
- DEAD END: high vector similarity establishes evidence support.
- DEAD END: retrieved profiles should always be injected.

## CLAIMS

- C41: RAG improves updateable evidence access but does not guarantee grounded or persona-faithful output.
- C42: Temporal eligibility must filter candidates before ranking, but the result establishes only a dated/latest-observed assertion unless current belief was explicitly reaffirmed under a declared freshness rule.
- C43: Korean retrieval needs target-corpus lexical/dense/hybrid/reranker ablation rather than a universal model choice.
- C44: Persona answers require atomic support and citation completeness/correctness verification after generation.
- C45: Refuted as originally worded. First-person rendering changes speaker and potential current-endorsement semantics; public mode remains dated third person, and any authorized private role-play is separately governed.
