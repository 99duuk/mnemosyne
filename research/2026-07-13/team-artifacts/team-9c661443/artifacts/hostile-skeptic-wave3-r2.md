# Wave 3 Hostile-Skeptic Review

Research cutoff: 2026-07-13. Scope: root research ledger plus all six team artifacts present at review time (the task mentioned four, but the directory contained collection, governance, evaluation, Korean-law, RAG, and training artifacts).

## Executive verdict

The evidence supports a **private, source-attributed, RAG-first analyst prototype** under verified acquisition authority. It does **not** yet clear a public named first-person persona, an unqualified “complete corpus” claim, or a production deletion/unlearning guarantee.

The strongest process blocker is fatal to synthesis wording: `claim-graph.md` has an empty `## Verified Claims` allowlist. Every current claim remains `partial` or otherwise unpromoted. Under the research protocol, high-risk conclusions cannot be described as locked, proven, or verified until they are explicitly promoted, or the final synthesis must label them provisional.

## Fatal blockers before synthesis

| ID | Blocker | Why fatal | Exact required correction |
|---|---|---|---|
| P0-1 | Empty verified-claims allowlist | The research protocol allows high-risk assertions only from promoted verified claims; presently there are none. | Add a claim verdict table and promote only claims meeting the evidence rule, counter-search, date check, and primary-source requirement. Otherwise say “provisional design recommendation,” not “verified conclusion.” |
| P0-2 | First-person semantic-preservation claim | “The author wrote X in 2023” → “I believe X” changes speaker, agency, temporal force, and current endorsement. Automated NLI cannot prove equivalence, especially for Korean hedging, sarcasm, or negation. | Keep public output in source-attributed third person. If first-person is retained, use explicitly archival/fictional wording and require specific living-subject authorization plus human review for high-risk assertions. Remove the claim that it is a semantics-neutral style transform. |
| P0-3 | Historical statement treated as current belief | An open-ended `valid_to` encodes database silence, not continued belief. Latest observed blog text does not prove present stance. | Replace `current` with `historically_asserted_at`, `explicitly_reaffirmed_until`, and `unknown_current`. Answer: “Latest observed statement was X on date Y; current view is unknown” unless there is a recent explicit reaffirmation or authorized validity rule. |
| P0-4 | Completeness overclaim | Owner signature and a Merkle root prove attestation/fixity of the submitted set, not that all historical, deleted, private, revised, media, or omitted items were supplied. PDF is known to be lossy. | Rename `COMPLETE` to `COMPLETE_RELATIVE_TO_OWNER_DECLARED_SCOPE_AT_CUTOFF`; disclose excluded/unverifiable history and asset/semantic-fidelity dimensions separately. Never say “complete corpus” without an independent authoritative denominator. |
| P0-5 | Deletion guarantee is unexecuted and restore rules conflict | Governance requires tombstones before restore and deleted bytes to be absent/inaccessible, while collection test 12 expects raw artifacts plus DB backup to reproduce the same hashes and completeness root. | Restore only the active authorized snapshot after replaying tombstones/revocations. Deleted raw artifacts must be absent or cryptographically inaccessible. Preserve only content-free historical roots. Run the end-to-end deletion, processor, backup-restore, and adapter-retirement drills before claiming deletion effectiveness. |
| P0-6 | Statistical gate cannot be met with stated sample guidance | With 100/100 successes, a one-sided exact 95% lower bound is about 0.9705, below the 0.98 support gate. Zero failures in 100 attacks still permits an upper bound of about 2.95%. | Pre-register power/sample size per metric. At least 149/149 independent successes are needed for a one-sided lower 95% bound at 0.98. Roughly 299–300 zero-failure trials are needed to bound failure below 1%; use cluster-aware models for correlated prompt variants. |

## Major constraints and overclaims

1. **robots.txt is not legal authorization.** RFC 9309 expressly says robots rules are not access authorization. Treat NAVER robots as an operational deny/preference signal; ground contractual restrictions in the Terms. Written approval remains the correct conservative acquisition gate, but not because robots alone makes access unlawful.
2. **Owner export is an acquisition mechanism, not a downstream rights grant.** Owner-operated PDF backup does not clear third-party expression, personal data, comments/media, platform terms, or public persona use.
3. **Disclosure is necessary but insufficient.** AI labeling does not itself prevent anthropomorphism or identity confusion. Require comprehension testing, persistent channel markers, non-anthropomorphic UX, and no claim that disclosure grants authority.
4. **Unlearning tests do not prove erasure.** MUSE/OpenUnlearning show multi-dimensional and inconsistent forgetting results. Canary non-extraction does not prove natural text was not memorized, and weak membership-inference performance does not prove privacy.
5. **LoRA isolation is release-level, not item-level deletion.** Revoking one source generally requires rebuilding or retiring the whole affected adapter and deleting optimizer, intermediate, merged, and derived copies.
6. **Numeric thresholds are provisional policy.** `500` examples/pairs, `20` clusters, `50` characters, `0.95/0.98`, `10%`, and `80%` are not universal scientific or legal constants. Retain only as predeclared starting policies with power, sensitivity, learning-curve, and cost calibration.
7. **Fifty characters is not a copyright boundary.** It can miss short distinctive expression, selection/arrangement, and close paraphrase. Use it only as an automated trigger; route distinctive passages to manual/legal review.
8. **No autonomous agency is a sound MVP policy, not a universal truth.** State it as the initial release boundary. Later read-only or low-risk autonomy requires scoped authorization, identity/authentication controls, transaction limits, audit, rollback, and risk-tiered human approval.
9. **Legal applicability remains fact-specific.** AI Basic Act duties depend on whether the deployment/operator falls within statutory scope. PIPA legal basis and personality/identity authorization are separate. Model retirement is a conservative technical control, not a categorical statutory command in every deployment.
10. **Research-group independence is overstated.** Multiple agents often reused overlapping papers and artifacts. Count independent source domains, not agent count, when satisfying the evidence rule.

## Cross-artifact contradictions

| Contradiction | Required reconciliation |
|---|---|
| “Immutable raw artifacts” vs physical deletion/non-restorability | Define immutable as append-only/version-preserving **while authorized and retained**, not undeletable. Deletion must erase bytes/keys according to policy while content-free provenance remains. |
| Restore exact normalized hashes/root vs tombstone-first restore | Restore only currently authorized rows; compare active-snapshot hashes/root. A historical content-free root may remain, but deleted content must not reappear merely to reproduce it. |
| `COMPLETE` vs lossy PDF and unverifiable omissions | Scope completeness to the signed owner-declared inventory and cutoff; keep inventory, asset, semantic-component, revision, and freshness dimensions separate. |
| First-person “style only” vs changed speaker/current endorsement | Remove the equivalence claim; public mode stays third-person and dated. Authorized simulation must remain explicitly fictional/archival and separately evaluated. |
| Fixed gates vs statement that no universal thresholds exist | Mark all numbers as provisional internal policies and show power/sensitivity calculations before use as release evidence. |
| No agency as architecture invariant vs future bounded tools | Make no-write/no-communication the MVP release profile, then define a risk-tiered promotion path rather than a timeless prohibition. |

## Claim-by-claim verdict and required correction

Verdicts: **S** supported with stated scope; **P** partial/provisional; **R** refuted as worded; **U** unresolved pending evidence.

| Claim | Verdict | Required correction before synthesis |
|---|---:|---|
| C1 | S | Say reachability is not permission; identify Terms/privacy/copyright bases separately from robots. |
| C2 | S | Keep as a documented API-contract limit; do not infer what private licensed interfaces may offer. |
| C3 | P | Replace “authorized route” with “owner-operated supported acquisition mechanism”; downstream rights remain separate. |
| C4 | U | RSS availability proves a feed surface only. Written platform clarification remains required for persistent AI ingestion. |
| C5 | P | Condition disclosure duty on operator/service statutory scope; say disclosure is necessary but does not prevent confusion or grant rights. |
| C6 | S | Preserve public-interest, biography, satire, and scholarship exceptions; named novel first-person speech remains a distinct high-risk use. |
| C7 | P | Present granular consent as the safest identity authorization, not the only possible PIPA processing basis. |
| C8 | P | State as conservative release policy, not categorical law; allow fact-specific documentary/public-interest exceptions after review. |
| C9 | P | Replace “removed” with a verified retirement/rebuild/unlearning decision; no current test proves identity effects are absent. |
| C10 | S | Ground in current/prior NAVER Terms and exact access pattern; do not use robots as legal authorization evidence. |
| C11 | U | Keep disabled pending channel-specific written clarification; do not convert uncertainty into categorical illegality. |
| C12 | S | Preserve discovery/witness exception only within approved registered scope; no transfer of result-data rights. |
| C13 | S | Add “relative to selected PDF scope”; no complete-preservation inference. |
| C14 | S | Keep four independent gates and evaluate at block/item level. |
| C15 | S | Keep fact-specific Article 35-5 analysis; neither safe harbor nor categorical prohibition. |
| C16 | S | Say a lawful basis may include objective-purpose compatibility or another statutory basis; public status alone is insufficient. |
| C17 | S | Explicitly separate unprotected abstract style from copied expression, false attribution, and personality interests. |
| C18 | S | Keep target linkage and sensitive-data gate; pseudonymization may still protect unrelated third parties. |
| C19 | S | Condition duty on statutory applicability; disclosure never supplies input or identity authority. |
| C20 | S | Use “source-grounded authored-behavior proxy,” never “digital twin of internal thinking.” |
| C21 | S | Require longitudinal, held-out behavior tests; fluency/style scores remain auxiliary. |
| C22 | S | Phrase RAG-first as a reversible default policy, not a theorem that training cannot improve style/behavior. |
| C23 | S | Keep separated dimensions and rolling time splits; target Korean gold data remains pending. |
| C24 | S | Human-calibrate Korean support labels; automatic NLI/LLM judgment remains triage, not proof. |
| C25 | S | Keep distinct gates; all numeric thresholds require power/sensitivity justification. |
| C26 | P | Owner export is non-bypass acquisition only; signed inventory proves attestation, not global completeness or rights clearance. |
| C27 | R | Replace “complete-corpus claim” with `complete relative to owner-declared in-scope inventory at cutoff`; fixity is not completeness. |
| C28 | S | Keep owner change-ledger default while acknowledging a future licensed endpoint could change the decision. |
| C29 | S | Keep quarantine; permit evidence-backed item-level clearance. |
| C30 | P | Fail closed is a conservative policy. Written approval resolves contract scope; robots alone does not. |
| C31 | S | Maintain deterministic privilege separation and run target injection/exfiltration tests; detection is not a boundary. |
| C32 | S | Enforce filters before retrieval and retain post-generation validation as defense in depth. |
| C33 | S | Keep both benefit and added poisoning/leakage/injection surfaces; target evidence is still unexecuted. |
| C34 | S | Add that canaries and MIAs are incomplete evidence; retirement/retraining is the reliable fallback. |
| C35 | P | Recast as MVP release policy. Later bounded autonomy needs scoped authorization and transaction controls. |
| C36 | S | Preserve binding-law/guidance/engineering labels and deployment-specific applicability. |
| C37 | P | Correct systems invariant, but do not claim operational compliance until saga, processor, restore, and failure-retry drills pass. |
| C38 | P | Replace “prevent” with “designed to prevent and verified by restore drill”; minimize tombstone linkability. |
| C39 | S | Evidence form is contractual/technical; API 200 alone is insufficient. |
| C40 | S | Keep approximate unlearning as insufficient proof; exact retraining or target-validated methods remain possible. |
| C41 | S | Preserve “improves but does not guarantee”; target harness is required. |
| C42 | P | Pre-ranking temporal eligibility is necessary, but absence of `valid_to` cannot establish present belief. Add `unknown_current`. |
| C43 | S | Keep target ablation; do not promote a Korean model from benchmark marketing alone. |
| C44 | S | Keep atomic support and separate correctness/completeness; sensitive claims require human adjudication. |
| C45 | R | A first-person rewrite necessarily changes speaker semantics. Public mode must remain dated third-person; authorized role-play needs explicit fictional/archival framing. |
| C46 | S | Keep smallest-stack rule as measured operational policy; scale only from media/QPS/latency evidence. |
| C47 | S | Report formula and measured per-query costs; vendor-independent values remain pending. |
| C48 | S | Keep staged promotion; private self-owned prototype is the lower-risk branch. |
| C49 | P | Store historical assertions and mutable facts in RAG/profile, but do not infer “current stance” without reaffirmation. |
| C50 | P | Keep as a cost/risk decision rule, not scientific proof that training has no residual value. |
| C51 | P | Keep unmerged LoRA as first escalation only after benchmark and retirement drill; revoke one item by rebuilding/retiring the affected adapter. |
| C52 | S | Keep for the stated single-blog objective; broad domain/language adaptation is the explicit countercase. |
| C53 | S | Keep DPO/distillation downstream; they do not provide grounding or clean deletion. |
| C54 | S | Keep rolling, dependency-grouped temporal split; separately measure pre-sync missing-source behavior. |
| C55 | P | Correct principle, but final sample size and clustered dependence must be power-calibrated; “100 where feasible” is insufficient for the 0.98 bound. |
| C56 | S | Keep hard protected-axis non-inferiority; style cannot average away rights/safety failure. |
| C57 | S | Add numeric interpretation: 0/100 failures still has about a 2.95% one-sided 95% upper bound. |

## Exact text replacements

1. Replace `COMPLETE` with `COMPLETE_RELATIVE_TO_OWNER_DECLARED_SCOPE_AT_CUTOFF` and define the denominator as the owner-signed inventory version. Add: “This status does not establish that deleted, private, historically omitted, or never-declared items are absent.”
2. Replace RAG `current` semantics with: “A source can establish only the latest observed assertion. `current` is returned only after explicit reaffirmation within a declared freshness window; otherwise return `unknown_current` and the date of the latest observation.”
3. Replace “first-person style transformation adds no semantic claim” with: “First-person rendering is a separately authorized identity act and is not presumed semantically equivalent to source-attributed analysis.”
4. Replace restore test 12 with: “After replaying tombstones and rights revocations, restore reproduces the active authorized snapshot hashes/root; deleted content remains absent or cryptographically inaccessible.”
5. Add to immutable-layer definitions: “Immutable means append-only while retained; it does not override erasure, retention expiry, key destruction, or rights revocation.”
6. Add to every numeric release gate: “Provisional internal threshold; final `n`, margin, and interval method are pre-registered from power analysis and cluster dependence.”
7. Replace “robots prohibits/authorizes” with: “robots is an operational machine-readable preference/deny signal and is honored; contractual authorization is assessed separately under platform Terms and written approval.”

## Fresh counter-search log

Twenty-four independent counter-search lanes were run: RFC robots authorization; AI Basic Act Article 31/decree; PIPC public-data legitimate interest; Korean copyright AI fair use; temporal RAG/current belief; Korean NLI semantic preservation; multilingual/Korean LLM judges; zero-failure sample size; persona temporal benchmarks; RAG temporal conflicts; style-transfer content preservation; Korean NLI limits; machine-unlearning benchmarks; LoRA item deletion; MIA reliability; canary non-extraction; disclosure/anthropomorphism; real-person impersonation/social engineering; Korean personality-right counterexamples; NIST autonomous agents; fixity versus completeness; signed-manifest completeness; PDF extraction limits; web-archive completeness.

Key counter-evidence: [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html); [AI Basic Act Article 31](https://www.law.go.kr/LSW/lsSideInfoP.do?docCls=jo&joBrNo=00&joNo=0031&lsiSeq=282791&urlMode=lsScJoRltInfoR); [MUSE](https://research.google/pubs/muse-machine-unlearning-six-way-evaluation-for-language-models/); [OpenUnlearning](https://arxiv.org/abs/2506.12618); [Do Membership Inference Attacks Work?](https://arxiv.org/abs/2402.07841); [LLM judge position bias](https://aclanthology.org/2025.ijcnlp-long.18/); [style-transfer content preservation failure](https://aclanthology.org/N19-1049/); [persistent-persona degradation](https://aclanthology.org/2026.eacl-long.246.pdf); [AI disclosure/anthropomorphism study](https://link.springer.com/article/10.1007/s00146-023-01818-7); [NIST AI Agent Standards Initiative](https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative); [PDF parser benchmark](https://arxiv.org/abs/2303.09957); [DPC fixity guidance](https://www.dpconline.org/handbook/technical-solutions-and-tools/fixity-and-checksums); [web-archive completeness study](https://link.springer.com/article/10.1007/s00799-015-0153-3).

## EXPAND

LEAD: Run a target Korean golden-set calibration with prospective sample-size planning.  
WHY: Current 0.95/0.98 gates cannot be interpreted from “100 where feasible,” and correlated variants violate independent-binomial assumptions.  
ANGLE: Pre-register strata, cluster unit, exact/mixed interval method, failure budget, and minimum detectable regression.

LEAD: Run one destructive deletion/restore/adapter-retirement drill.  
WHY: Design documents conflict on immutable raw recovery versus non-restorability, and no end-to-end evidence exists.  
ANGLE: Revoke one source, trace every descendant and processor, restore backup with tombstones, then prove the source cannot serve or re-enter a rebuilt adapter.

LEAD: Obtain written NAVER clarification for RSS/persistent owner-authorized ingestion.  
WHY: Current official materials establish a feed surface and automation restrictions but do not resolve this exact use.  
ANGLE: Submit exact endpoints, cadence, storage duration, registered application, owner authorization, and AI/RAG purpose.

LEAD: Validate identity comprehension rather than disclosure presence alone.  
WHY: Persistent labels can coexist with anthropomorphism and mistaken belief that the system is the real person.  
ANGLE: Test unseen Korean users across new/resumed/shared/API contexts for source, agency, endorsement, and current-belief understanding.

## CLAIMS

CLAIM: The current evidence clears only a private, source-attributed, RAG-first analyst prototype, not a public named first-person persona.  
STATUS: Supported as a conservative release decision; public authorization and target identity-confusion evidence remain absent.  
RISK: High.  
SOURCES: Korean law artifact; identity/persona research; disclosure counter-study.  
COUNTER: Authorized fictional role-play can be lawful and useful on specific facts.  
PRIMARY: AI Basic Act, PIPA/case-law sources, peer-reviewed persona studies.

CLAIM: The synthesis currently has no protocol-compliant verified-claim allowlist.  
STATUS: Confirmed by direct inspection of `claim-graph.md`; `## Verified Claims` is empty.  
RISK: Fatal to any “verified/locked/proven” wording.  
SOURCES: Root claim graph and ulw-research evidence protocol.  
COUNTER: Individual artifacts contain strong evidence, but it has not been promoted through the required ledger step.  
PRIMARY: Research-session artifacts.

CLAIM: Owner-signed inventory plus PDF and Merkle fixity can prove completeness only relative to the declared scope and cutoff.  
STATUS: Supported; the unqualified complete-corpus claim is refuted.  
RISK: High.  
SOURCES: NAVER PDF limitations, DPC fixity guidance, PDF and web-archive completeness research.  
COUNTER: An authoritative platform export or independently verified account denominator could strengthen the claim.  
PRIMARY: NAVER Help and preservation research.

CLAIM: A dated third-person assertion cannot be transformed into present first-person belief without adding identity and temporal semantics.  
STATUS: Supported by semantic analysis and style-transfer/persona counter-evidence; C45 is refuted as worded.  
RISK: High.  
SOURCES: Source architecture, style-transfer research, Korean/NLI limitations, identity law.  
COUNTER: Explicitly fictional or archival first-person quotation is possible with authorization and disclosure.  
PRIMARY: Peer-reviewed research and binding identity-law sources.

CLAIM: Current deletion guarantees are architecture proposals, not verified operational facts.  
STATUS: Confirmed; root ledger records the deletion drill as pending and artifacts conflict on restore semantics.  
RISK: High.  
SOURCES: Governance, collection, training artifacts; MUSE/OpenUnlearning/MIA counter-evidence.  
COUNTER: A passed end-to-end drill can promote bounded operational claims.  
PRIMARY: Direct artifact inspection and peer-reviewed/primary research.
