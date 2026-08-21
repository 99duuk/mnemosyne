# Wave 1 - RAG, Memorization, and Impersonation Security

Observer: `root`  
Observed at: 2026-07-13  
Method: OWASP primary guidance, NIST guidance and machine-unlearning counterevidence.

## Threat model and controls

| Threat | Prevent | Detect | Recover |
|---|---|---|---|
| Indirect prompt injection in posts | treat corpus as untrusted data; strip hidden/active markup; immutable source instruction boundary; no target tools | injection classifier plus canary corpus and output policy | quarantine item; rebuild affected index/profile |
| Corpus poisoning/revision takeover | signed owner delivery, hashes, revision lineage, rights gate and manual review | unexpected source/hash/embedding-distribution alerts | roll back eligible view; tombstone poisoned revision |
| Cross-item/privacy exfiltration | per-subject/tenant access filters before vector search; least-privilege read-only store; no sensitive blocks | red-team extraction, canaries, access/audit logs | revoke access; remove chunks/cache; incident notice |
| Fabricated quote/attribution | exact span matcher; synthesis never placed in quotation marks | zero-tolerance quote test and citation validator | block output; suspend public endpoint and correct |
| Memorization from fine-tuning | RAG-first; no raw long-span SFT; separable adapters; dedup and rare-span tests | extraction and membership-inference suite | retire checkpoint if removal cannot be proven |
| Identity escalation/excessive agency | no credentials or external tools; draft/read-only behavior; current human approval under own identity | attempted-action telemetry | disable capability and rotate affected credentials |
| Disclosure bypass | persistent AI/not-the-person header and export metadata | representative-user comprehension test | downgrade first-person mode to attributed L1 |
| Deleted/private content resurrection | active lifecycle filter before retrieval; non-content tombstone | revocation prompts and index enumeration | rebuild index/profile/cache; retire adapter/checkpoint |

## Findings

1. OWASP identifies the shared natural-language channel for instructions and data as the prompt-injection root condition. A retrieved blog post can contain active-looking instructions and must never gain policy authority.
2. RAG moves risk into ingestion, vector storage, retrieval and downstream integration. Access control must be enforced before retrieval, not delegated to a generation prompt.
3. Vector/embedding weaknesses include poisoning and sensitive-data leakage. Embeddings are derived personal-data artifacts in this architecture and inherit subject, consent, lifecycle and deletion filters.
4. Excessive agency is unnecessary for this use case and creates a separate high-impact vulnerability. A persona system should have no autonomous external-action capability.
5. Machine unlearning is not a reliable deletion promise. MUSE reports that evaluated methods trade off memorization, privacy leakage, utility and repeated deletion sustainability. Separable RAG plus checkpoint retirement is more auditable.

## Sources

- OWASP Prompt Injection Prevention: https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html
- OWASP RAG Security: https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html
- OWASP Vector and Embedding Weaknesses: https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/
- OWASP Excessive Agency: https://genai.owasp.org/llmrisk/llm062025-excessive-agency/
- OWASP LLM Verification Standard: https://owasp.org/www-project-llm-verification-standard/LLMSVS-v2.0-en.html
- MUSE unlearning evaluation: https://arxiv.org/abs/2407.06460
- Machine unlearning survey: https://arxiv.org/abs/2404.01206
- NIST AI 600-1: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence

## Contradictions and resolution

- Counter: RAG reduces hallucination. Resolution: grounding can help, but retrieved content introduces poisoning, access and indirect-injection surfaces; response support still needs validation.
- Counter: unlearning algorithms delete a person's influence. Resolution: current evaluations expose privacy, utility and repeated-request limitations; do not promise deletion from weights without target-specific proof.
- Counter: tools make the clone useful. Resolution: the requested value is analysis/conversation. External agency is unnecessary and creates false-identity and security risk.

## EXPAND

- LEAD: Execute a synthetic poisoned-post/canary retrieval suite against the eventual stack - WHY: architecture controls need runtime proof - ANGLE: security acceptance test.
- LEAD: Test target adapter extraction and retirement - WHY: generic unlearning findings cannot prove target behavior - ANGLE: rare-span and membership probes.
- DEAD END: prompt wording alone is a sufficient injection/access-control defense.
- DEAD END: approximate unlearning can be represented as guaranteed erasure without empirical verification.

## CLAIMS

- C31: Retrieved blog content is untrusted data and must not be allowed to issue system/tool instructions.
- C32: Subject/lifecycle/access filters must execute before vector retrieval and every returned chunk must retain lineage.
- C33: RAG reduces some grounding problems but adds poisoning, exfiltration and vector-store attack surfaces.
- C34: Fine-tuned identity effects require verified unlearning or checkpoint retirement after revocation; deleting source files alone is insufficient.
- C35: The persona should have no autonomous external agency; draft-only behavior materially reduces both security and false-identity risk.
