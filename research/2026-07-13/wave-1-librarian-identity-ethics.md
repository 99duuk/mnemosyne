# Wave 1 - Identity, Consent, and Impersonation

Observer: `/root/identity_ethics_r2`  
Observed at: 2026-07-13  
Coverage: 60+ query sweep; Korean primary law/regulator material, international standards, peer-reviewed HCI/ethics, active counter-search.

## Key findings

1. Use a persona risk ladder: L0 archive/search, L1 attributed analysis, L2 recognizable style simulation, L3 named first-person persona, L4 real-world proxy. Without a living subject's explicit identity consent, public deployment stops at L1.
2. Korean AI Basic Act Article 31 makes AI-use/output disclosure a baseline for public generative services, but disclosure does not supply copyright, privacy, personality, or identity authorization.
3. PIPA Articles 15, 22, and 37 support purpose-specific legal basis/consent and withdrawal/cessation controls. A generic permission to publish or use data for AI is not evidence of permission for a named public conversational identity.
4. Copyright permission and identity authorization are separate gates. The blog author also cannot clear third-party comments, quotations, correspondence, images, or depicted persons by themselves.
5. Revocation must be architectural: stop generation, delete/quarantine source/index/cache/profile, prevent re-ingest, notify downstream, verify removal, and retire an identity-bearing checkpoint when unlearning cannot be proven.
6. A persona must not autonomously act as the represented person. External or consequential actions require current human approval under the operator's own identity.
7. Foreign and ethical guidance converges on persistent disclosure, calibrated reliance, human responsibility, vulnerable-user safeguards, and stricter posthumous governance. These are comparative safeguards, not automatically binding Korean law.

## Primary and high-value sources

- Korean AI Basic Act: https://www.law.go.kr/LSW/lsInfoP.do?ancYnChk=&chrClsCd=010202&efYd=20260122&lsiSeq=282791&urlMode=lsInfoP
- MSIT implementation explanation: https://m.korea.kr/news/policyNewsView.do?newsId=148958380
- PIPA: https://www.law.go.kr/법령/개인정보보호법
- Korean AI voice injunction summary: https://law.go.kr/LSW/precInfoP.do?mode=0&precSeq=613155
- Korean UCPA: https://www.law.go.kr/LSW/lsInfoP.do?ancYnChk=&chrClsCd=010202&efYd=20260528&lsiSeq=271245&urlMode=lsInfoP
- Korean Copyright Act: https://law.go.kr/LSW/lsInfoP.do?ancYnChk=0&lsId=000798
- Personality/likeness case: https://www.law.go.kr/LSW/precInfoP.do?precSeq=222117
- Public-figure biography counterexample: https://www.law.go.kr/LSW/precInfoP.do?precSeq=228069
- UNESCO AI Ethics Recommendation: https://www.unesco.org/en/legal-affairs/recommendation-ethics-artificial-intelligence
- NIST AI 600-1: https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf
- UNICEF AI and children: https://www.unicef.org/innocenti/reports/policy-guidance-ai-children
- Cambridge deadbot ethics paper: https://www.repository.cam.ac.uk/items/8b798105-7573-4d7d-9768-50efcac99a44

## Contradictions and resolution

- Counter: public-interest biography, documentary work, satire, scholarship, and some legitimate-interest processing may be lawful without consent. Resolution: this keeps L1 attributed analysis available; it does not establish permission for false current attribution or autonomous identity agency.
- Counter: disclosure sometimes reduces trust and conversion. Resolution: disclosure is for informed choice and calibrated reliance, not engagement optimization.
- Counter: style alone may not be categorically protected like a copied work. Resolution: gate on identifiability, false association, scope of consent, corpus rights, audience confusion, and harm rather than claiming a universal style copyright.

## EXPAND

- LEAD: Obtain the final official Korean AI Basic Act Article 31 transparency guideline PDF and map exact UI/accessibility/export-label examples - WHY: operational form may be refined - ANGLE: NIA/TTA/MSIT 2026 guideline repository.
- LEAD: Track appeal or merits disposition of Seoul Central District Court 2025카합20687 - WHY: current evidence is a first-instance provisional injunction - ANGLE: court docket updates.
- LEAD: Resolve postmortem authority where Article 128 relatives disagree - WHY: standing is not a product-governance protocol - ANGLE: Korean commentary/case law.
- DEAD END: No primary Korean rule found equating a public blog with consent for a named interactive persona.
- DEAD END: No universal evidence that transparency increases trust.
- DEAD END: No support for treating a generic copyright license as identity/endorsement consent.

## CLAIMS

- C5: Public AI disclosure is required as a baseline in Korea, but it does not cure other rights defects. High risk; primary law plus MSIT, UNESCO/NIST comparison; counter-search recorded.
- C6: A living author's public blog is not equivalent to consent for a named first-person persona generating novel statements. High risk; PIPA/personality cases plus counterexamples for biography/analysis.
- C7: Consent for an L2/L3 persona must be granular, demonstrable, revocable, channel- and identifier-specific. High risk; PIPA primary law, 2025 voice injunction analogy.
- C8: Public release without living-subject consent should stop at L1 attributed analysis. High risk operational gate; admits public-interest expression counterexamples.
- C9: Revocation is credible only when the system can stop, remove retrieval derivatives, prevent re-ingestion, and retire checkpoints if removal cannot be verified. High risk; PIPA Article 37 plus technical dependency still pending.
