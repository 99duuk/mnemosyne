# ULW-Research Synthesis: 네이버 블로그 기반 사고·문체 프록시

Research date: 2026-07-30 KST  
Scope: implementation architecture, collection boundary, Korean legal/privacy risk, local-Mac feasibility, and evaluation.  
This is a technical research synthesis, not legal advice.

## Executive summary

The requested outcome should not be specified as “an exact duplicate of a person's thinking.” A blog only records selected, dated public expressions; it cannot prove current beliefs, private reasoning, or future decisions. Current digital-twin research likewise finds that even strong LLMs struggle to simulate continuous human behaviour, not merely dialogue. The implementable product is therefore a **source-grounded writing-and-viewpoint proxy**: it answers only what the author wrote, identifies the date and source, preserves contradiction and change over time, and abstains outside that evidence. [BehaviorChain](https://aclanthology.org/2025.findings-acl.813/)

For an unknown person's NAVER Blog, an all-post automatic crawler is not an acceptable starting point. NAVER's current legal notice restricts automated collection to explicit permission/pre-approval, compliant API access, or allowed guidance/robots scope; the current Blog robots observation also specifically flags AI-training/RAG automation. A human click or Safari shortcut changes the mechanics, not the underlying platform or rights basis. [NAVER legal notice](https://policy.naver.com/policy/disclaimer.html) · [NAVER Blog robots](https://blog.naver.com/robots.txt) · [Apple Shortcuts web-page inputs](https://support.apple.com/en-gb/guide/shortcuts-mac/apd7644168e1/mac)

The practical design is therefore conditional:

1. **No author/platform permission:** do not build the all-post corpus or a named first-person clone. At most consider a separate, source-attributed documentary analysis after fact-specific copyright/privacy review.
2. **Author permission plus an owner-delivered corpus:** build a private, third-person RAG system first. NAVER documents owner-side PDF backup of directly authored posts, but it is lossy and is not a transferable account export. Prefer the author's original Markdown/HTML/media in addition to PDF. [NAVER Blog backup](https://help.naver.com/service/5593/contents/15293?lang=ko&osType=PC) · [NAVER PDF procedure](https://help.naver.com/service/5593/contents/15295?lang=ko&osType=PC)
3. **Only after evidence and safety gates pass:** consider a small, unmerged style adapter for residual voice patterns. Do not use it as the store of facts, current views, citations, or deletion-sensitive content.

## 1. Problem analysis

### 1.1 The requested “mind clone” has no valid test oracle

“Think exactly like the person” has no observable ground truth from blog posts alone. The attainable test target is narrower:

- retrieve the relevant post and exact span;
- state *what was written*, when it was written, and whether later posts contradict it;
- reproduce only evidence-backed rhetorical tendencies;
- say `unknown` when the corpus does not support a claim;
- never speak as the real person or imply a current opinion without recent explicit evidence.

This distinction is product-critical: a first-person answer adds speaker identity and apparent present-tense endorsement that a historical post does not establish. The research benchmark above shows why fluent conversation is not evidence of faithful behavioural replication. [BehaviorChain](https://aclanthology.org/2025.findings-acl.813/)

### 1.2 Public visibility is not a collection or reuse licence

Treat four gates independently:

| Gate | Required question | MVP action on failure |
|---|---|---|
| Platform access | Is NAVER allowing this exact endpoint, rate, automation, storage and AI purpose? | Do not automate collection. |
| Copyright/DB | Is there a valid basis to copy, transform, embed, train on and serve each text/media block? | Exclude or obtain permission. |
| Personal information | Does content contain personal/sensitive data, and is there a documented processing basis, purpose, retention and deletion path? | Quarantine and review. |
| Identity/public representation | Is there explicit permission to name, imitate, use first-person voice or publish it? | Private third-person analysis only, or stop. |

NAVER's own terms describe the licence that a member grants **NAVER**; they do not grant third-party collectors a separate reuse licence. Korean PIPA requires a processing basis and purpose limitation, and PIPC's generative-AI guidance calls for source verification, privacy-preserving preparation, access control, testing, user rights and transparency across the AI lifecycle. [NAVER Terms](https://policy.naver.com/rules/service_en.html) · [PIPA Article 15](https://law.go.kr/lsLinkCommonInfo.do?lsJoLnkSeq=1020398625) · [PIPC generative-AI guidance](https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS211&mCode=C040020000&nttId=11414)

**Result for the stated stranger case:** the request cannot safely be implemented as “collect all their posts and train a clone.” Do not replace missing permission with scraping, manual bulk capture, bot-evasion, cookies, or browser automation.

## 2. Correct implementation target

Define the product as:

> A private, source-attributed assistant that describes the author's documented statements, reasoning patterns and stylistic features as of a specified date, with paragraph-level evidence and abstention outside the authorized corpus.

Default language is third-person: “In a post dated 2024-03-02, the author argued X because Y.” The interface always displays `Synthetic analysis - not the person`, source date, and a link or corpus document identifier.

## 3. Collection and corpus design

### 3.1 Accepted inputs

Accept only one of these paths:

1. Author's original Markdown/HTML/text and media, delivered outside NAVER with a rights/consent manifest.
2. Author-operated NAVER Blog PDF backup, plus a signed inventory and original media where needed. NAVER says the backup supports directly authored posts and lists PDF, size and media-format constraints. [NAVER Blog backup](https://help.naver.com/service/5593/contents/15293?lang=ko&osType=PC)
3. Written platform permission that names the collection route and permits the AI purpose.

Do **not** accept scraped article HTML, bulk browser exports, copied comments, or inferred post lists as canonical input. NAVER also says Blog data transfer/backup/ownership transfer between same-name IDs is unavailable; this does not contradict the per-post PDF feature, it describes a different capability. [NAVER Blog data-transfer help](https://help.naver.com/service/5593/contents/15183?lang=ko&osType=COMMONOS)

### 3.2 Package format

```text
delivery-<subject>-<snapshot-date>/
  consent-and-rights.json
  inventory.jsonl
  original/                 # preferred canonical source
  naver-pdf/                # optional evidence/backup source
  media/                    # separately licensed assets
  revisions.jsonl
  SHA256SUMS
```

Each `inventory.jsonl` record should contain at least:

```json
{
  "document_id": "author-2024-03-02-001",
  "source_url": "https://blog.naver.com/...",
  "title": "...",
  "published_at": "2024-03-02T09:00:00+09:00",
  "collected_at": "2026-07-30T00:00:00+09:00",
  "source_sha256": "...",
  "rights_basis_id": "consent-v1",
  "rights_scope": ["store", "index", "private_rag"],
  "visibility_at_capture": "public",
  "third_party_content": "quarantined"
}
```

Keep source, extracted text, chunks, embeddings, evaluation fixtures, answer cache and any adapter in a directed lineage graph. A future withdrawal must first suspend serving, then invalidate all descendants, then run a deletion/rebuild drill. A database row delete alone is insufficient.

### 3.3 PDF conversion QA

NAVER documents that some attachments and display forms are omitted or altered in PDF backup. Build a converter, but make it a non-authoritative derivative:

- retain the original PDF and hash;
- extract text to Markdown with page and paragraph anchors;
- sample-check title/date/body/quote anchors against the PDF;
- put OCR uncertainty, comments, quoted third-party text and images into quarantine;
- report corpus coverage as `complete relative to the owner-declared inventory at cutoff T`, never “all posts exist.”

## 4. Recommended architecture: RAG before training

```text
AUTHORIZED DELIVERY
  -> checksum + consent/rights gate
  -> raw store + extracted Markdown
  -> paragraph/span normalization + time metadata
  -> lexical index + vector index
  -> retrieval filtered by rights, lifecycle, author and as-of date
  -> evidence pack (supporting and contradicting spans)
  -> constrained generation
  -> claim/citation/time/identity verifier
  -> answer with sources OR explicit abstention
```

RAG is the first architecture because its evidence is inspectable, updateable and removable. The original RAG work combines parametric generation with explicit non-parametric memory; later comparison research found RAG consistently outperformed unsupervised fine-tuning for the paper's knowledge-injection tasks. That does not make RAG automatically trustworthy: retrieved text can be ignored or misread, so verify each atomic claim. [RAG paper](https://arxiv.org/abs/2005.11401) · [Fine-tuning vs. retrieval](https://arxiv.org/abs/2312.05934)

### Retrieval rules

- Filter by `rights_scope`, `active` lifecycle, subject, and `as_of` **before** ranking.
- Use a Korean lexical baseline (BM25/Nori or Kiwi) plus dense retrieval; decide hybrid/reranking only after a held-out Korean test set comparison.
- Preserve conflicting later/earlier positions rather than collapsing them into a single persona summary.
- Treat corpus text as untrusted data, never as instructions for the system or tools.
- Allow no external-action tools in the proxy. It should not send messages, post, buy, change accounts or claim authority.

### Output contract

```text
For every answer:
  1. Is the requested answer within authorized evidence?
  2. Extract dated atomic claims and counterevidence.
  3. Generate in third-person, with paragraph/span references.
  4. Verify each claim against its cited span and time qualifier.
  5. Otherwise return NO_EVIDENCE, TEMPORAL_AMBIGUITY,
     CONFLICT, RIGHTS_BLOCK, QUOTE_MISMATCH, or POLICY_BLOCK.
```

Do not equate “a citation was displayed” with “the claim is supported.” Citation research finds fine-grained support evaluation difficult and no single automatic faithfulness metric reliably wins across all settings; use deterministic span checks, human-labelled cases, and calibrated automated evaluation. [Citation evaluation study](https://aclanthology.org/2024.inlg-main.35/) · [ARES RAG evaluation](https://aclanthology.org/2024.naacl-long.20/)

## 5. Training decision

Do not start with raw-post next-token training. Keep facts, positions, dates and citations in the retrievable corpus. Consider an unmerged LoRA only when all conditions hold:

1. explicit written permission covers adaptation and the intended audience;
2. RAG grounding, temporal and identity gates already pass;
3. a blinded evaluation shows a persistent **style-only** failure that prompt/profile examples cannot fix;
4. the adapter does not worsen factuality, citation, privacy, Korean fluency or impersonation scores;
5. a deletion/rebuild plan covers adapter files, checkpoints, optimizer state and exports.

LoRA reduces the number of trainable parameters compared with full fine-tuning, but it does not turn training data into a harmless source. Language-model memorization and prompt-conditioned training-data emission remain documented risks, especially where repeated or distinctive text is involved. [LoRA](https://arxiv.org/abs/2106.09685) · [Memorization study](https://arxiv.org/abs/2202.07646)

## 6. Evaluation harness

Create a hold-out test set before tuning. Split by document/time/topic so the model cannot pass by memorizing near duplicates.

| Test family | Expected pass condition |
|---|---|
| Source support | Every atomic answer claim has an entailing source span, or the system abstains. |
| Citation correctness | Span points to the correct document, date, author and text; direct quotations match exactly. |
| Temporal | “As of 2023” excludes later posts; “current view” becomes `latest observed` unless reconfirmed. |
| Contradiction | Conflicting posts are shown as conflict, not silently averaged. |
| Style | Similarity judged on unseen topics while semantic claims and speaker identity remain unchanged. |
| Identity | System rejects “pretend you are them,” declares synthetic status, and does not imply live endorsement. |
| Privacy/rights | Revoked/quarantined chunks never retrieve; deletion drill removes descendants. |
| Prompt injection | Corpus strings attempting to alter policy are treated only as quoted evidence. |

Release gate: zero unsupported direct quotes, 100% blocked retrieval for revoked test documents, and predeclared thresholds for claim support and disclosure comprehension. Do not ship a public named first-person experience merely because a style score is high.

## 7. Mac M3 Pro deployment path

Apple documents PyTorch MPS acceleration on Apple silicon, and current local runtimes document Apple M-series/Metal support. Use the M3 Pro first for **inference, embeddings, indexing and evaluation**, not as the reason to train first. Exact model size depends on the actual unified memory and measured latency; it was not verified during this session because the local SSH client configuration currently rejects system SSH config ownership. [Apple PyTorch MPS](https://developer.apple.com/metal/pytorch/) · [Ollama macOS](https://docs.ollama.com/macos) · [llama.cpp](https://github.com/ggml-org/llama.cpp)

Suggested local components:

- raw files: encrypted local directory/object store;
- metadata and lineage: PostgreSQL or SQLite for a private MVP;
- lexical index: SQLite FTS5 or OpenSearch/Elasticsearch only when justified;
- vector index: SQLite-vector, LanceDB or a local FAISS index;
- inference: a small local model via Ollama/llama.cpp, or a hosted model only if the consent/data-processing scope permits it;
- embedding and evaluation runs: versioned by model, prompt, corpus snapshot and test-set version.

## 8. Delivery plan

| Phase | Deliverable | Hard gate |
|---|---|---|
| 0. Rights | signed scope, consent/rights matrix, retention/withdrawal policy | No valid scope = no target corpus. |
| 1. Ingestion | owner package validator, PDF-to-Markdown QA, inventory and hashes | No traceable source/rights record = quarantine. |
| 2. Private RAG | filtered retrieval, citations, abstention, third-person UI | No citation/temporal pass = no user access. |
| 3. Harness | held-out Korean suite, injection/revocation/identity tests | No predeclared metrics = no release decision. |
| 4. Operations | audit log, suspension, deletion/rebuild drill | Failed drill = no deletion guarantee. |
| 5. Optional adapter | shadow-mode LoRA comparison | No style-only benefit or safety regression = discard. |
| 6. Public decision | counsel review, clear disclosure, takedown SLA, consent scope | Named first-person mode remains blocked by default. |

## 9. Decision for the stated situation

Because the target is a stranger and permission cannot be requested, the correct next action is **not** to write a crawler. Build Phase 1-3 against your own writing or a consenting test author, complete the evaluation harness, and retain the ingestion adapter behind a rights gate. If a lawful/authorized corpus later becomes available, you can add it without changing the core architecture. If it never does, keep the project as a generic source-grounded writing-analysis product rather than a clone of that individual.

## Sources

1. [NAVER legal notice](https://policy.naver.com/policy/disclaimer.html) - automated collection conditions.
2. [NAVER Blog backup guide](https://help.naver.com/service/5593/contents/15293?lang=ko&osType=PC) - owner-side PDF backup limits and lossiness.
3. [NAVER Blog PDF procedure](https://help.naver.com/service/5593/contents/15295?lang=ko&osType=PC) - owner-operated workflow.
4. [NAVER Blog data transfer help](https://help.naver.com/service/5593/contents/15183?lang=ko&osType=COMMONOS) - no Blog data transfer/backup/ownership transfer between same-name IDs.
5. [NAVER terms (English translation)](https://policy.naver.com/rules/service_en.html) - member-to-NAVER licence context.
6. [PIPA Article 15](https://law.go.kr/lsLinkCommonInfo.do?lsJoLnkSeq=1020398625) - collection/use legal bases.
7. [PIPC generative-AI privacy guidance announcement](https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS211&mCode=C040020000&nttId=11414) - lifecycle controls.
8. [BehaviorChain](https://aclanthology.org/2025.findings-acl.813/) - limits of persona-based continuous-behaviour simulation.
9. [Retrieval-Augmented Generation](https://arxiv.org/abs/2005.11401) - explicit retrieval memory architecture.
10. [Fine-Tuning or Retrieval?](https://arxiv.org/abs/2312.05934) - knowledge-injection comparison.
11. [Fine-grained citation evaluation](https://aclanthology.org/2024.inlg-main.35/) - limitations of single faithfulness metrics.
12. [ARES](https://aclanthology.org/2024.naacl-long.20/) - RAG context/faithfulness/relevance evaluation.
13. [LoRA](https://arxiv.org/abs/2106.09685) - parameter-efficient adaptation.
14. [Quantifying memorization](https://arxiv.org/abs/2202.07646) - training-data emission risk.
15. [Apple PyTorch MPS](https://developer.apple.com/metal/pytorch/) - Apple-silicon acceleration.
16. [Ollama macOS](https://docs.ollama.com/macos) and [llama.cpp](https://github.com/ggml-org/llama.cpp) - local runtime support.
