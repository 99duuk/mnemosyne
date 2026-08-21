# Wave 2 - Training Method Decision

Observer: `/root/identity_ethics_r2` on bounded training-method follow-up  
Observed at: 2026-07-13  
Full artifact: `.omo/teams/team-9c661443/artifacts/training-methods-r2.md`

## Decision

Use two independent planes:

- Mutable truth plane: versioned profile + RAG for facts, dated stances, citations and deletion.
- Behavior plane: prompt contract first, then an optional unmerged one-person LoRA, and only then optional preference tuning.

The production default is no training. Training is prohibited when the failure is retrieval, stale/conflicting facts, citations, rights/deletion filters, base Korean capability, injection, latency or cost. Fix that subsystem.

## Method matrix conclusion

- Static prompt/profile: always first for identity boundary and explicit style rules; exclude changing facts.
- RAG: default facts/stance/citation layer; independently verify retrieval and synthesis.
- LoRA/QLoRA: first training escalation for repeatable residual style/behavior failure; never merge the per-person adapter.
- Full SFT: generally rejected; only consider if a measured broad behavior requirement beats LoRA enough to justify deletion cost.
- Continued pretraining: wrong method for one blog; raw diffusion, forgetting and no citation/update solution.
- DPO: only after stable adapter behavior and consistent real chosen/rejected labels.
- Distillation: only after a stable teacher and demonstrated serving-cost break-even; student keeps RAG and separate deletion lineage.

## Escalation gate

Train only after prompt/profile+RAG passes factual, citation, temporal, privacy, identity and deletion gates and a repeated behavior gap remains across at least five intent clusters. The artifact proposes a 500 unique approved example release-policy gate for LoRA/SFT and 500 preference pairs for DPO; these are project policies, not universal research thresholds. Pilot learning curves may begin earlier but cannot define release.

LoRA must show blinded owner-preference improvement with confidence interval excluding zero and no material factual/safety/Korean/leakage regression. Deletion/adapter isolation must pass before approval.

## Data construction and deletion

- Convert eligible prose into reviewed prompt-response behavior examples; do not next-token train over the raw blog.
- Split by source document, topic and time; deduplicate before split; cap domination by any one post.
- Remove facts/third-party content from style examples and preserve provenance to source rights versions.
- Record base/tokenizer/corpus/rights/code/config/seed/optimizer/checkpoint/evaluation hashes.
- Adapter deletion only helps when the base was never trained on the corpus and no merged copies, intermediate checkpoints or exports remain.

## Sources

- Original RAG: https://papers.nips.cc/paper_files/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html
- RAG versus fine-tuning: https://aclanthology.org/2024.emnlp-main.15.pdf
- LIMA: https://papers.nips.cc/paper/2023/file/ac662d74829e4407ce1d126477f4a03a-Paper-Conference.pdf
- LoRA: https://openreview.net/forum?id=nZeVKeeFYf9
- QLoRA: https://arxiv.org/abs/2305.14314
- DPO: https://proceedings.neurips.cc/paper_files/paper/2023/hash/a85b405ed65c6477a4fe8302b5e06ce7-Abstract-Conference.html
- Fine-tuning memorization: https://aclanthology.org/2024.acl-long.216.pdf
- Deduplication/memorization: https://proceedings.mlr.press/v162/kandpal22a.html

## EXPAND

- LEAD: Benchmark the chosen Korean base on the frozen suite before creating training data - WHY: evidence supports escalation, not a model-independent need to train - ANGLE: lane-level failure, CI, latency and cost.
- LEAD: Execute adapter retirement drill - WHY: operational separability is LoRA's key advantage - ANGLE: locate/delete every adapter/checkpoint/state/export and verify base-only behavior.
- LEAD: Small blinded preference pilot before DPO - WHY: owner label inconsistency creates overfitting risk - ANGLE: repeated A/B ordering and self-consistency.
- DEAD END: continued pretraining as a one-blog persona solution.
- DEAD END: fine-tuning as a repair for missing evidence, stale facts or rights filtering.

## CLAIMS

- C49: Mutable facts and dated stances belong in RAG/profile, not primarily in weights.
- C50: No training is justified when prompt/profile+RAG passes all release gates.
- C51: An unmerged one-person LoRA is the preferred first training escalation when a measured residual behavior gap remains.
- C52: Continued pretraining is not justified for one blog persona.
- C53: DPO and distillation are downstream optimizations, not grounding or deletion mechanisms.
