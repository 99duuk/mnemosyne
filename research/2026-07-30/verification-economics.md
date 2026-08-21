# Verification Economics

| claim | Risk | Error cost | Verification cost/time | Chosen verification path | Decision | Outcome | Residual risk |
|---|---|---|---|---|---|---|---|
| Naver platform rules | High | Unlawful or account-restricted collection design | Low-medium | Official Naver pages plus counter-search | verify | Pending | Terms may change |
| Korean legal constraints | High | Rights infringement or misrepresentation | Medium | Primary statutes/guidance, cross-check with official agencies | verify | Pending | Fact-specific legal analysis remains necessary |
| RAG-before-fine-tune implementation order | Medium | Wasted build effort and untraceable answers | Medium | Papers, official docs, prototype architecture review | verify | Pending | Model/data quality varies |
| Local Mac feasibility | Medium | Wrong hardware plan | Low | Official hardware/runtime documentation and local runtime test where needed | verify | Pending | Exact model size depends on RAM and quantization |
| Naver owner acquisition path | High | Building an infeasible or noncompliant importer | Low | Official Help center pages, direct counter-search | verify | Per-post owner PDF backup verified; complete transferable export not verified | PDF is lossy and owner-only |
| Citation verification | High | Unsupported claims presented as sourced | Medium | ACL evaluation research and explicit atomic-claim checks | verify | Automated metrics require human calibration; no single metric is sufficient | Domain-specific gold set required |
