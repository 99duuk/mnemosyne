# Wave 2 - Independent Evaluation Harness Review

Observer: `/root/collection_engineering_r2` on bounded evaluation follow-up  
Observed at: 2026-07-13  
Full artifact: `.omo/teams/team-9c661443/artifacts/evaluation-harness-r2.md`

## Outcome

The independent design confirmed the multi-gate approach and found one blocking contradiction in the root spec: held-out evidence was excluded from retrieval while retrieval recall was measured against it. The corrected protocol excludes future sources from adapter/profile construction but includes all legitimately query-time-available documents in the signed as-of retrieval snapshot; questions and labels remain sealed.

The root spec was corrected immediately.

## Material corrections accepted

- Rolling-origin dependency-component folds replace a single percentage split.
- “Reasoning choice” becomes source-documented rationale/decision; latent thought is never gold.
- Gates apply to cluster-bootstrap confidence bounds, not point estimates.
- Candidate recall, ranking precision/nDCG, claim support, citation completeness, speaker and time validity are separate.
- Exact quotes are one contiguous NFC source substring with ID, offsets and hash; composite quotes are prohibited.
- Stance uses adjudicated macro-F1 and transition tests; annotator agreement is separately reported.
- Abstention is paired with answerable-refusal rate and risk-coverage.
- Canary extraction is a hard test; membership inference remains a distribution-sensitive diagnostic.
- Final hard-gate sets receive complete human gold labeling. LLM judges only triage after calibration.
- Prompt injection, persistent disclosure comprehension, sequential revocation and adapter rebuild have explicit calculations/gates.
- A simpler RAG arm is not an automatically safe fallback; it must pass every applicable gate.
- No weighted overall score can average away a privacy, identity, deletion, quote or agency failure.

## Sources

- HELM multi-metric evaluation: https://arxiv.org/abs/2211.09110
- Data deduplication: https://aclanthology.org/2022.acl-long.577/
- BEIR retrieval metrics: https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/hash/65b9eea6e1cc6bb9f0cd2a47751a186f-Abstract-round2.html
- ALCE: https://aclanthology.org/2023.emnlp-main.398/
- Training data extraction: https://www.usenix.org/system/files/sec21-carlini-extracting.pdf
- AgentDojo: https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html
- MUSE: https://arxiv.org/abs/2407.06460

## EXPAND

- LEAD: Korean pilot annotation for duplicate, stance and entailment rubrics - WHY: English thresholds do not transfer automatically - ANGLE: development-only calibration.
- LEAD: Pre-register sample counts, attack budgets, latency and revocation SLO - WHY: zero observed failures has meaning only relative to exposure - ANGLE: signed test manifest.
- DEAD END: one aggregate persona score is a valid release decision.
- DEAD END: lower-complexity RAG automatically passes safety when an adapter fails.

## CLAIMS

- C54: The split unit is a time-bounded dependency component; query-time retrieval may use all legitimately as-of available evidence while future data remains excluded from profile/adapter construction.
- C55: Hard release gates use confidence bounds and complete human gold labels, not point estimates or a 10% spot check.
- C56: No style/persona gain compensates for factual, privacy, identity, revocation or agency regression.
- C57: Adversarial zero-failure results are bounded evidence for a declared attack budget, not proof of zero risk.
