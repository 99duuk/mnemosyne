# Wave 1 - Reversible Data Governance

Observer: `/root/identity_ethics_r2` on bounded governance follow-up  
Observed at: 2026-07-13  
Full artifact: `.omo/teams/team-9c661443/artifacts/data-governance-lifecycle-r2.md`

## Key findings

1. Authority is not one Boolean. Personal-data basis, sensitive/unique-data basis, copyright/license and persona-publication permission need separate effective dates, scopes, evidence and withdrawal states.
2. Every acquisition begins in quarantine. Only reviewed, active artifacts may serve or build descendants.
3. Complete lineage covers raw, normalized, chunk, embedding, profile, dataset snapshot, model, evaluation, cache and export. Parent invalidation synchronously blocks descendants before slower physical deletion.
4. Deletion is a verified saga: requester/scope resolution, immediate serving denial, recursive invalidation, primary/derived purge, processor acknowledgements, backup restore gate, model decision, independent verification and a minimal re-ingestion tombstone.
5. Source state and authority state are separate. Public-to-private or missing triggers an operational stop but does not alone decide the legal reason or prove permanent deletion.
6. PIPA Articles 21, 36 and 37 support restoration-resistant destruction, correction/deletion, processing suspension and consent withdrawal when applicable. Processor controls derive from Article 26.
7. Access-log retention under current PIPC Notice 2026-9 is generally at least one year and at least two years for specified classes; the exact class must be assessed and does not justify raw-content audit retention.
8. Approximate machine unlearning is not sufficient deletion proof. If residual extraction/inference/influence cannot be disproved, retire and retrain from an authorized snapshot.

## Operational state model

`DISCOVERED -> QUARANTINED -> REVIEWED -> AUTHORIZED -> ACTIVE -> SUSPENDED -> DELETE_PENDING -> PURGING -> VERIFYING -> DELETED -> TOMBSTONED`

Failures remain suspended and cycle through `PARTIAL_FAILURE -> PURGING`. A legal hold is isolated and unavailable to retrieval, training, profile, evaluation and export.

## Sources

- PIPA Article 21: https://www.law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=900078981
- PIPA Article 26: https://www.law.go.kr/법령/개인정보보호법/제26조
- PIPA Article 36: https://law.go.kr/LSW/lsSideInfoP.do?docCls=jo&joBrNo=00&joNo=0036&lsiSeq=270351&urlMode=lsScJoRltInfoR
- PIPA Article 37: https://www.law.go.kr/LSW/lsLawLinkInfo.do?chrClsCd=010202&lsJoLnkSeq=900079171
- PIPC Notice 2026-9 Article 8: https://www.law.go.kr/LSW/admRulSideInfoP.do?admRulSeq=2100000281400&chrClsCd=010201&docCls=jo&joNo=0008&urlMode=admRulScJoRltInfoR
- PIPC 2025 GenAI guide: https://pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS217&mCode=G010030020&nttId=11439
- ICML 2023 deletion counterevidence: https://proceedings.mlr.press/v202/chourasia23a.html
- ICLR 2025 unlearning failure: https://proceedings.iclr.cc/paper_files/paper/2025/hash/7e810b2c75d69be186cadd2fe3febeab-Abstract-Conference.html

## EXPAND

- LEAD: Determine the applicable one- versus two-year access-log class from projected subject/data categories - WHY: binding retention changes - ANGLE: deployment matrix.
- LEAD: Execute one canary deletion across DB, objects, vector index, profile, cache, processor, backup and model probes - WHY: schema does not prove non-restorability - ANGLE: clean-room drill.
- LEAD: Review actual authority instrument and backup/model residuals with Korean counsel - WHY: rights layers are fact-specific - ANGLE: compile reviewed scope into rights versions.
- DEAD END: one consent Boolean can safely govern all downstream operations.
- DEAD END: a processor HTTP 200 or a deleted DB row proves end-to-end deletion.

## CLAIMS

- C36: Binding personal-data duties and nonbinding engineering recommendations must be labeled separately.
- C37: Immediate logical denial and recursive descendant invalidation precede asynchronous physical purge.
- C38: A minimal tombstone and restore gate are required to prevent deleted/private content from being reintroduced.
- C39: Processor deletion needs contractual propagation, evidence and verification; outsourcing does not eliminate controller accountability.
- C40: Approximate unlearning is not sole deletion proof; unverifiable identity-bearing checkpoints are retired.
