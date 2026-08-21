# Wave 3 Counter-search: RAG, Citations, and Training

## Lead L-05: decorative citations

- [Fine-grained citation evaluation](https://aclanthology.org/2024.inlg-main.35/) reports that no single faithfulness metric wins consistently in its evaluation settings.
- [ARES](https://aclanthology.org/2024.naacl-long.20/) evaluates context relevance, answer faithfulness and answer relevance, with human annotation used to calibrate prediction-powered inference.
- [RAGAS](https://aclanthology.org/2024.eacl-demo.16/) separately frames retrieval and generation dimensions.
- Resolution: require deterministic source/span checks plus a human-labelled held-out suite; do not release based only on prompt-formatted citations or one LLM judge.

## Lead: RAG versus training

- The original [RAG paper](https://arxiv.org/abs/2005.11401) establishes explicit non-parametric retrieval memory alongside generation.
- [Fine-Tuning or Retrieval?](https://arxiv.org/abs/2312.05934) reports RAG outperforming unsupervised fine-tuning on the study's knowledge-injection tasks.
- [LoRA](https://arxiv.org/abs/2106.09685) establishes parameter-efficient adaptation, but [memorization research](https://arxiv.org/abs/2202.07646) documents prompt-conditioned training-data emission risk.
- Resolution: keep factual claims, temporal views, citations and revocation-sensitive material in retrieval; permit an adapter only for measured style-only residuals under explicit authorization.

## EXPAND

none - the decision boundary is sufficiently narrow: RAG is not asserted to guarantee correctness, and training is not asserted to be forbidden in every authorized case.
