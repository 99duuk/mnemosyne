# Training-method decision for one authorized Korean blog persona

Research date: 2026-07-13  
Scope: one authorized person's Korean blog corpus. Numeric release gates below are explicit engineering policy proposals, not universal empirical laws. They must be recalibrated for the selected base model and deployment risk.

## TL;DR

Use two independent planes:

```text
mutable truth plane: versioned profile + RAG -> facts, dated stances, citations, deletion
behavior plane: prompt contract -> optional unmerged LoRA -> optional DPO-on-LoRA
```

Do not put factual biography, current opinions, dated preferences, or quotable blog passages into weights merely because training is possible. Controlled research finds RAG more reliable than unsupervised fine-tuning for new and updated knowledge, while fine-tuning is better understood as behavior/format/style adaptation ([NeurIPS RAG](https://papers.nips.cc/paper_files/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html), [EMNLP 2024 comparison](https://aclanthology.org/2024.emnlp-main.15.pdf), [LIMA](https://papers.nips.cc/paper/2023/file/ac662d74829e4407ce1d126477f4a03a-Paper-Conference.pdf)).

The default production answer is **no training**. Train only when a versioned prompt/profile plus tested RAG passes grounding and safety gates but fails a predeclared style/behavior gate by a material margin. When training is justified, start with an unmerged, one-person LoRA/QLoRA adapter. Full SFT, continued pretraining, preference tuning, and distillation require separate escalation evidence.

## 1. What each plane owns

### Factual and stance grounding

The truth plane owns:

* biographical facts and events;
* dated views, preferences, and changes of mind;
* direct quotations and their exact source spans;
* uncertainty, contradiction, supersession, privacy, and deletion state;
* source URLs, post IDs, timestamps, rights versions, and citations.

These are retrieval records, not training targets:

```json
{
  "claim_id": "uuid",
  "subject": "person",
  "predicate": "prefers_workflow",
  "object": "structured_planning",
  "stance": "supports|opposes|mixed|unknown",
  "valid_from": "RFC3339|null",
  "valid_until": "RFC3339|null",
  "asserted_at": "RFC3339",
  "source_item_version_id": "uuid",
  "source_span": [120, 203],
  "quote_allowed": false,
  "confidence": "explicit|inferred|ambiguous",
  "supersedes_claim_id": "uuid|null",
  "rights_basis_version_id": "uuid",
  "governance_state": "active|restricted|deleted"
}
```

Retrieval must filter `governance_state=active`, resolve temporal scope, surface conflicting stances rather than averaging them, and attach a source to every persona-specific factual assertion. RAG does not guarantee correct use of retrieved evidence: long-context position effects and retrieval/synthesis failures are documented ([Lost in the Middle](https://arxiv.org/abs/2307.03172)). Therefore retrieval recall and generation faithfulness are separate gates.

### Style and behavior adaptation

The behavior plane owns stable tendencies that do not assert new facts:

* sentence length, paragraph rhythm, formality, Korean endings, vocabulary preferences;
* response organization, directness, hedging, examples, and question-asking behavior;
* refusal, uncertainty, citation, and identity-disclosure behavior;
* channel-specific format, not the person's changing beliefs.

Style adaptation should use approved prompt→response examples, not next-token training over the raw blog. That reduces direct copying pressure and lets reviewers remove personal/third-party facts. Fine-tuning can still memorize or reactivate source expression, so this transformation is risk reduction, not proof of non-memorization ([ICML deduplication study](https://proceedings.mlr.press/v162/kandpal22a.html), [ACL 2024 fine-tuning memorization](https://aclanthology.org/2024.acl-long.216.pdf), [2026 copyright-recall counterevidence](https://arxiv.org/abs/2603.20957)).

## 2. Exact decision matrix

Data gates are release-policy minima for this project, except where a paper's own scale is explicitly cited.

| Method | Correct job | Data construction/gate | Facts and dated stances | Style/behavior | Temporal update | Deletion/unlearning | Leakage/copyright | Checkpoint isolation | Relative cost | Decision |
|---|---|---|---|---|---|---|---|---|---|---|
| Static prompt/profile | Identity boundary, stable rules, short style contract | One versioned profile; 20–60 atomic rules; 8–20 approved examples; facts excluded | Weak unless facts are injected | Good for explicit traits; weak for implicit style | Edit immediately | Delete profile/examples and caches | Lowest weight-level risk; context may still leak | No new checkpoint | Build 1/5; inference context 2/5 | **Always first** |
| RAG | Factual/stance grounding, citations, current/deleted knowledge | All authorized items; semantic chunks normally 200–600 Korean tokens; item/time/right metadata; labeled retrieval set | **Best fit**; controlled comparison favors RAG for new knowledge | Moderate through retrieved style exemplars, but not guaranteed | Reindex individual records | Delete source/chunks/vectors/cache; no persona weights created | Verbatim output remains possible, so quote controls and overlap filters are required | Index namespace per corpus/version | Build 2/5; inference 3/5 | **Default grounding layer** |
| Full supervised fine-tuning | Stable response behavior when prompt/RAG measurably fail | Policy gate: ≥500 unique, manually approved prompt→response examples across ≥20 intent clusters; document/time-separated holdout; no raw next-token blog dump | Poor update mechanism; weights cannot cite or deterministically supersede | Strong, broad behavior change | Retrain/revalidate | Hard: all checkpoints/optimizer state affected; retrain/retire fallback | Higher memorization/copying and catastrophic-regression risk | Full persona-specific checkpoint | Build 4/5; train 4/5; inference 2/5 | **Generally reject**; consider only if LoRA fails a measured requirement |
| LoRA/PEFT or QLoRA | Same behavior objective as SFT with frozen base and separable adapter | Same ≥500-example policy gate; pilot may start at 200–300 only to estimate learning curves, never to ship without full gate | Not a factual store | Preferred training option for persistent style/format behavior | Retrain small adapter | Delete/retire unmerged adapter plus optimizer/intermediate artifacts; base stays unchanged only if never trained on corpus | Adapter can memorize; separation is not anonymization | **Strong if never merged**, one adapter/person/base hash | Build 3/5; train 2/5; inference 2–3/5 | **First training escalation** |
| Continued pretraining | Broad Korean/domain language modeling from a large unlabeled corpus | A single blog fails method fit regardless of token count; reconsider only for a broader licensed domain corpus and a language/domain objective | Unreliable for precise facts/updates | May absorb surface distribution but without behavioral labels | Expensive new training | Hardest; broad weight diffusion and forgetting | Highest raw-corpus memorization exposure | Full checkpoint; weak item isolation | Build/train 5/5 | **Do not use for one persona** |
| Preference tuning / DPO | Choose between acceptable behaviors after SFT/LoRA | Policy gate: ≥500 unique chosen/rejected pairs across ≥20 intent clusters; 10% blind repeats; ≥80% owner self-consistency; explicit reason codes | Does not add reliable knowledge | Useful for nuanced preferences such as directness, caveats, or verbosity | Retrain preference adapter | Same as its underlying LoRA/full checkpoint; pair data and reference scores also deleted | Rejected outputs can contain prohibited expression; distribution shift/overoptimization risk | Prefer separate DPO adapter on frozen base/SFT adapter | Build 4/5; train 3/5 | **Only after stable SFT/LoRA and real pairwise labels** |
| Distillation | Reduce inference cost/latency after the teacher is stable | Policy gate: ≥10,000 approved, diverse teacher traces with source IDs; held-out topics/time; teacher version frozen | Student still needs RAG; distillation is not a knowledge-update strategy | Can compress teacher behavior | Regenerate traces/retrain student | Separate student and traces must be retired; cannot delete teacher influence by deleting teacher alone | Students can inherit teacher membership/memorization risk | Separate full student checkpoint | Build/train 5/5; inference 1/5 | **Only for demonstrated serving economics** |

Evidence boundaries:

* LIMA demonstrates strong behavioral alignment from 1,000 curated examples on a 65B model, but also says knowledge is largely learned in pretraining and reports robustness limitations. It does **not** establish 1,000 as a universal persona threshold.
* LoRA freezes the base and trains low-rank updates; QLoRA reduces training memory enough to fine-tune a 65B model on one 48 GB GPU in the paper's setup ([LoRA](https://openreview.net/forum?id=nZeVKeeFYf9), [QLoRA](https://arxiv.org/abs/2305.14314)). That hardware result is not a guaranteed cost for another base, sequence length, or dataset.
* DPO's original paper reports stable, lightweight preference optimization, while later work finds weaker implicit-reward generalization under distribution shift ([NeurIPS 2023](https://proceedings.neurips.cc/paper_files/paper/2023/hash/a85b405ed65c6477a4fe8302b5e06ce7-Abstract-Conference.html), [EMNLP 2024 counterevidence](https://machinelearning.apple.com/research/reward-generalization)).
* Continued pretraining improves real domain tasks in appropriate settings, but forgetting is documented, including target-language adaptation without source-language mixture ([Don't Stop Pretraining](https://arxiv.org/abs/2004.10964), [Continual Domain-Tuning](https://arxiv.org/abs/2004.02288), [2025 language-adaptation study](https://arxiv.org/abs/2506.00288)).
* Distillation can lower serving cost, but peer-reviewed work finds privacy and memorization can transfer from teacher to student ([EMNLP 2025](https://aclanthology.org/2025.emnlp-main.1015.pdf), [NeurIPS 2021](https://papers.neurips.cc/paper_files/paper/2021/hash/4ca82782c5372a547c104929f03fe7a9-Abstract.html)).

## 3. RAG-first escalation rule

### Stage 0: build the no-training baseline

1. Create a fact-free behavior profile with explicit Korean style rules and identity/safety boundaries.
2. Build a versioned RAG corpus for facts, dated stances, source quotations, and style exemplars.
3. Generate with two passes when accuracy matters: source-grounded semantic answer first, style transformation second, with a meaning-preservation check.
4. Evaluate on the fixed 200-prompt suite below.

### Stage 1: no-training release gate

Release without training only when all conditions hold:

```text
retrieval Recall@10                     >= 0.95
persona factual claims with valid source >= 0.98
citation span correctness                >= 0.98
contradiction/obsolete-stance error       <= 0.01 and zero critical errors
owner-approved style score                >= 4.0 / 5.0
Korean naturalness/readability            >= 4.0 / 5.0
unsafe identity or third-party leakage    = 0 critical cases
unauthorized verbatim overlap             = 0 above internal review threshold
p95 latency and per-request cost           within product SLO/budget
```

These thresholds are internal release policy, not claims that academic literature identifies universal cutoffs.

### Stage 2: decide whether training is justified

Training is prohibited if any failure is primarily:

* missing/wrong retrieval;
* stale or conflicting facts/stances;
* missing citations;
* authorization, privacy, or deletion filtering;
* insufficient base-model Korean capability;
* prompt injection, tool failure, latency, or cost unrelated to response behavior.

Fix the corresponding subsystem. Training does not repair those root causes.

Escalate to LoRA only when:

1. grounding/safety gates already pass;
2. the same style/behavior failure appears in at least 20 prompts across at least five intent clusters;
3. prompt/profile and few-shot variants fail to improve it by at least 0.3/5 owner-rating points;
4. a blinded LoRA pilot improves owner preference by at least 10 percentage points, with the 95% confidence interval excluding zero;
5. factual, safety, Korean, leakage, and latency gates regress by no more than one percentage point and have no new critical failure;
6. deletion and checkpoint-isolation drills pass.

Escalate beyond LoRA only as follows:

```text
LoRA misses broad behavior requirement by >=5 pp while full SFT passes
  -> consider full SFT, otherwise reject

LoRA output is acceptable but owner repeatedly prefers one of two valid responses,
and preference data meets the pair/reliability gate
  -> DPO on an isolated adapter

Stable teacher passes all gates but measured inference cost/latency violates SLO,
and projected distillation savings exceed teacher-generation + training + QA cost
  -> distill; retain RAG and deletion lineage

Objective is only this person's persona
  -> never continued-pretrain
```

### When no training is justified

No training is justified when prompt/profile plus RAG meets the release gate, the remaining differences are subjective or inconsistent, there are fewer than 500 approved unique behavior examples, the owner cannot label preferences consistently, facts change frequently, deletion must be immediate, the corpus contains substantial third-party material, or serving volume cannot amortize training and evaluation cost.

## 4. Corpus construction

Raw blog posts are evidence sources. They are not automatically instruction examples.

### Style example schema

```json
{
  "example_id": "uuid",
  "intent_cluster": "explain_tradeoff",
  "prompt_ko": "...",
  "approved_response_ko": "...",
  "style_traits": ["direct", "structured", "low_hedging"],
  "forbidden_facts_removed": true,
  "third_party_removed": true,
  "source_item_version_ids": ["uuid"],
  "transformation": "human_written|human_rewritten|approved_synthetic",
  "rights_basis_version_id": "uuid",
  "reviewer_id": "uuid",
  "approved_at": "RFC3339"
}
```

### Preference pair schema

```json
{
  "pair_id": "uuid",
  "prompt_id": "uuid",
  "chosen": "...",
  "rejected": "...",
  "reason_codes": ["too_verbose", "weak_position", "wrong_formality"],
  "fact_equivalent": true,
  "both_safe": true,
  "owner_label": "A",
  "blind_repeat_group": "uuid|null",
  "model_versions": ["base-hash", "adapter-hash"],
  "source_rights_versions": ["uuid"]
}
```

Construction rules:

* Deduplicate exact and semantic near-duplicates before splitting. Kandpal et al. found regeneration risk grows superlinearly with duplicate count; deduplication reduces but does not eliminate exposure.
* Split holdouts by source document, topic, and time, not random chunks. Random chunk splitting leaks adjacent blog language into evaluation.
* Balance at least 20 intent clusters; cap any single post at 2% of training examples.
* Preserve a `semantic_content` representation so style scoring does not reward factual mutation.
* Prefer human-written or human-rewritten targets. Synthetic augmentation must be approved and labeled; it cannot silently become evidence of the person's real view.
* Exclude direct quotation targets unless quoting is the explicit authorized task. Run longest-common-substring and approximate-match extraction tests against every source.

## 5. Checkpoint isolation and deletion

```json
{
  "training_run_id": "uuid",
  "base_model_sha256": "...",
  "base_license": "...",
  "tokenizer_sha256": "...",
  "corpus_manifest_sha256": "...",
  "rights_manifest_sha256": "...",
  "train_code_commit": "...",
  "method": "lora|sft|dpo|cpt|distill",
  "adapter_config": {"rank": 16, "alpha": 32, "targets": ["q_proj", "v_proj"]},
  "random_seed": 42,
  "parent_checkpoint_ids": ["uuid"],
  "optimizer_artifact_ids": ["uuid"],
  "intermediate_checkpoint_ids": ["uuid"],
  "evaluation_report_sha256": "...",
  "merged": false
}
```

For one persona, never merge the adapter into the base model. Hugging Face PEFT at pinned commit [`6a832dec...`](https://github.com/huggingface/peft/blob/6a832dec2868b341fe5ba70f85b8121edc49ac69/src/peft/peft_model.py#L1170-L1181) implements adapter deletion; its [checkpoint guide](https://github.com/huggingface/peft/blob/6a832dec2868b341fe5ba70f85b8121edc49ac69/docs/source/developer_guides/checkpoint.md#L211-L218) states that `merge_and_unload` produces a basic model without PEFT-specific functionality. The operational implication is strong isolation, not proof of legal/statistical unlearning.

Deletion scope by method:

| Method | Required artifacts |
|---|---|
| Prompt/profile | profile versions, examples, prompt/output caches |
| RAG | source records, chunks, embeddings, sparse index, reranker cache, cited outputs |
| LoRA/DPO-LoRA | all above plus adapter, optimizer states, gradients if stored, intermediate/final checkpoints, evaluation extracts |
| Full SFT/CPT | all full checkpoints and derived releases; retire/retrain from an authorized snapshot unless validated exact unlearning exists |
| Distillation | teacher traces/logits, student training set, student checkpoints, plus underlying teacher artifacts |

Deleting an unmerged adapter cleanly removes that adapter from serving only if the base was never trained on the same corpus and no merged/exported copies remain. Approximate unlearning cannot replace artifact lineage and retirement/retraining fallback ([ICML 2023 counterevidence](https://proceedings.mlr.press/v202/chourasia23a.html)).

## 6. Evaluation suite

Use 200 frozen release prompts plus an untouched 50-prompt final audit:

| Lane | Count | Required measurements |
|---|---:|---|
| Explicit facts and quotations | 40 | Recall@k, source/citation correctness, atomic-claim faithfulness |
| Dated stances and supersession | 30 | correct temporal selection, contradiction reporting, obsolete-answer rate |
| Unseen-topic style transfer | 40 | owner pairwise preference, 1–5 style rubric, semantic preservation |
| Korean dialogue and multi-turn consistency | 30 | naturalness, honorific/register consistency, self-contradiction |
| Uncertainty/refusal/identity boundary | 20 | calibrated abstention, disclosure, no invented memories |
| Third-party/privacy/copyright leakage | 20 | canary extraction, overlap, unauthorized-name/details, jailbreak attempts |
| Long-context/retrieval stress | 20 | evidence-position robustness, missing-hop and conflicting-document behavior |

The additional 50 prompts remain sealed until a release candidate is selected.

Automated metrics are diagnostic, not a sole release decision:

* Retrieval: Recall@k, MRR, nDCG, time-filter accuracy.
* Grounding: atomic claim support, citation entailment/span correctness, contradiction rate. RAGAS provides a useful decomposition but uses model-based evaluation that requires calibration ([EACL 2024](https://aclanthology.org/2024.eacl-demo.16.pdf)).
* Persona: owner blind pairwise choice, style rubric, NLI consistency, and multi-turn stability.
* Stylometry: character n-grams, function-word/POS features, authorship verification, and distance from held-out real posts. Recent work recommends an ensemble because few-shot imitation remains inconsistent across ordinary authors ([EMNLP 2025](https://aclanthology.org/2025.findings-emnlp.532/)).
* Korean: native human review plus relevant tasks from [KoDialogBench](https://aclanthology.org/2024.lrec-main.865/); that benchmark tests Korean conversational competence, not individual-persona authenticity.
* Leakage: exact/approximate source overlap, prefix continuation extraction, membership/canary tests, and disclosure violations.

BLEU/ROUGE or one LLM-judge score cannot decide persona quality. Open-domain dialogue permits many correct responses, and common reference metrics may correlate poorly with human judgment ([dialogue-metric counterevidence](https://www.jstage.jst.go.jp/article/jnlp/30/2/30_531/_article)).

## 7. Cost model

Do not compare methods with provider-specific dollar prices. Use measured workload variables:

```text
prompt/profile monthly cost
  = requests * added_profile_tokens * input_token_price

RAG monthly cost
  = corpus_embedding_cost + vector_storage
  + requests * (retrieval + rerank + retrieved_tokens * input_token_price)

training release cost
  = curation_hours * labor_rate
  + labeling_hours * labor_rate
  + GPU_hours * GPU_rate
  + evaluation_runs * inference_cost
  + checkpoint_storage + deletion_drill + regression_maintenance

distillation break-even months
  = (teacher_trace_generation + student_training + QA)
    / (teacher_cost_per_request - student_cost_per_request) / monthly_requests
```

For a single blog, data construction, owner review, leakage testing, and regression evaluation usually dominate a short LoRA run. Distillation is justified only when the measured break-even fits the model's expected stable lifetime; frequent stance updates still stay in RAG.

Pinned implementation evidence:

* PEFT HEAD verified at `6a832dec2868b341fe5ba70f85b8121edc49ac69`; adapter load/delete and non-merged operation were inspected.
* TRL HEAD verified at [`197db06e...`](https://github.com/huggingface/trl/blob/197db06ec1f39aeded422867106c3dda9c79ee2d/trl/trainer/dpo_trainer.py#L409-L590); `DPOTrainer` has an explicit reference-model path. DPO therefore adds chosen/rejected and reference/policy scoring work relative to simple SFT, although exact memory and throughput depend on PEFT and reference-sharing configuration.

## 8. Positive and negative evidence

| Proposition | Positive evidence | Counterevidence / limit | Verdict |
|---|---|---|---|
| RAG supports mutable knowledge | Original RAG reports provenance/update motivation and strong knowledge-task results; EMNLP 2024 finds RAG beats unsupervised fine-tuning for old/new knowledge | Retrieval can miss evidence; long contexts can underuse middle evidence | Use RAG, but independently test retrieval and synthesis |
| Small curated SFT can change behavior | LIMA achieves strong alignment behavior from 1,000 curated examples | Different model/task; authors note robustness limits; does not prove factual update or a universal size | Use learning curves and project gates, not “1,000 is enough” |
| LoRA reduces adaptation cost | Frozen base and low-rank updates; QLoRA greatly reduces memory | Low-rank capacity and adapter serving overhead can matter; adapter can memorize | Preferred first training option, not a privacy mechanism |
| DPO simplifies preference training | Original DPO is stable and avoids a separate reward-model/RL loop | Later work reports likelihood displacement and weaker out-of-distribution reward generalization | Use only with consistent real pairs and separate regression tests |
| Continued pretraining can adapt domains/languages | Domain-adaptive pretraining improves downstream tasks | Catastrophic forgetting and raw-corpus diffusion; one blog is not a broad domain corpus | Reject for this use case |
| Distillation lowers inference cost | Student can approximate teacher at lower serving cost | Membership/memorization can transfer; teacher/student drift and deletion multiply | Only after workload break-even and full lineage |
| Fine-tuning can improve personal imitation | IMPersona reports trained impersonation exceeding prompting; style studies show prompt limitations | Safety risks and verbatim/copyright reactivation; style classifiers can confuse topic with author | Train only authorized behavior examples and keep factual grounding external |

The U.S. Copyright Office's [AI training report](https://www.copyright.gov/ai/Copyright-and-Artificial-Intelligence-Part-3-Generative-AI-Training-Report-Pre-Publication-Version.pdf) is comparative policy evidence, not Korean law. It reinforces that small creator-specific corpora and stylistic imitation need separate analysis. No technical method turns authorization into permission for unrelated third-party or pre-existing model content.

## 9. Distinct query log

1. `Retrieval-Augmented Generation knowledge-intensive NLP tasks Lewis 2020 provenance update factuality paper`
2. `persona prompting large language model profile prompt style consistency factual grounding paper`
3. `retrieval augmented generation counterevidence retrieval failure lost in the middle paper`
4. `Korean persona dialogue evaluation benchmark style consistency factual stance large language model`
5. `LoRA Low-Rank Adaptation paper parameter efficient fine tuning frozen base model rank memory primary`
6. `LIMA Less Is More for Alignment 1000 examples supervised fine tuning paper`
7. `Don't Stop Pretraining domain adaptive pretraining continued pretraining paper catastrophic forgetting`
8. `Direct Preference Optimization DPO paper preference tuning limitations overfitting distribution shift`
9. `extracting training data large language models memorization Carlini paper`
10. `deduplicating training data makes language models better memorization privacy paper Kandpal`
11. `fine-tuning language models memorization privacy leakage small dataset paper`
12. `knowledge distillation memorization privacy leakage large language model student model paper`
13. `QLoRA Efficient Finetuning of Quantized LLMs paper 24GB 65B memory NF4`
14. `site:github.com/huggingface/peft LoRA adapter checkpoint merge unload documentation`
15. `site:github.com/huggingface/trl DPOTrainer source reference model commit`
16. `machine unlearning LoRA adapter deletion exact unlearning fine-tuning data paper`
17. `continued pretraining catastrophic forgetting language models domain adaptation empirical paper`
18. `Direct Preference Optimization Your Language Model is Secretly a Reward Model NeurIPS 2023 primary paper`
19. `site:copyright.gov artificial intelligence report training data memorization outputs copyrighted works 2025`
20. `site:copyright.or.kr 생성형 AI 학습데이터 저작권 블로그 2025`
21. `RAG versus fine tuning factual knowledge updates benchmark paper comparison`
22. `LoRA Low-Rank Adaptation of Large Language Models ICLR 2022 OpenReview`
23. `persona dialogue dataset construction style behavior supervised fine tuning human evaluation paper`
24. `large language model style imitation memorization copyrighted text verbatim leakage fine tuning paper`
25. `dialogue generation automatic metrics poor correlation human judgments BLEU persona consistency paper`
26. `RAG evaluation retrieval recall faithfulness citation correctness benchmark paper RAGAS`
27. `authorship style imitation evaluation classifier stylometry large language model persona paper`
28. `Korean language model evaluation human style factual consistency benchmark primary paper`

## Risks

* Authorization of one person's blog does not authorize third-party text, comments, correspondence, media, or facts about others.
* One-person imitation can create impersonation and disclosure risks even when technically accurate; identity boundaries and channel restrictions remain outside training quality.
* An adapter is separable but not automatically unlearned, anonymous, non-infringing, or safe.
* Merging adapters, mixing people in one checkpoint, or training the base destroys the strongest deletion/isolation advantage.
* Synthetic examples can introduce positions the person never held. They require approval and provenance.
* A high stylometry score may reward topic copying rather than style. Evaluate unseen topics and semantic preservation.
* A high persona score must never compensate for factual, privacy, safety, or deletion failure.

## EXPAND

LEAD: Benchmark the selected Korean base model with the 200+50 suite before creating any training corpus beyond the prompt/RAG baseline.  
WHY: The evidence supports an escalation process, not a model-independent prediction that training is needed.  
ANGLE: Measure baseline failures by lane, confidence interval, latency, and cost; train only against persistent behavior failures.

LEAD: Run an adapter retirement drill before approving LoRA.  
WHY: Operational isolation is the principal reason to prefer LoRA over full SFT for one person.  
ANGLE: Prove the adapter never merged, locate every checkpoint/optimizer/export, delete it, restart serving, and confirm base-only behavior and source extraction tests.

LEAD: Have the authorized person label a small blinded pilot before committing to DPO.  
WHY: Noisy or inconsistent pairwise labels create distribution-shift and preference-overfitting risk.  
ANGLE: Use 50 prompts with repeated A/B ordering to estimate self-consistency and the likely cost of reaching the 500-pair gate.

## CLAIMS

CLAIM: Mutable persona facts and dated stances should remain in a versioned RAG/profile layer rather than being encoded primarily through fine-tuning.  
STATUS: Supported by primary RAG work and controlled RAG-vs-fine-tuning evidence; production recommendation, not a universal theorem.  
RISK: Retrieval and evidence use can still fail, so Recall@k, citation correctness, and faithfulness require separate gates.  
SOURCES: NeurIPS 2020 RAG; EMNLP 2024 knowledge-injection comparison; Lost in the Middle.  
COUNTER: Fine-tuning can incorporate some knowledge when facts are repeated in many variations, but controlled work still found RAG consistently stronger.  
PRIMARY: https://papers.nips.cc/paper_files/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html

CLAIM: No model training is justified when prompt/profile plus RAG meets grounding, behavior, safety, deletion, latency, and cost gates.  
STATUS: Decision rule synthesized from evidence; numeric thresholds are explicit internal policy proposals.  
RISK: Treating any threshold as universal would be unsupported; recalibrate on the chosen base and risk profile.  
SOURCES: RAG, LIMA, individual-style imitation research, RAGAS, KoDialogBench.  
COUNTER: Training can outperform prompting for some individual imitation tasks, but that only supports escalation after measured baseline failure.  
PRIMARY: https://aclanthology.org/2025.findings-emnlp.532/

CLAIM: When behavior training is necessary, an unmerged one-person LoRA/QLoRA adapter is the preferred first escalation because it reduces trainable state and preserves a retireable boundary.  
STATUS: Supported by LoRA/QLoRA papers and verified PEFT implementation; deletion advantage is conditional.  
RISK: Adapter deletion is insufficient if the base, merged copies, optimizer states, traces, caches, or exports contain corpus influence.  
SOURCES: ICLR 2022 LoRA; NeurIPS 2023 QLoRA; PEFT pinned commit `6a832dec...`.  
COUNTER: Full SFT may outperform low-rank adaptation on some broad behavior shifts; require a measured ≥5-point gap before accepting its larger deletion cost.  
PRIMARY: https://openreview.net/forum?id=nZeVKeeFYf9

CLAIM: Continued pretraining is not justified for a single person's blog persona.  
STATUS: Strong method-fit conclusion.  
RISK: It diffuses raw text into a full checkpoint, complicates deletion, and can cause forgetting without solving citation or temporal-update requirements.  
SOURCES: Don't Stop Pretraining; continual domain-tuning and language-adaptation counterevidence.  
COUNTER: Continued pretraining is effective for sufficiently broad domain/language adaptation; that is a different objective and corpus.  
PRIMARY: https://arxiv.org/abs/2004.10964

CLAIM: DPO and distillation are downstream optimizations, not substitutes for grounded knowledge or clean deletion.  
STATUS: Supported by primary method papers and independent counterevidence.  
RISK: DPO has distribution-shift/overoptimization failure modes; distillation can transfer teacher memorization to the student.  
SOURCES: NeurIPS 2023 DPO; EMNLP 2024 DPO generalization; EMNLP 2025 distillation privacy; NeurIPS 2021 teacher leakage.  
COUNTER: DPO can simplify preference alignment and distillation can materially lower serving cost when their data and workload gates are satisfied.  
PRIMARY: https://proceedings.neurips.cc/paper_files/paper/2023/hash/a85b405ed65c6477a4fe8302b5e06ce7-Abstract-Conference.html
