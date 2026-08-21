# Wave 1 - Persona Validity and Model-Method Evidence

Observer: `root`  
Observed at: 2026-07-13  
Method: ACL/arXiv primary-paper search plus explicit counter-search for positive digital-twin results.

## Key findings

1. A text corpus cannot reveal a person's private internal state. The testable product is a source-grounded proxy for observable writing, stated positions and decision patterns, with temporal and uncertainty labels.
2. BehaviorChain evaluated 15,846 behaviors over 1,001 personas and reports that even state-of-the-art models struggle with continuous human-behavior simulation. Dialogue resemblance is not evidence of behavioral equivalence.
3. PersonaGym evaluated 10 models, 200 personas and 10,000 questions and found persona capability does not monotonically improve with general model size/recency. Model selection therefore requires persona-specific held-out evaluation.
4. PersonaLLM provides positive evidence that prompting can induce perceivable Big Five-associated linguistic patterns, but that is assigned trait expression rather than identification of one real author's latent psychology.
5. LaMP formalizes user-history retrieval and time-based splits. Retrieval selects task-relevant history and improves personalization, but corpus relevance and temporal splits are prerequisites; random or global history is not an adequate baseline.
6. Fine-tuning versus retrieval studies find RAG more reliable for factual knowledge injection in their evaluated tasks. This supports RAG-first for traceability and updates; it does not prove superior stylistic imitation or subjective decision fidelity.
7. Positive counterevidence such as PersonaTwin shows that richer demographic, behavioral and psychometric conditioning can improve proxy outcomes. It also demonstrates why blog text alone is an information-limited input, not an exact twin.

## Sources

- BehaviorChain: https://aclanthology.org/2025.findings-acl.813/
- PersonaGym: https://aclanthology.org/2025.findings-emnlp.368/
- PersonaLLM: https://aclanthology.org/2024.findings-naacl.229/
- LaMP: https://aclanthology.org/2024.acl-long.399/
- Fine-Tuning or Retrieval?: https://arxiv.org/abs/2312.05934
- PersonaTwin: https://aclanthology.org/2025.gem-1.66/
- Persona consistency across tasks: https://aclanthology.org/2025.findings-emnlp.603/

## Contradictions and resolution

- Counter: humans can perceive prompted personality traits and richer persona frameworks achieve strong task similarity. Resolution: this supports observable simulation, not equality of private thought, current endorsement or continuous real-world behavior.
- Counter: fine-tuning can improve style. Resolution: style benefit must be measured separately from factual/stance faithfulness, while deletion and provenance favor separable retrieval.
- Counter: a large frontier model should be the best persona model. Resolution: PersonaGym reports no monotonic relation; compare candidates on the target's held-out authored material.

## EXPAND

- LEAD: Extract exact BehaviorChain failure categories and baselines - WHY: convert digital-twin limitation into evaluation cases - ANGLE: paper tables and code.
- LEAD: Compare RAG, profile prompting and one-person PEFT on identical time-held-out posts - WHY: no single cited paper answers the full persona objective - ANGLE: synthetic authorized fixture, fixed questions and ablations.
- LEAD: Add contradiction and opinion-change benchmarks - WHY: static persona scoring can punish legitimate temporal change - ANGLE: dated claims and before/after questions.
- DEAD END: no paper establishes that public writing alone can reproduce a person's internal thinking exactly.

## CLAIMS

- C20: “Same thinking” is not an observable or falsifiable target from blog text; the system must be specified as a proxy for observable authored behavior.
- C21: State-of-the-art dialogue models still struggle with continuous persona behavior, so fluent resemblance cannot certify a digital twin.
- C22: RAG-first is justified for factual grounding, provenance, updates and deletion, but persona fidelity still requires independent evaluation and may benefit from a separable style adapter.
- C23: Evaluation must use time-held-out authored outcomes, not training-corpus self-reconstruction or generic personality questionnaires alone.
