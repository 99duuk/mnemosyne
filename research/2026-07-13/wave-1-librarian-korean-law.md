# Wave 1 - Korean Copyright, Privacy, Database, and Personality Law

Observer: `/root/korean_law_r2`  
Observed at: 2026-07-13  
Coverage: current statutes, Supreme Court and lower-court materials, regulator/government guidance, and counter-search against categorical prohibition claims.

## Key findings

1. Current Korean law has no categorical AI/TDM exemption. Copyright Act Article 35-5 is a fact-specific fair-use rule; the 2026 copyright guide is nonbinding guidance rather than a safe harbor.
2. Ideas and an abstract style are generally distinguishable from protected expression, but actual sentences, close paraphrases, distinctive selection/arrangement, photographs and other expressive elements can be protected.
3. Database-producer protection can apply to substantial extraction/reuse, including repeated and systematic small extractions depending on the proven facts.
4. Public personal data remains protected. PIPA Article 15 requires a processing basis; Supreme Court 2014Da235080 makes the objectively recognized original disclosure purpose central rather than treating public status as blanket reuse consent.
5. Sensitive information under Article 23 needs separate consent or another statutory basis. A persona intentionally tied to its target is not pseudonymized as to that target.
6. UCPA protection for identity indicators requires factual elements such as domestic recognition and economic value, so it does not automatically cover every blogger. General personality rights and false association remain separate risk routes.
7. AI Basic Act Article 31 supplies disclosure duties, not authorization for training inputs or identity simulation.
8. No per se ban on all nonconsensual analysis or style resemblance was found. The high-risk configuration is a public, commercial, named and first-person persona without granular consent, especially when it creates novel attribution.

## Primary and high-value sources

- Copyright Act Article 35-5: https://law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1025203559
- Copyright Commission 2026 AI guide: https://www.copyright.or.kr/information-materials/publication/research-report/view.do?brdctsno=55211
- MCST caveat on guide: https://www.mcst.go.kr/english/policy/pressView.jsp?pSeq=635
- Database right Article 93: https://law.go.kr/LSW/lsSideInfoP.do?docCls=jo&joBrNo=00&joNo=0093&lsiSeq=283335&urlMode=lsScJoRltInfoR
- Supreme Court database case 2023Do17354: https://www.law.go.kr/LSW/precInfoP.do?precSeq=600551
- PIPA Article 15: https://law.go.kr/LSW/lsLinkCommonInfo.do?ancYnChk=&chrClsCd=010202&lsJoLnkSeq=1020398481
- Public personal-data case 2014Da235080: https://www.law.go.kr/LSW/precInfoP.do?precSeq=183259
- PIPA Article 23: https://www.law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1027416043
- UCPA Article 2: https://law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1020635549
- Personality-right case 2020Da227455: https://lawclerk.scourt.go.kr/portal/news/NewsViewAction.work?gubun=4&seqnum=7657
- AI Basic Act Article 31: https://law.go.kr/LSW/lsSideInfoP.do?docCls=jo&joBrNo=00&joNo=0031&lsiSeq=282791&urlMode=lsScJoRltInfoR
- PIPC public-data AI guide: https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS217&mCode=G010030000&nttId=10375
- PIPC 2025 lifecycle guide: https://pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS217&mCode=G010030020&nttId=11439

## Contradictions and resolution

- Counter: Article 35-5 or the 2026 guide makes AI training categorically fair. Resolution: neither creates a categorical safe harbor; purpose, nature, amount, market effect and other facts still matter.
- Counter: style is not copyright, so a clone is unrestricted. Resolution: abstract style and protectable expression differ; close output, corpus copying, database extraction, privacy, personality and false-attribution questions remain.
- Counter: public personal data may be reused freely. Resolution: Korean precedent keeps it protected and asks whether reuse falls within the objectively recognized original disclosure purpose.
- Counter: every blogger has a statutory publicity right. Resolution: the UCPA route has recognition/economic-value elements; ordinary bloggers still may have personality, privacy, contract and copyright claims.

## EXPAND

- LEAD: Apply Article 35-5 factors to exact corpus size, access path, output controls and commercial substitution - WHY: legal outcome is fact-specific - ANGLE: deployment-specific counsel memo.
- LEAD: Test whether health, beliefs, family or other post content enters Article 23 categories - WHY: sensitive information has a separate gate - ANGLE: item-level classifier plus human review.
- LEAD: Determine target recognition/economic value and marketing language - WHY: UCPA applicability depends on facts - ANGLE: identity-risk assessment.
- LEAD: Investigate memorization/extraction and membership-inference controls - WHY: output leakage affects copyright/privacy risk - ANGLE: security/evaluation lanes.
- DEAD END: no categorical Korean rule was found that all public blog training is lawful or that all persona simulation is categorically prohibited.

## CLAIMS

- C15: Korean Copyright Act Article 35-5 is fact-specific; neither current law nor the 2026 guide creates a categorical AI-training safe harbor.
- C16: Public personal information remains protected and reuse must be assessed against a legal basis and the objectively recognized original disclosure purpose.
- C17: Abstract style resemblance is not equivalent to copying expression, but it does not resolve corpus copying, close paraphrase, database, privacy, personality or false-attribution risks.
- C18: A target-linked persona is not pseudonymized with respect to that target; sensitive-information processing requires a separate gate.
- C19: The AI Basic Act disclosure requirement is an output-transparency duty, not an input-rights license.
