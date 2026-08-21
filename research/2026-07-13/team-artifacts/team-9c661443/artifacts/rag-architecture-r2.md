# Evidence-grounded Korean persona RAG architecture

Research valid at 2026-07-13. Scope assumes a legally and contractually authorized, provenance-complete blog corpus. Authorization to store a corpus does not imply that every block is eligible for persona simulation; block-level authorship, quotation, privacy, and deletion controls remain mandatory.

## 1. Decision

Build two products over one evidence layer, not one unconstrained "persona chatbot":

1. **Source-attributed analyst (default):** third-person, dated analysis of what the author wrote, every factual/stance clause linked to source spans. It may compare historical positions and must say when the corpus is silent or conflicted.
2. **Disclosed first-person role-play (optional, higher-risk and not public-by-default):** first-person rendering is a separately authorized identity act, not a semantics-neutral style transformation. Changing “the author wrote X in 2023” to “I believe X” changes speaker and may imply current endorsement. Keep public output in dated third person. If authorized role-play is tested privately, use explicit archival/fictional framing, visible citations, human review for high-risk assertions, and never claim it represents current belief.

RAG supplies evidence at inference time; it does not itself establish persona fidelity. Peer-reviewed evidence shows that RAG can improve factuality/provenance, but RAGTruth documents unsupported and contradictory claims despite retrieval, HoH shows stale evidence harms answers even when current evidence is present, and persona-consistency work adds NLI, rewrite, training, attribute extraction, or special memory mechanisms rather than relying on nearest-neighbor retrieval alone.

## 2. System architecture

```text
AUTHORIZED RAW CORPUS
  -> deterministic normalization + provenance/rights gate
  -> document / paragraph / sentence-span records
  -> claim candidates + exact evidence spans
  -> temporal claim graph + versioned profile memory
  -> immutable index generation
       |-- Korean BM25 (Nori/Kiwi-aware lexical fields)
       |-- Korean dense vectors (KURE-v1 or benchmark winner)
       |-- exact quote/ngram index

QUERY
  -> authorization + mode gate
  -> deterministic intent/time parser + bounded classifier
  -> metadata/temporal filter plan
  -> lexical and dense candidate retrieval in parallel
  -> reciprocal-rank fusion -> optional cross-encoder rerank
  -> claim/contradiction evidence pack
  -> grounded answer planner
       |-- analyst renderer
       `-- optional disclosed first-person style renderer
  -> atomic-claim support verifier + exact-quote validator
  -> citation assembler / abstention gate
  -> response + evidence trace + corpus generation ID
```

The generator has no write path to the source corpus, profile, indexes, prompt, credentials, or tools. Retrieved blog text is untrusted data even when the owner authorized its acquisition.

## 3. Ingest and normalization

### 3.1 Immutable layers

Maintain distinct representations:

- `raw_artifact`: immutable authorized bytes, capture hash, consent/policy version;
- `document_revision`: one post version with canonical post identity and publication/capture times;
- `source_block`: title, paragraph, list, quote, table, caption, media OCR, comment, or unknown component with page/DOM offsets;
- `sentence_span`: Korean sentence boundaries inside an eligible paragraph, retaining parent and character offsets;
- `claim`: an extracted proposition, never treated as truth merely because an LLM extracted it;
- `profile_item`: a derived, versioned author attribute with supporting and counter-evidence sets.

Normalization must not destroy evidence needed for quotations:

- preserve NFC source text and exact character offsets;
- create a separate NFKC/search-normalized field;
- normalize line endings and invisible controls in the search field only;
- retain punctuation, emoji, dialect, spacing, honorifics, sentence endings, and code-switching for style analysis;
- never merge media OCR, comments, quotations, or platform chrome into author prose;
- every derived object stores `derivation_version`, `source_revision_id`, and source span hashes.

### 3.2 Korean segmentation

Use paragraph boundaries as citation parents. Split sentences with a pinned Korean segmenter (Kiwi or KSS) but store the original paragraph and offsets. Do not index arbitrary fixed-token chunks as the only unit.

Index three linked granularities:

- **sentence/claim child:** precise lexical and semantic matching;
- **paragraph parent:** enough context for qualification, negation, and citation;
- **document summary metadata:** coarse candidate routing only, never evidence by itself.

For a hit, return the parent paragraph plus only the adjacent sentence needed to resolve pronouns or ellipsis. Chunk/window sizes must be selected on an in-domain Korean retrieval set; no universal character/token size is asserted.

Elasticsearch's official Nori tokenizer uses `mecab-ko-dic`, supports compound decomposition, and allows user dictionaries. Use `decompound_mode=mixed` so exact compounds and components coexist. Maintain a reviewed user dictionary for names, products, coined expressions, dialect spellings, and recurring blog terms. Kiwi can supply morphology/sentence boundaries for preprocessing and evaluation, but one analyzer configuration must be version-pinned per index generation.

### 3.3 Claims

Extract atomic claim candidates from eligible author-original sentences:

```text
claim_id
subject / predicate / object-or-complement
polarity                 positive | negative
modality                 asserted | uncertain | hypothetical | quoted
claim_kind               fact | preference | value | plan | experience | style
valid_from / valid_to    nullable, with precision day|month|year|unknown
asserted_at               post publication time
source_span_id            exact paragraph/sentence offsets
extraction_confidence
review_status             machine_candidate | accepted | rejected
```

Keep the source statement and extraction separate. Negation, hedging (`아마`, `생각한다`, `당시에는`), reported speech, quotations, sarcasm, and hypothetical language block automatic promotion to a profile item. High-impact/current persona claims require either human review or corroboration from multiple independent owner-original passages.

## 4. Temporal claim graph and contradictions

Claims are append-only versions, not mutable profile fields.

```text
claim A --SUPPORTS--> claim B
claim A --CONTRADICTS_CANDIDATE--> claim C
claim A --SUPERSEDED_BY--> claim D
claim A --QUALIFIES--> claim E
```

An NLI model can propose edges, but only deterministic time/identity evidence or review can mark `SUPERSEDED_BY`. Semantic opposition without matching subject, scope, and time is not a contradiction.

Retrieval views:

- `latest_observed`: return the most recent eligible authored assertion with its date. A missing `valid_to` means only that no later observation is recorded; it does not establish present belief;
- `current`: return only after an explicit reaffirmation within a predeclared freshness rule authorized for the use case; otherwise return `unknown_current` plus the latest observed dated assertion;
- `historical(as_of=t)`: require interval containment at `t` and cite sources available by `t`;
- `trajectory`: retrieve all accepted versions, order by asserted/valid time, and describe changes without selecting one as timeless;
- `unknown_time`: do not coerce to current; label undated and lower confidence.

If same-time eligible claims conflict and neither supersedes the other, return both evidence sets and abstain from a unified position. HoH's finding that outdated content distracts and misleads RAG makes metadata filtering before vector search a correctness boundary, not a ranking hint.

## 5. Retrieval

### 5.1 Query routing

First parse explicit dates/ranges and Korean temporal expressions deterministically. Then classify into one or more routes:

| Route | Retrieval behavior |
|---|---|
| `exact_quote` | exact/NFC substring and character n-gram search; dense retrieval cannot authorize quotation marks |
| `current_stance` | active accepted stance claims; changed-view evidence included when material |
| `historical_stance` | `as_of` interval filter before ranking |
| `stance_trajectory` | version-group retrieval, chronological synthesis |
| `factual_recall` | claims + paragraph parents, dated citations |
| `style_example` | eligible prose exemplars matched by discourse situation; assertions separately grounded |
| `profile_summary` | versioned profile items with support/counter sets |
| `open_chat` | retrieval only if the requested response needs corpus evidence; otherwise generic assistant behavior, not simulated biography |
| `unsupported/out_of_scope` | abstain or answer explicitly outside persona mode |

The bounded classifier returns probabilities and can select multiple routes. Low confidence expands to safe multi-route retrieval; it never invents a date or silently defaults an explicitly historical query to current.

### 5.2 Hard filters before scoring

Every candidate must match:

```text
owner_subject_id
authorization_scope and consent_version
lifecycle = active
rights_state = eligible
origin = owner_original
language = ko (or explicit code-switch allowance)
index_generation = serving_generation
requested time interval
mode allowlist (analysis vs simulation)
injection_state != blocked
```

Apply these in SQL/search filters, not in a prompt. With approximate vector indexes, test filtered recall: pgvector documents that approximate filtering occurs after index scanning and can return too few rows; iterative scans, partial indexes, or partitioning may be required.

### 5.3 Korean hybrid ranking

Run in parallel:

1. **Lexical:** BM25 over Nori `mixed` morphology plus exact surface/name/date/quote fields. This protects rare names, Korean compounds, dates, quoted phrases, and negation markers.
2. **Dense:** benchmark KURE-v1 and BGE-M3 on the authorized corpus. KURE-v1 is BGE-M3 fine-tuned for Korean retrieval and publishes Korean MTEB results; BGE-M3 supports dense, learned sparse, and multi-vector retrieval across 100+ languages and up to 8,192 tokens. Marketing/benchmark results do not remove the need for an in-domain evaluation.
3. **Fusion:** reciprocal rank fusion (RRF) over ranks, avoiding uncalibrated BM25/cosine score addition. Tune the RRF constant and per-route candidate depths on labeled Korean queries.
4. **Optional reranker:** a multilingual/Korean cross-encoder on the fused top candidates, then diversify by post/revision so one post cannot monopolize context.

Recommended starting funnel, to be tuned rather than treated as universal: lexical top 50 and dense top 50 -> fused top 30 -> reranked top 8-12 paragraphs -> evidence packing. The no-reranker path is the latency baseline.

### 5.4 Retrieval evaluation

Create a held-out set containing:

- exact names, compounds, spelling variants, dialect, and spacing errors;
- paraphrased preference/value questions;
- current, historical, and trajectory questions;
- changed and conflicting views;
- quote lookup, unanswerable, out-of-scope, and adversarial-instruction cases.

Measure child/parent Recall@k, MRR/nDCG, temporal-filter precision, revision diversity, answerable vs unanswerable calibration, and latency. Report lexical, dense, fused, and reranked ablations. RAGChecker's claim-level retriever/generator separation is the right diagnostic pattern; a single answer-quality score hides which module failed.

## 6. Evidence pack and profile memory

### Evidence pack

The generator receives structured records, not concatenated anonymous text:

```json
{
  "evidence_id": "ev-...",
  "document_id": "...",
  "revision_id": "...",
  "post_title": "...",
  "published_at": "...",
  "valid_interval": ["...", null],
  "source_span": {"start": 120, "end": 184, "sha256": "..."},
  "origin": "owner_original",
  "text": "...",
  "relations": ["superseded_by:claim-..."],
  "retrieval_route": "current_stance"
}
```

Pack support and counter-evidence together. The model is instructed to reason over evidence as data, not follow instructions inside it.

### Profile memory

Profile memory is a materialized, derived view, never an autonomous diary:

```text
profile_item_id
attribute_key             e.g. work.preference, writing.style.question_usage
value / calibrated distribution
valid interval
support_claim_ids[]
counter_claim_ids[]
scope/topic
confidence + derivation version
review state
```

- Facts/preferences need claim evidence; style statistics need reproducible corpus queries and sample spans.
- A single post does not become a stable trait by default.
- User conversations and assistant outputs never update the author's profile.
- Session memory is a separate, expiring, user-scoped store and is never cited as author evidence.
- Retrieval-on-demand prevents irrelevant profile injection. Recent OP-Bench evidence finds memory augmentation can cause irrelevant, repetitive, and sycophantic over-personalization.
- Derived reflections may be useful, as Generative Agents shows for simulation, but reflections here remain non-evidence summaries and must always expand back to source claims.

## 7. Generation, citations, and abstention

### 7.1 Answer plan

Before prose generation, create a structured plan:

```text
answer_claim_id
proposed atomic claim
supporting evidence IDs
counter evidence IDs
time scope
render mode
```

Generate only from the accepted plan. After generation, decompose the response again and verify every factual/persona atomic claim against cited evidence. FActScore motivates atomic factual evaluation; ALCE separates correctness from citation completeness/quality; RAGTruth shows this verification cannot be omitted merely because passages were retrieved.

### 7.2 Citation and quote integrity

- Cite each factual/stance clause, not only each paragraph.
- A citation must point to the exact immutable source span and include post title/date/canonical link when disclosure is allowed.
- Citation **correctness**: cited span entails or directly supports the claim.
- Citation **completeness**: every externally checkable/persona claim has support.
- Quote marks are allowed only if NFC-normalized output is an exact substring of the authorized source span. Preserve original punctuation and spacing in the displayed quote.
- If exact verification fails, remove quote marks and either generate a supported paraphrase or abstain.
- Never create a composite quote from multiple spans.
- Keep direct quote length governed separately; technical exactness does not grant copyright permission.

### 7.3 Abstention

Abstain or qualify when any condition holds:

- no eligible evidence above a route-specific calibrated threshold;
- retrieved passages are relevant but do not entail the planned claim;
- temporal intent is ambiguous and current/historical answers differ;
- unresolved same-time contradiction;
- only quotes/comments/third-party/media OCR support the answer;
- requested first-person belief/experience is absent;
- exact quote validation fails and paraphrase would change meaning;
- authorization/deletion/index generation is stale;
- prompt injection or poisoned-content gate fires.

Return a reason code (`NO_EVIDENCE`, `TEMPORAL_AMBIGUITY`, `CONFLICT`, `RIGHTS_BLOCK`, `QUOTE_MISMATCH`, `POLICY_BLOCK`) and optionally the nearest safe evidence. Thresholds must be calibrated against labeled answerable/unanswerable Korean queries, not selected by intuition.

## 8. Analysis mode vs first-person simulation

| Property | Source-attributed analyst | First-person simulation |
|---|---|---|
| Default | yes | no; explicit user/owner opt-in |
| Voice | third person | first person with persistent simulation disclosure |
| Evidence | mandatory per claim | mandatory before style transformation |
| Unknowns | "the corpus does not establish..." | cannot invent an answer; same abstention |
| Current position | only active claim versions | same evidence, rendered as simulation |
| Historical position | dated description | explicitly historical first-person framing, never presented as current |
| Style | neutral synthesis | eligible style exemplars, but no copied signature phrases by default |
| Citations | visible | visible; never hidden for immersion |
| Evaluation | factual/temporal/citation | all analyst tests plus persona consistency, disclosure, non-impersonation, and drift |

Implementation rule: produce an evidence-backed third-person answer first. A semantic diff/NLI check may detect some drift in an optional privately authorized role-play renderer, but cannot prove equivalence, especially for Korean hedging, sarcasm, negation, speaker identity, or temporal force. Any detected drift is rejected; passing automated checks still does not authorize public first-person output.

## 9. Prompt-injection boundary

OWASP explicitly includes an attacker-modified RAG repository document as prompt injection. Treat all corpus text as untrusted:

- ingestion detects/labels instruction-like spans but detection is not a complete defense;
- data and instructions use separate typed fields and fixed delimiters;
- never interpolate retrieved text into system/developer instructions;
- no retrieved content can request tools, network, secrets, memory writes, policy changes, or additional retrieval scopes;
- the generator in persona mode has no tools and no secrets;
- authorization and metadata filters execute before the model;
- output validation rejects leaked delimiters, control text, unsupported tool syntax, and evidence-free claims;
- adversarial fixtures include Korean imperative injection, encoded/hidden instructions, quoted prompts, and instructions inside images/OCR;
- provenance signatures and corpus-generation manifests detect unauthorized index changes.

Prompt-level reminders are defense-in-depth, not a security boundary.

## 10. Latency and cost

Critical-path model:

```text
T_total = T_route
        + max(T_lexical, T_dense)
        + optional T_rerank
        + T_generate
        + optional T_claim_verify
        + T_quote/citation_validate
```

Serving tiers:

| Tier | Path | Trade-off |
|---|---|---|
| Fast analyst | deterministic route + parallel BM25/dense + RRF + one generation + deterministic quote/citation checks | lowest model latency; weaker fine-grained relevance/support assurance |
| Standard | fast path + cross-encoder rerank + atomic post-generation support check | preferred default; extra model pass |
| High assurance | standard + contradiction expansion + independent verifier + style semantic-diff check | highest latency/cost; required for first-person or sensitive stance answers |

Cost controls:

- precompute embeddings/claims/profile items per immutable revision;
- route `exact_quote` to lexical search without dense or generation when possible;
- skip retrieval for generic non-persona chat, following the retrieval-on-demand principle supported by Self-RAG;
- cache retrieval traces by normalized query, filters, mode, model versions, and `index_generation`;
- never cache across different `as_of`, consent, rights, or corpus generations;
- batch offline embedding and rebuilds; benchmark KURE/BGE inference on actual hardware;
- measure recall loss before enabling ANN compression/approximation. pgvector documents HNSW as faster in query speed/recall trade-off than IVFFlat but slower to build and more memory-intensive.

No external benchmark latency is used as a production SLA. Record p50/p95/p99 per stage and token/model cost per answered and abstained query.

## 11. Deletion and rebuild

Maintain a dependency graph:

```text
document revision
  -> source blocks
  -> sentence spans / claims
  -> lexical postings / dense embeddings
  -> contradiction edges
  -> profile items
  -> retrieval caches / evaluation fixtures
```

Deletion, consent revocation, or private transition:

1. Transactionally mark the source revision non-serving and emit a signed deletion event.
2. Remove/tombstone its lexical and vector entries from the active generation.
3. Invalidate retrieval/answer caches keyed to the generation.
4. Recompute affected claim relations and every profile item whose support/counter set changed; delete an item with no valid support.
5. Remove derived style exemplars/statistics and evaluation fixtures containing the source.
6. Increment `corpus_generation`; new requests cannot use the previous generation.
7. Build a shadow index from the authorized snapshot, verify row counts, source hashes, filter behavior, and golden-query results, then atomically switch the serving alias.
8. Keep or erase restricted raw lineage only according to the governing retention/deletion policy; it is never queryable by the persona service.
9. Require acknowledgements from every downstream consumer and record deletion-lag SLA.

Do not attempt in-place mutation of embeddings or profile prose without dependency recomputation. A deleted source can otherwise survive as a summary, cache entry, contradiction edge, or style exemplar.

## 12. Minimal empirical check

A local Node.js fixture tested deterministic temporal filtering and exact-quote validation with two opposing Korean work-preference claims:

```text
old: 2021-01-01..2023-12-31 "나는 원격근무를 선호한다."
new: 2024-01-01..open       "지금은 사무실에서 동료와 협업하는 방식을 더 선호한다."
```

Observed result:

- without a time filter, a simple Korean character-bigram lexical score tied the old and new claims (`0.2857` each);
- `as_of=2022-06-01` admitted only the old work-preference claim;
- `as_of=2026-07-13` admitted only the new claim;
- an exact source substring passed quote validation; an altered quote failed.

Verdict: **CONFIRMED** for the narrow deterministic properties: temporal eligibility must precede ranking, and quote integrity can be enforced by source-span substring checks. This toy test does not validate dense retrieval quality, NLI accuracy, or persona fidelity.

## 13. Acceptance and evaluation gates

1. Every returned source block is eligible under the serving consent/rights/index generation.
2. Exact-name, exact-quote, paraphrase, current, historical, trajectory, and unanswerable Korean retrieval suites meet separately defined recall targets.
3. Current queries never cite expired claims as the current position.
4. Historical queries never use evidence published after `as_of` unless clearly labeled retrospective evidence.
5. Same-time unresolved contradiction returns both sides and abstains from synthesis.
6. Every response atomic claim is entailed by at least one citation; citation completeness and correctness are scored separately.
7. Every displayed quote exactly verifies against one source span.
8. Simulation output adds no semantic claim relative to the supported analyst plan and always displays disclosure.
9. Retrieved instructions cannot change tools, policies, memory, filters, or output contract.
10. Deleting any fixture source removes it from retrieval, profile memory, caches, style exemplars, and rebuilt indexes.
11. Lexical, dense, hybrid, and reranked ablations are retained; hybrid is deployed only if it wins the in-domain evaluation at acceptable p95/cost.
12. Run RAGTruth-style hallucination spans, ALCE-style citation support/completeness, FActScore-style atomic precision, RAGChecker retrieval/generator diagnostics, temporal conflict tests, and persona consistency/NLI tests.

## 14. Evidence and sources

Primary papers/docs:

1. Foundational RAG: https://papers.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html
2. BGE-M3 multilingual/dense-sparse-multivector paper: https://arxiv.org/abs/2402.03216
3. Nori tokenizer official reference: https://www.elastic.co/docs/reference/elasticsearch/plugins/analysis-nori-tokenizer
4. Reciprocal Rank Fusion paper: https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
5. RAGTruth, ACL 2024: https://aclanthology.org/2024.acl-long.585/
6. ALCE citation evaluation: https://arxiv.org/abs/2305.14627
7. FActScore atomic factual precision: https://arxiv.org/abs/2305.14251
8. RAGChecker diagnostics: https://arxiv.org/abs/2408.08067
9. Self-RAG retrieval-on-demand and critique, ICLR 2024 author manuscript: https://arxiv.org/abs/2310.11511
10. HoH outdated-information benchmark, ACL 2025: https://aclanthology.org/2025.acl-long.301/
11. Generative Agents memory/relevance/recency/reflection, UIST 2023: https://arxiv.org/abs/2304.03442
12. Persona consistency via pragmatic/NLI mechanism, EMNLP 2020: https://aclanthology.org/2020.emnlp-main.65/
13. Persona consistency via generate-delete-rewrite, ACL 2020: https://virtual.acl2020.org/paper_main.516.html
14. Persona factual consistency, EACL 2021: https://aclanthology.org/2021.eacl-main.44/
15. Retrieval augmentation for personalized dialogue, EMNLP 2023: https://aclanthology.org/2023.emnlp-main.154.pdf
16. Character-LLM profile/experience training: https://arxiv.org/abs/2310.10158
17. OP-Bench over-personalization counterevidence: https://arxiv.org/abs/2601.13722
18. RAG-based role-play with adaptive splitter/selection/attributes (supporting but not RAG-alone evidence): https://arxiv.org/abs/2508.02016
19. OWASP LLM01 prompt injection: https://genai.owasp.org/llmrisk/llm01-prompt-injection/

SHA-pinned verified OSS:

1. KURE-v1 Korean retrieval model/evaluation, commit `992e31d8e0b127dd27b1d387548739b84d9607d3`: https://github.com/nlpai-lab/KURE/blob/992e31d8e0b127dd27b1d387548739b84d9607d3/README.md
2. FlagEmbedding/BGE-M3 and rerankers, commit `7ed43d67ec03fbe5c31c0992dbfa941fb1860549`: https://github.com/FlagOpen/FlagEmbedding/blob/7ed43d67ec03fbe5c31c0992dbfa941fb1860549/README.md
3. Kiwi Korean morphology/sentence splitting, commit `693d6f2e029cd7635853ae32d917c315c5efa3f4`: https://github.com/bab2min/Kiwi/blob/693d6f2e029cd7635853ae32d917c315c5efa3f4/README.md
4. KSS sentence segmentation, commit `d7e26bd565569e816268a838a3816b3ed84d8034`: https://github.com/hyunwoongko/kss/blob/d7e26bd565569e816268a838a3816b3ed84d8034/README.md
5. RAGChecker claim-level diagnostics, commit `6091f08c00e676e87a970f2aeb4a23a484746348`: https://github.com/amazon-science/RAGChecker/blob/6091f08c00e676e87a970f2aeb4a23a484746348/README.md
6. ALCE citation evaluation, commit `246c476a4edfc564266b7346b6e29ef4861ae937`: https://github.com/princeton-nlp/ALCE/blob/246c476a4edfc564266b7346b6e29ef4861ae937/README.md
7. RAGTruth dataset/evaluation, commit `c103204b9ce28d6bbad859304bf30de72b8ed8fe`: https://github.com/ParticleMedia/RAGTruth/blob/c103204b9ce28d6bbad859304bf30de72b8ed8fe/README.md
8. pgvector ANN/filter/index behavior, commit `a6420355c5d1c08f4c5fbd5112fc17e4cf3b5eb5`: https://github.com/pgvector/pgvector/blob/a6420355c5d1c08f4c5fbd5112fc17e4cf3b5eb5/README.md

Research method: 24 distinct web queries across Korean retrieval, hybrid ranking, temporal RAG, persona consistency, citations, hallucination, memory, and prompt injection; primary/peer-reviewed sources were preferred and counter-search explicitly sought both RAG-for-persona improvements and evidence that retrieval alone is insufficient.

## EXPAND

- LEAD: Build an authorized Korean golden set from real corpus questions, including changed stances, dialect/spacing, exact quotes, and unanswerables. - WHY: public Korean benchmarks do not measure this author's temporal/persona retrieval. - ANGLE: stratified human annotations with lexical/dense/hybrid/reranker ablations.
- LEAD: Benchmark KURE-v1, BGE-M3 dense, BGE-M3 learned sparse, and a Korean cross-encoder on target hardware. - WHY: model papers and Korean MTEB scores do not determine in-domain recall, filtered ANN behavior, latency, or cost. - ANGLE: fixed candidate corpus, cold/warm p95, Recall@k/nDCG, memory and rebuild time.
- LEAD: Calibrate Korean NLI/claim verification and contradiction thresholds. - WHY: semantic opposition, historical change, quotation, sarcasm, and hedging can be confused. - ANGLE: manually labeled support/contradict/neutral/temporally-compatible pairs.
- LEAD: Validate style transformation without semantic drift. - WHY: first-person rendering can invent stronger beliefs or currentness even when retrieval is correct. - ANGLE: paired analyst/simulation outputs, atomic semantic diff, human reviewers, adversarial absent-experience prompts.
- LEAD: Run deletion drills through embeddings, profile items, caches, evaluations, and serving aliases. - WHY: derived memory can preserve deleted data after source removal. - ANGLE: dependency-ledger audit with maximum deletion-lag measurement.
- DEAD END: Treating a high vector similarity score as evidence support. Relevance does not entail a claim, resolve time, or authorize a quote.
- DEAD END: Treating a retrieved profile/memory as always useful. Retrieval-on-demand and OP-Bench counter indiscriminate personalization.

## CLAIMS

- CLAIM: RAG improves access to explicit evidence and updateable non-parametric memory but does not guarantee grounded or persona-faithful generation. - STATUS: supported - RISK: high - SOURCES: NeurIPS RAG, ACL RAGTruth, ACL HoH, EMNLP/ACL persona consistency papers - COUNTER: RAG-based persona systems report gains, but use adaptive selection, attribute extraction, emotion, NLI, rewrite, or training beyond baseline RAG - PRIMARY: peer-reviewed papers plus current persona preprints
- CLAIM: Korean persona retrieval should benchmark lexical and dense channels and fuse them rather than assume dense-only superiority. - STATUS: supported design inference - RISK: normal - SOURCES: Nori official docs, BGE-M3 paper, KURE OSS/results, RRF paper - COUNTER: a sufficiently strong dense model may win a specific corpus; ablation is the deployment gate - PRIMARY: official documentation and papers
- CLAIM: Temporal metadata must filter candidates before ranking for current/historical queries. - STATUS: supported - RISK: high - SOURCES: ACL HoH plus local deterministic fixture - COUNTER: temporal ranking alone could sometimes demote stale material, but cannot guarantee exclusion or historical correctness - PRIMARY: peer-reviewed benchmark and executed check
- CLAIM: Every persona assertion should be evaluated as an atomic claim with citation correctness and completeness separated. - STATUS: supported - RISK: high - SOURCES: FActScore, ALCE, RAGChecker, RAGTruth - COUNTER: automatic NLI/claim extraction is imperfect, so sensitive claims require review/calibration - PRIMARY: peer-reviewed papers and pinned evaluation OSS
- CLAIM: Exact quotations can and should be deterministically checked against immutable source spans. - STATUS: supported by execution - RISK: normal - SOURCES: local Node.js fixture and provenance design - COUNTER: substring integrity proves textual exactness, not copyright permission, authorship, or contextual fairness - PRIMARY: executed local verification
- CLAIM: Source-attributed analysis is safer and epistemically clearer than first-person simulation; simulation must be a disclosed, evidence-preserving style layer. - STATUS: supported design conclusion - RISK: high - SOURCES: persona consistency research, Character-LLM, RAGTruth, ALCE - COUNTER: role-play systems may improve immersion/persona scores, but those scores do not establish real-person identity, current belief, or absence of semantic drift - PRIMARY: peer-reviewed papers and primary preprints
- CLAIM: Prompt injection remains a boundary concern even for an authorized corpus; retrieved text cannot be trusted as instructions. - STATUS: supported - RISK: high - SOURCES: OWASP LLM01 and indirect-prompt-injection research - COUNTER: provenance and filters reduce risk but no prompt-only defense establishes a control boundary - PRIMARY: OWASP and security papers
- CLAIM: Deletion is incomplete unless dependent claims, embeddings, profile memory, caches, style exemplars, and index generations are rebuilt or invalidated. - STATUS: supported systems invariant - RISK: high - SOURCES: lineage architecture and pgvector index behavior - COUNTER: direct index-row deletion is sufficient only when no derived artifact or cache exists, which is not this architecture - PRIMARY: executed architecture dependency analysis and pinned pgvector documentation
