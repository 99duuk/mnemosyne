# Korean-law lane: public Naver Blog collection and named-person persona-model reuse

Research date: 2026-07-13 (KST)  
Scope: Korean law only; public blog posts collected for model training, fine-tuning, embeddings/RAG, or an interactive persona modeled on a real author. Platform terms and technical collection controls are adjacent, not resolved by this memo. This is a research synthesis, not a legal opinion for a specific deployment.

## TL;DR

Public accessibility is not a license. A public blog corpus can simultaneously implicate (1) copyright in individual posts, (2) database-maker rights in a platform corpus, (3) personal information and sensitive information, (4) name/portrait/personality and publicity-like interests, (5) unfair-competition rules, and (6) AI transparency duties.

The proposed use is not governed by a settled Korean rule saying that AI training is lawful or unlawful. Korea has no enacted, dedicated text-and-data-mining exception as of the research date. The current route is the fact-specific fair-use rule in Copyright Act Article 35-5. The Ministry of Culture, Sports and Tourism (MCST) and Korea Copyright Commission (KCC) published a 2026 AI-training fair-use guide, but the official release expressly says its hypotheticals are not authoritative interpretations and courts may decide similar facts differently. It is a reference, not a safe harbor.

For a no-consent, public, commercial, named-person chatbot, the overall risk is high. Targeting one author increases memorization, expressive-substitution, attribution, endorsement, and identity risks. Public posts can also reveal or allow inference of political views, beliefs, health, or sex-life information; PIPA Article 23 generally requires separate consent or an express statutory basis for those sensitive categories. The general legitimate-interest basis does not itself override Article 23.

The durable path is explicit author permission plus independent clearance of platform/database rights, third-party works and people, and sensitive-data handling. The system should still minimize and filter data, prevent verbatim regeneration, support deletion/revocation, identify itself as AI, and avoid claiming to be or speak for the person.

## Analysis: legal lifecycle and principal causes

The legal questions follow the data lifecycle rather than collapsing into a single “scraping legality” question:

1. **Access and acquisition**: Was the material genuinely public? Were login, rate-limit, robots, technical protection, or objective access restrictions bypassed? Did collection copy a substantial or repeatedly systematic part of a protected database?
2. **Corpus creation**: Downloading, normalizing, chunking, embedding, or fine-tuning commonly entails copies or transformations. Copyright fair use, database rights, PIPA legal bases, sensitive data, and third-party material must each be assessed.
3. **Model use**: A model deliberately associated with a named person creates attribution, impersonation, endorsement, personality, publicity-like, and unfair-competition exposure beyond generic corpus training.
4. **Outputs**: Style or abstract ideas are not normally copyrightable, but protected sentences, selection/arrangement, distinctive expression, or substantial parts can be reproduced. Output similarity and market substitution are separate from input-stage legality.
5. **Retention, deletion, and operations**: PIPA purpose limitation, retention/destruction, safeguards, notices, data-subject rights, processors, and overseas transfer can continue to apply. A deletion request is technically difficult if target material has been fine-tuned into weights; design must address that before collection.

## Primary-source matrix

Status labels: **Binding** = enacted law or reported court holding; **Guidance** = official but non-binding administrative/commission material; **Proposal** = announced reform not verified as enacted; **Analogy** = reasoned application without a directly controlling AI-persona holding.

| ID | Issue | Status | Primary or official source | Rule / observation | Application to the proposed use |
|---|---|---|---|---|---|
| C1 | Work and protected expression | Binding | [Copyright Act, current consolidated text](https://www.law.go.kr/LSW/lsSc.do?query=%EC%A0%80%EC%9E%91%EA%B6%8C%EB%B2%95&tabMenuId=tab18&x=0&y=0) | A work is a creative production expressing human thoughts or emotions; literary works are an enumerated category. | Original blog prose, photographs, illustrations, and creative selection/arrangement may be protected. Public display does not place them in the public domain. Short factual fragments or commonplace wording may lack creativity. |
| C2 | Idea/expression distinction | Binding + official explanation | [Supreme Court precedent database](https://www.law.go.kr/LSW/precInfoP.do?precSeq=113785); [KCC copyright primer](https://www.copyright.or.kr/information-materials/common-sense/knowledge-for-netizen/index.do) | Copyright protects creative expression, not an underlying idea, theory, concept, or artistic style as such. | Abstract “thinking patterns,” subjects, facts, or writing style are not independently monopolized by copyright. This does not permit copying the author’s actual expressive choices or substantial structure. |
| C3 | General fair use | Binding | [Copyright Act Article 35-5](https://law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1025203559) | Use is permitted only when it does not conflict with normal exploitation or unreasonably prejudice legitimate interests, considering purpose/character, work type/purpose, amount/substantiality, and market/value effect. | Collection and training require a record-specific, use-specific balance. Commercial purpose and crawling do not automatically defeat fair use, but neither establishes it. Single-author exhaustive copying, memorization, replacement, and licensing-market harm weaken the case. |
| C4 | Supreme Court fair-use application | Binding holding; not an AI case | [KCC official case page for Supreme Court 2021Da272001](https://www.copyright.or.kr/information-materials/trend/precedents/view.do?brdctsno=53328); [Supreme Court judgment PDF](https://www.scourt.go.kr/sjudge/1721627857672_145737.pdf) | Long-term, unrestricted online provision of exam questions containing protected works was not fair use; all circumstances and market effects matter. | Confirms that online availability, educational context, or partial use does not decide the issue alone. It does not resolve AI training, but it makes blanket “training is transformative” conclusions untenable. |
| C5 | 2026 AI-training fair-use guide | Guidance | [KCC guide page, published 2026-02-26](https://www.copyright.or.kr/information-materials/publication/research-report/view.do?brdclasscode=03&brdclasscodeList=&brdctsno=55211&etc1=&etc2=&nationcode=&nationcodeList=&pageIndex=1&searchTarget=SUBJECT&searchText=&searchkeyword=); [MCST official release](https://www.mcst.go.kr/english/policy/pressView.jsp?pSeq=635) | The guide analyzes training copies and Article 35-5; it says commercial purpose or crawling is not automatically disqualifying and requires a comprehensive balance. MCST expressly says hypotheticals are not authoritative interpretations and courts ultimately decide; similar facts can produce different rulings. | Useful compliance evidence, not a statutory exception, approval, or safe harbor. The non-binding caveat must accompany any reliance on the guide. |
| C6 | Dedicated TDM exception | Current-law negative finding + proposal | [Current Copyright Act](https://www.law.go.kr/LSW/lsSc.do?query=%EC%A0%80%EC%9E%91%EA%B6%8C%EB%B2%95&tabMenuId=tab18&x=0&y=0); [MCST 2025 work plan](https://mcst.go.kr/servlets/eduport/front/upload/UplDownloadFile?pFileName=2025%EB%85%84_%EB%AC%B8%ED%99%94%EC%B2%B4%EC%9C%A1%EA%B4%80%EA%B4%91%EB%B6%80_%EC%A3%BC%EC%9A%94%EC%97%85%EB%AC%B4_%EC%B6%94%EC%A7%84%EA%B3%84%ED%9A%8D.pdf&pPath=0302000000&pRealName=20250110171603318075115762_PRESS20250115104322261675.pdf) | The consolidated Act contains no dedicated AI/TDM training exception. MCST described TDM immunity as a legislative-reform item. | Treat TDM immunity and training-data-disclosure rules as reform discussions unless a later enacted amendment is identified. Current analysis returns to Article 35-5. |
| C7 | Attribution and integrity | Binding | [Copyright Act, current consolidated text](https://www.law.go.kr/LSW/lsSc.do?query=%EC%A0%80%EC%9E%91%EA%B6%8C%EB%B2%95&tabMenuId=tab18&x=0&y=0) | Authors have rights concerning indication of name and integrity of their works, subject to statutory limits. | Direct quotations or altered presentation under the author’s name can add moral-right risk. Labeling generated text as the person’s words is materially riskier than describing it as AI-generated synthesis. |
| C8 | Style in generative AI | Guidance/research; unsettled | [KCC technology report](https://www.copyright.or.kr/information-materials/trend/tmis/view.do?brdclasscode=&brdclasscodeList=&brdctsno=54338&etc1=&etc2=&nationcode=&nationcodeList=&noticeYn=&pageIndex=8&searchTarget=ALL&searchText=&searchkeyword=) | The official research discussion notes the view that style is closer to idea and therefore difficult to protect, while training and output copying can still infringe; courts have not settled the AI-specific issue. | “Only copying style” is not a complete defense where the system also ingests full posts, generates close paraphrases, or trades on the person’s identity. |
| D1 | Database-maker right | Binding | [Copyright Act Article 93](https://law.go.kr/LSW/lsSideInfoP.do?docCls=jo&joBrNo=00&joNo=0093&lsiSeq=283335&urlMode=lsScJoRltInfoR) | A database maker has rights in all or a substantial part. Repeated/systematic extraction of individually insubstantial portions is treated as substantial when it conflicts with normal use or unreasonably harms the maker. | An author’s page, a platform category, or a broader platform corpus may be a protected database only if statutory investment and structure requirements are met. Systematic crawling can matter even when each request is small. Copyright permission from the post author does not automatically clear platform database rights. |
| D2 | Database substantiality | Binding | [Supreme Court 2023Do17354](https://www.law.go.kr/LSW/precInfoP.do?precSeq=600551) | Quantitative importance is measured against the database as a whole; qualitative importance focuses on investment in creating, updating, verifying, and supplementing the extracted portion. Repeated small extraction must have the same practical effect as extracting a substantial part. | The result depends on corpus boundaries, amount, frequency, and platform investment. “Only public pages” and “only a few fields per request” do not end the analysis. |
| D3 | Access restrictions and scraping | Binding, fact-specific | [Supreme Court 2021Do1533](https://www.law.go.kr/precInfoP.do?precSeq=221765) | Access authorization can depend on objective service-provider intent, terms, and technical restrictions; the case also applies the database-right framework. | Do not generalize this restricted-access case into a ban on public-web collection. Conversely, bypassing authentication, blocks, rate limits, or technical protections creates risks distinct from copyright fair use. |
| D4 | UCPA protection of supplied data | Binding + official legislative explanation | [UCPA current Article 2](https://law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1020635549); [KIPO official explanation](https://www.kipo.go.kr/ko/kpoBultnDetail.do?aprchId=BUT0000029&keyword=&menuCd=SCD0200618&ntatcSeq=19314&pageIndex=&searchCondition=&sysCd=SCD02%2F1000) | Certain electronically accumulated, substantially managed, non-secret data supplied in business can be protected against specified unauthorized acquisition/use, including circumvention scenarios. | Whether open blog pages satisfy the “supplied to specified persons or many specified persons” and other elements is uncertain. Do not treat the UCPA data clause as automatically covering every public website. |
| P1 | PIPA legal basis and legitimate interest | Binding | [PIPA Article 15](https://law.go.kr/LSW/lsLinkCommonInfo.do?ancYnChk=&chrClsCd=010202&lsJoLnkSeq=1020398481) | Processing requires a legal basis. Legitimate interest applies only where processing is necessary, the controller’s interest clearly prevails, the processing is substantially related, and it stays within a reasonable scope. | Public availability is not a legal basis by itself. A documented purpose/necessity/balancing assessment is required. A named commercial persona and expansive retention make the balance harder than anonymized internal analysis. |
| P2 | Publicly available personal data | Binding precedent | [Supreme Court 2014Da235080](https://law.go.kr/LSW/precStmdInfoP.do?precSeq=183259); [Supreme Court judgment PDF](https://www.scourt.go.kr/sjudge/1471519090552_201810.pdf) | Public personal information remains protected. Non-consensual collection/use may be lawful within an objectively recognizable scope considering the person’s public status, nature/purpose/scope of original disclosure, later purpose/form, and competing interests. Commercial purpose alone is not automatically unlawful. | This directory/profile aggregation case is not blanket permission for persona modeling. An interactive simulation that infers views or answers new questions can exceed the original blog-disclosure purpose and readers’ objective expectations. |
| P3 | PIPC public-data AI guidance | Guidance | [PIPC 2024 guide](https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS217&mCode=G010030000&nttId=10375); [PIPC corrective explanation](https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS210&mCode=C020020000&nttId=10665) | Blogs are among publicly accessible sources. Article 15(1)(6) can support AI training/services only after legitimacy, necessity, concrete balancing, and safeguards. PIPC explicitly says public data remains personal data and the guide is not government licensing or approval; binding change would require legislation. | A legitimate-interest assessment is possible but not presumed. Preserve the PIPC non-binding caveat. Identify the controller, purpose, data categories, expected use, risks, opt-out, and less intrusive alternatives. |
| P4 | Current generative-AI privacy lifecycle | Guidance | [PIPC 2025 generative-AI privacy guide](https://pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS217&mCode=G010030020&nttId=11439); [PIPC press release](https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS074&mCode=C020010000&nttId=11410) | The lifecycle approach covers planning, data collection, training/development, and service operation, including fine-tuning via commercial APIs or open-source models. | Use the guide to evidence privacy-by-design: minimize, filter, secure, document, test extraction, control prompts/outputs, handle rights requests, and govern providers. It does not supply an independent legal basis. |
| P5 | Sensitive information | Binding | [PIPA Article 23](https://www.law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1027416043) | Ideology/belief, union/party membership, political views, health, sex life, and prescribed categories require separate consent or an express statutory authorization. | This is often the strongest blocker. A “thinking/personality” corpus can explicitly contain or infer political views, beliefs, health, or sex-life information. Article 15 legitimate interest does not itself satisfy Article 23. Exclude these data or obtain valid separate consent unless another express basis applies. |
| P6 | Pseudonymized scientific research | Binding | [PIPA Article 28-2 legislation page](https://www.law.go.kr/LSW/lsInfoP.do?ancNo=16930&ancYd=20200204&ancYnChk=0&chrClsCd=010202&efGubun=Y&efYd=20200805&lsiSeq=213857&nwJoYnInfo=Y) | Pseudonymized information may be processed without consent for statistics, scientific research, or public-interest records, subject to the statutory regime. | A persona intentionally linked to the real author is not pseudonymized as to that target. Commercial mimicry is not automatically scientific research. Pseudonymization remains useful for third parties and internal evaluation. |
| P7 | LLM privacy inspection findings | Guidance/enforcement signal | [PIPC 2024 LLM inspection release](https://www.pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS074&mCode=C020010000&nttId=10027) | PIPC recommended filtering identifiers and important data, clearer notice of input use, privacy-policy clarity, and reporting processes. | These are concrete operational expectations for corpus and service controls, especially where user prompts may add new personal information. |
| P8 | Downstream PIPA lifecycle duties | Binding framework | [PIPA current consolidated text](https://www.law.go.kr/LSW/lsInfoP.do?ancYnChk=&chrClsCd=010202&efYd=20251002&lsiSeq=270351&urlMode=lsInfoP) | Purpose limitation, indirect-collection notice in applicable cases, retention/destruction, safeguards, privacy policy, rights of access/correction/deletion/suspension, processors, and overseas transfers can apply. | A lawful collection theory does not end compliance. Fine-tuning makes deletion and correction difficult; the architecture must specify retraining, model-version retirement, retrieval-store deletion, provider deletion, and audit evidence. |
| I1 | Statutory publicity-like unfair competition | Binding | [UCPA Article 2(1), identifying-sign clause](https://law.go.kr/lsLinkCommonInfo.do?chrClsCd=010202&lsJoLnkSeq=1020635549) | Unauthorized business use, contrary to fair commercial practice or competition, of a domestically widely recognized and economically valuable person’s name, portrait, voice, signature, or other identifying sign can be unfair competition when it harms economic interests. | A well-known monetized blogger may qualify; an ordinary blogger may not. Use of name, portrait, voice clone, handle, signature phrase, or marketing such as “chat with X” strengthens the claim. Textual style alone is not squarely resolved as an “identifying sign.” |
| I2 | Scope of publicity-like clause | Official explanation | [KIPO 2022 explanation](https://kipo.go.kr/ko/kpoBultnDetail.do?aprchId=BUT0000029&keyword=&menuCd=SCD0200618&ntatcSeq=19495&pageIndex=&searchCondition=&sysCd=SCD02); [KIPO 2026 enforcement update](https://www.kipo.go.kr/ko/kpoBultnDetail.do?aprchId=BUT0000029&keyword=&menuCd=SCD0200618&ntatcSeq=20949&pageIndex=&searchCondition=&sysCd=SCD02) | KIPO explains the elements as wide domestic recognition, economic value, identifying sign, unauthorized commercial use, and economic harm; administrative enforcement has become active. | Do not call this a universal Korean “publicity right.” It is a defined unfair-competition cause of action with elements. General personality/tort doctrines remain separate. |
| I3 | Name, portrait, and personality interests | Binding judicial doctrine + official interpretation | [Supreme Court 2020Da227455 case note](https://lawclerk.scourt.go.kr/portal/news/NewsViewAction.work?gubun=4&searchOption=&searchWord=&seqnum=7657); [Supreme Court 2023Da233895 release](https://www.scourt.go.kr/supreme/news/NewsViewAction2.work?gubun=702&searchOption=&searchWord=&seqnum=1631); [KIPO official legal interpretation](https://www.law.go.kr/LSW/cgmExpcInfoP.do?cgmExpcDatSeq=6509798&mode=2&ofiClsCd=350137) | Constitutional personality interests protect against unauthorized photography, depiction, publication, commercial use, or impersonating use of a person’s name/likeness, subject to purpose, means, proportionality, and interest balancing. | Even if the target is not famous enough for the UCPA identifying-sign clause, a service that uses the real name/avatar and represents generated views as theirs can create personality/tort exposure. Private, clearly labeled analysis is lower risk than public impersonation. |
| I4 | General UCPA catch-all | Binding precedent with caution | [Supreme Court 2019Ma6525 judgment PDF](https://www.scourt.go.kr/sjudge/1585660736173_221856.pdf); [KCC cautionary analysis](https://www.copyright.or.kr/information-materials/trend/the-copyright/view.do?brdclasscode=&brdclasscodeList=&brdctsno=46188&etc1=&etc2=&nationcode=&nationcodeList=&noticeYn=&pageIndex=15&searchTarget=SUBJECT&searchText=%EC%9D%B4%EC%8A%88%EB%A6%AC%ED%8F%AC%ED%8A%B8&searchkeyword=) | Supreme Court recognized unfair appropriation of reputation/content built through another’s substantial investment under the general clause. KCC analysis cautions against using the catch-all to recreate expired or absent copyright protection and shrink the public domain. | A persona product that free-rides on a creator’s cultivated reputation or paid content may face a catch-all claim, but it is fact-specific and cannot automatically convert unprotected style or ideas into property. |
| A1 | AI notice and output labeling | Binding | [AI Basic Act Article 31 and current text](https://law.go.kr/LSW/lsSideInfoP.do?docCls=jo&joBrNo=00&joNo=0031&lsiSeq=282791&urlMode=lsScJoRltInfoR) | Providers of generative-AI products/services must notify users in advance that AI is used and mark outputs as AI-generated. Realistic synthetic audio/image/video requires clear notice or marking. | A public persona chatbot must identify AI operation and generated outputs. The prudent disclosure also says it is not the person and does not communicate their current views. Compliance does not cure copyright, privacy, or personality defects. |
| A2 | High-impact AI | Binding | [AI Basic Act current text](https://www.law.go.kr/LSW/lsInfoP.do?ancYnChk=&chrClsCd=010202&efYd=20260122&lsiSeq=282791&urlMode=lsInfoP); [Article 34](https://www.law.go.kr/lsLinkCommonInfo.do?lsJoLnkSeq=1031809457); [Enforcement Decree](https://www.law.go.kr/LSW/lsInfoP.do?lsId=015032) | High-impact systems in enumerated consequential sectors require risk management, explanation including a training-data overview, user protection, human oversight, and documentation. | A persona chatbot is not high-impact solely because it mimics a person. It may become high-impact if used in covered hiring, lending, education, healthcare, public services, criminal, or other major rights/safety decisions. |
| A3 | AI Act relationship to training rights | Binding negative inference from the Act | [AI Basic Act current text](https://www.law.go.kr/LSW/lsInfoP.do?ancYnChk=&chrClsCd=010202&efYd=20260122&lsiSeq=282791&urlMode=lsInfoP) | The Act imposes AI governance and transparency; it does not grant a general license to collect or train on copyrighted works or personal data. | AI labeling is an additional duty, not an authorization under Copyright Act, PIPA, UCPA, contract, or database law. |
| A4 | Enforcement grace | Official enforcement policy, not statutory suspension | [MSIT official release](https://www.msit.go.kr/eng/bbs/view.do?bbsSeqNo=42&mId=4&mPid=2&nttSeqNo=1191&sCode=eng) | MSIT announced at least a one-year grace period before administrative fines after the Act took effect. | Do not treat the grace period as negating duties or civil exposure. Build compliance now; policy can change and other statutes remain enforceable. |

## Exact solution: release gates

### Gate 1 — obtain and scope permission

Obtain written, informed permission from the author for each intended operation: collection, local storage, reproduction, embeddings/RAG, fine-tuning, public generation, commercial use, use of name/portrait/handle/voice, quotations, derivative presentation, and retention. State whether the author may revoke consent and what happens to trained checkpoints after revocation.

Author permission is necessary but not always sufficient. Separately identify platform/database rights, reposted works, comments, linked media, guest text, photographs of others, and third-party personal information. Prefer an author-controlled export or licensed API over systematic platform crawling.

### Gate 2 — block sensitive and third-party information

Before training, classify personal information and apply a hard filter for PIPA Article 23 categories, minors, identifiers, contact details, third-party anecdotes, private messages, and accidental secrets. If a sensitive-data category is intentionally part of the persona, obtain the legally required separate consent; otherwise exclude it. Do not rely on general legitimate interest for Article 23 data.

### Gate 3 — document fair use only as a fallback theory

If no copyright license covers a use, produce an Article 35-5 assessment for the exact corpus, model, output controls, audience, retention, and market. Record:

- why full text is necessary rather than summaries, licensed data, or retrieval of limited excerpts;
- whether the use adds a materially different analytical function;
- the amount and expressive centrality of copied material;
- controls against memorization, reconstruction, and substitute consumption;
- effect on the author’s current and plausible licensing markets;
- source attribution and removal mechanisms.

Do not write “KCC says AI training is fair use.” The accurate statement is that KCC supplies a non-binding factor-analysis guide and courts decide the outcome.

### Gate 4 — separate corpus, identity, and output controls

- **Corpus**: maintain provenance per item, rights status, hash, source URL, collection time, included personal-data categories, and deletion state.
- **Identity**: use a neutral product name unless identity rights are licensed. Never claim the model is the person, is endorsed by them, or reflects their current views.
- **Outputs**: label every output as AI-generated; run similarity and long-sequence matching against the corpus; block requests for verbatim reproduction, private facts, political/health profiling, impersonation, or professional advice in the person’s name.
- **Lifecycle**: support retrieval-store deletion, data-provider deletion, checkpoint retirement/retraining, audit logging, incident response, and model-version traceability.

### Gate 5 — launch only after scenario classification

| Scenario | Baseline risk | Conditions for responsible progress |
|---|---:|---|
| Author-approved, private internal retrieval | Medium | Written permission; platform/third-party clearance; Article 23 screening; minimal excerpts; no public impersonation; deletion controls. |
| Author-approved, public persona | Medium–High | Express identity/commercial/output permission; clear AI/non-endorsement disclosure; third-party and sensitive-data clearance; verbatim-output controls; termination/revocation plan. |
| No-consent, anonymized internal research | Medium and fact-specific | Document Article 35-5 and Article 15(1)(6); exclude Article 23 data; minimize corpus; no identity-facing output; no technical bypass; no substitute publication. |
| No-consent, public commercial named-person persona | High | Do not launch on “public data + fair use” alone. Obtain permission or redesign to remove the real identity, sensitive profiling, expressive imitation, and corpus reconstruction. |

## Extensible alternatives

1. **Author-operated product**: the author exports and licenses selected posts, approves persona constraints, and can revoke or refresh the corpus. This best aligns copyright, privacy, identity, and accuracy.
2. **Source-linked retrieval assistant**: answer from small, licensed excerpts with citations and explicit uncertainty instead of fine-tuning an identity into model weights. This improves provenance and deletion, although retrieval and quotation still require legal review.
3. **Topic model without identity**: extract high-level topics, public facts, and non-identifying analytical categories; do not expose a named “digital twin.” This reduces personality/publicity and PIPA scope but does not erase copyright in source copies.
4. **Synthetic composite persona**: build from licensed or original material across multiple contributors and prohibit mapping back to one person. This can reduce target-specific identity and memorization risks, provided the composition is not still recognizable as a particular person.
5. **On-device/private author tool**: keep the corpus under the author’s control, avoid external model-provider retention, and limit outputs to the author. This narrows disclosure but still needs third-party and sensitive-data governance.

## Counter-search and falsification log

The research deliberately searched for rules that would make the use categorically lawful as well as categorically unlawful.

| Candidate shortcut | Result of counter-search | Conclusion |
|---|---|---|
| “Anything publicly posted may be collected and trained on.” | PIPA Article 15, PIPC guidance, and Supreme Court 2014Da235080 all preserve legal-basis and scope analysis for public personal data. Copyright contains no public-web exception. | Rejected. Public status is one factor, not permission. |
| “Korea enacted a broad TDM exception.” | Current consolidated Copyright Act was checked against MCST’s own characterization of TDM immunity as a reform item. | Not verified as enacted as of 2026-07-13. |
| “The 2026 KCC guide guarantees fair use.” | MCST’s official release expressly denies authoritative status to the hypotheticals and says courts decide, potentially differently on similar facts. | Rejected. Non-binding reference only. |
| “Commercial training can never be fair use.” | Article 35-5 has no categorical commercial bar; the 2026 official guide says commercial purpose or crawling is not automatically disqualifying. | Rejected. Commerciality is adverse/contextual, not dispositive. |
| “Style is copyrighted, so persona imitation is automatically infringement.” | Statute, case doctrine, and KCC materials preserve the idea/expression distinction and generally place abstract style near the idea side. | Rejected as a categorical copyright claim; actual expressive copying remains actionable. |
| “Style is unprotected, so a named persona is safe.” | Personality/name/portrait doctrines, UCPA identifying-sign and catch-all rules, PIPA, attribution, output copying, and false-endorsement facts remain independent. | Rejected. Copyright is only one layer. |
| “Every public website is a protected database and scraping is criminal.” | Database status, substantiality, access authorization, and technical restrictions are element- and fact-specific in Supreme Court cases. | Rejected. Do not generalize restricted-access or large-database cases to all public pages. |
| “The UCPA publicity-like clause protects every blogger.” | Current text and KIPO explanations require domestic recognition, economic value, specified identifying use, commercial unfairness, and economic harm. | Rejected. A non-famous target may instead rely on general personality/tort doctrines. |
| “Legitimate interest covers political or health data in public posts.” | PIPA Article 23 imposes separate consent or an express statutory basis for sensitive information. | Rejected. Article 15(1)(6) is not a standalone Article 23 exception. |
| “AI Basic Act labeling legalizes the training data.” | Current Act adds transparency and high-impact governance but grants no copyright or PIPA license. | Rejected. Duties are cumulative. |
| “A database maker wins whenever small pieces are repeatedly requested.” | Supreme Court 2023Do17354 requires the repeated extraction to have the practical effect of extracting a substantial part, with quantitative and qualitative analysis. | Rejected as categorical. Corpus facts control. |
| “A public commercial persona is categorically prohibited.” | No located statute or Supreme Court judgment creates a per se ban. Fair use, public-data processing, personality balancing, and UCPA elements are fact-specific. | Rejected as overstatement, while the combined risk remains high. |

## Settled law, guidance, proposal, and analogy

### Settled or relatively settled

- Copyright protects creative expression, not abstract ideas or style.
- Article 35-5 is a multi-factor, case-specific fair-use rule.
- Public personal information remains protected; public disclosure is not blanket consent.
- Sensitive information requires the separate Article 23 basis.
- Database rights can reach substantial extraction and qualifying repeated/systematic small extraction.
- The AI Basic Act imposes generative-AI notice/output marking and additional high-impact duties.
- Widely recognized, economically valuable identity signs have a defined UCPA protection path; general personality interests can exist without fame.

### Official guidance, not binding adjudication

- KCC’s 2026 AI-training fair-use guide.
- PIPC’s 2024 public-data AI guide and 2025 generative-AI lifecycle guide.
- Agency compliance examples and inspection recommendations.

### Proposal or reform direction, not current permission

- A dedicated TDM immunity/exception.
- General training-data disclosure beyond currently enacted AI Act requirements.
- Any broader statutory resolution of generative-AI training copyright conflicts unless a later enactment is identified.

### Analogy or unresolved application

- Whether a specific training run on public blog posts is fair use.
- Whether model weights themselves constitute a copy, a database extraction, or personal information in the particular architecture.
- Whether a person’s textual style, reasoning pattern, or signature phrases are an UCPA “identifying sign.”
- When a named persona exceeds the objectively recognizable scope of the author’s original public disclosure.
- How courts will weigh an emerging licensing market for author-specific AI personas.
- Whether output filters and deletion architecture materially change the Korean fair-use outcome.

## Unresolved facts requiring product-specific legal review

1. Who is the target, and are they domestically widely recognized or economically exploiting their identity/content?
2. Does the target own every post and media item, or are there employer, publisher, photographer, guest, comment-author, or platform rights?
3. Is collection from an author export, official API, ordinary public requests, or a path that bypasses login, blocks, rate limits, or technical controls?
4. What percentage and which qualitatively valuable part of the relevant database is extracted, and how frequently?
5. Does the corpus contain political views, beliefs, health, sex-life information, minors, or third-party personal information?
6. Is the model fine-tuned, retrieval-based, or prompt-only? Can it reconstruct sentences or identify training membership?
7. Is the service private, research-only, internal commercial, or public commercial? Does it substitute for reading/licensing the posts or for the author’s services?
8. Are name, portrait, voice, handle, signature phrase, or endorsements used in product naming and marketing?
9. Can a data-subject request remove the data from indexes, backups, vendors, and deployed model versions?
10. Are model/API providers processors, independent controllers, or overseas recipients under the actual contracts and flows?
11. Is the persona used for a high-impact sector or a consequential decision covered by the AI Basic Act?
12. Which version of each statute applies at collection, training, and launch, particularly if a pending reform is later enacted?

## Observations

- The strongest legal conclusion is layered: no single consent, fair-use theory, or AI disclosure clears every layer.
- The architecture affects legal exposure. Retrieval with item-level provenance and deletion is not automatically lawful, but it is easier to govern than irreversible author-specific fine-tuning.
- A real-person persona is qualitatively different from generic language-model training. It deliberately preserves identity linkage and invites users to attribute novel statements to the target.
- The 2026 KCC guide improves the quality of a fair-use assessment but also makes weak documentation less defensible because it identifies the factors a responsible developer should have considered.
- Sensitive-information screening should occur before embeddings or fine-tuning, not only at output time. Once included in weights, deletion and proof of non-use become materially harder.
- Avoid overstating UCPA. Its data and publicity-like clauses have specific elements, and the catch-all should not be used to privatize ideas or public-domain material.
- Avoid understating general personality rights. A non-famous person can still object to unauthorized impersonating or commercial identity use even when the statutory publicity-like clause does not apply.

## EXPAND

Use these leads for the next research wave only if the product design remains no-consent or public-facing:

1. Obtain the exact target blog URLs and preserve collection-method evidence; test public access without bypass and map robots, login, rate, and contractual controls in a separate platform-policy lane.
2. Commission a corpus audit that measures copied percentage and qualitative value against the relevant platform/database boundary, not merely against the target author’s posts.
3. Search post-2026-07-13 National Assembly enactments and Supreme Court/KCC updates for a TDM amendment or first Korean AI-training judgment before launch.
4. Seek PIPC interpretive consultation on Article 23 where the persona intentionally models beliefs, political views, health, or other sensitive traits.
5. Validate whether author-specific model weights permit extraction, membership inference, or substantial-expression regeneration; retain empirical results as part of the Article 35-5 and PIPA balancing record.
6. Review actual model-provider terms, processor roles, deletion guarantees, retention, and overseas-transfer destinations.
7. Test alternative designs—licensed source-linked RAG, anonymized topic assistant, or author-operated local model—against the same legal matrix.

## CLAIMS

| Claim ID | Atomic claim | Evidence type | Confidence | Important qualifier |
|---|---|---|---:|---|
| KR-COPY-001 | Public availability of a blog post does not eliminate copyright or create a general training license. | Statute; no public-web exception | High | Individual items may be unprotected facts/commonplace text or separately licensed. |
| KR-COPY-002 | Korea had no dedicated enacted TDM exception identified in the current Copyright Act as of 2026-07-13. | Current statute + MCST reform plan | High | Re-check later enactments at launch. |
| KR-COPY-003 | AI training is assessed, absent permission, under the fact-specific Article 35-5 fair-use framework. | Statute + 2026 official guide | High | No located Supreme Court holding squarely resolves generative-AI training. |
| KR-COPY-004 | KCC’s 2026 AI-training guide is non-binding and not a safe harbor. | MCST official express caveat | Very high | Courts can decide similar facts differently. |
| KR-COPY-005 | Commercial purpose or web crawling does not automatically preclude fair use. | MCST/KCC official guide characterization | High | They remain relevant within the overall balance; market substitution can be decisive. |
| KR-COPY-006 | Abstract style, ideas, and thought concepts are generally outside copyright, but actual expression and substantial structure remain protected. | Statute/case doctrine/KCC | High | AI-specific application to signature phrases and close paraphrase is fact-dependent. |
| KR-DB-001 | Database rights can reach a substantial part and qualifying repeated/systematic extraction of small parts. | Copyright Act Article 93 | Very high | The source must qualify as a protected database and the practical substantiality test must be met. |
| KR-DB-002 | A post author’s permission does not necessarily clear a platform database maker’s separate right. | Statutory separation of rights | High | Whether the platform has a right in the exact corpus is fact-specific. |
| KR-ACCESS-001 | Bypassing objective access or technical restrictions creates risks separate from copyright fair use. | Supreme Court 2021Do1533; UCPA | High | Do not infer that ordinary access to genuinely public pages is automatically unauthorized. |
| KR-PRIV-001 | Publicly available personal data remains personal data and requires a PIPA legal basis. | Supreme Court + PIPC + PIPA | Very high | Public disclosure and commercial purpose are factors, not categorical answers. |
| KR-PRIV-002 | Article 15(1)(6) legitimate interest requires necessity, a clearly prevailing interest, relation to purpose, reasonable scope, and safeguards. | PIPA + PIPC guidance | Very high | The controller must document the balance for the exact use. |
| KR-PRIV-003 | PIPA Article 23 sensitive information generally needs separate consent or express statutory authorization. | Statute | Very high | General legitimate interest does not independently clear Article 23. |
| KR-PRIV-004 | A named persona model is not pseudonymized as to the target merely because third-party identifiers are removed. | Statutory definition/application | High | Pseudonymization may still reduce risk for third parties and research datasets. |
| KR-ID-001 | UCPA protection for identity signs requires wide domestic recognition, economic value, unauthorized business use contrary to fair practice/competition, and economic harm. | Statute + KIPO official explanation | Very high | Ordinary bloggers may not meet the recognition/economic-value elements. |
| KR-ID-002 | General name, portrait, and personality interests can protect non-famous people against unauthorized impersonating or commercial use. | Supreme Court doctrine + official interpretation | High | Liability remains subject to purpose, proportionality, public interest, and balancing. |
| KR-ID-003 | No located Korean Supreme Court holding squarely decides whether textual style or “thinking pattern” used in an AI persona is an UCPA identifying sign. | Negative case-law finding | Medium-High | Actual name, image, voice, handle, signature phrase, or endorsement facts make the case stronger. |
| KR-AI-001 | A public generative-AI persona must notify users of AI operation and mark generated outputs under the AI Basic Act. | Current statute | Very high | Precise implementation follows current decree/guidance and service form. |
| KR-AI-002 | AI Basic Act compliance does not authorize copyrighted or personal-data training material. | Current Act’s scope + cumulative statutes | Very high | Copyright, PIPA, UCPA, contract, and database analyses remain independent. |
| KR-AI-003 | A persona chatbot is not high-impact solely because it imitates a person. | AI Basic Act categories | High | Covered consequential-sector deployment can trigger high-impact duties. |
| KR-RISK-001 | A no-consent, public, commercial named-person persona has high combined Korean-law risk. | Synthesis across independent regimes | High | This is a risk classification, not a per se illegality holding. |
| KR-DESIGN-001 | Express author permission, database/platform clearance, Article 23 screening, provenance, anti-memorization controls, deletion, and AI/non-endorsement labeling materially reduce risk. | Statutory duties + official guidance + design inference | High | None is individually sufficient; third-party rights and actual contracts still control. |
