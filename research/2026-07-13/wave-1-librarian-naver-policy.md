# Wave 1 - Naver Policy and Official Acquisition Surfaces

Observer: `/root/naver_policy_r2`  
Observed at: 2026-07-13  
Coverage: 40+ official-domain queries, current and previous terms, Help, Developers, NAVER API HUB, live robots and an empirical RSS sample.

## Key findings

1. Current and immediately previous Naver Terms prohibit automated collection of IDs/posts without Naver's prior permission. The restriction predates the 2025-07-10 revision.
2. The Search Collection Policy explicitly separates public visibility from permission for robot copying. Author permission over expression does not waive Naver's platform-access rule.
3. Author-enabled RSS is a narrow official exception for feed distribution and collection/search. Public materials do not extend it to persistent AI/RAG ingestion; current Blog robots explicitly signal the opposite purpose restriction.
4. Blog Search API is a query-based discovery/snippet interface: bounded pagination, non-guaranteed indexing, no full body and no documented per-owner corpus export.
5. Legacy and API HUB terms grant access, not ownership or a default right to warehouse, process or train on result data outside the approved scope.
6. Owner PDF backup is official but lossy and bounded. It needs reconciliation against an owner inventory and cannot be the canonical complete corpus by itself.
7. Lowest-risk order is owner-supplied originals outside Naver, written granular license, third-party clearance, owner PDF as audit evidence, and written Naver authorization before automated endpoint retrieval.

## Primary sources

- Current terms: https://policy.naver.com/rules/service.html
- Previous terms: https://policy.naver.com/rules/service_pre_20250710.html
- Search Collection Policy: https://policy.naver.com/policy/search_policy.html
- Blog robots: https://blog.naver.com/robots.txt
- RSS robots: https://rss.blog.naver.com/robots.txt
- Owner PDF backup: https://help.naver.com/service/5593/contents/15293?lang=ko&osType=PC
- Owner PDF workflow: https://help.naver.com/service/5593/contents/15295?lang=ko&osType=PC
- External-send/RSS setting: https://help.naver.com/service/5593/contents/15408
- RSS support: https://help.naver.com/service/5593/contents/24722?lang=ko&osType=COMMONOS
- Search exposure: https://help.naver.com/service/5593/contents/9564?lang=ko
- Legacy Blog Search API: https://developers.naver.com/docs/serviceapi/search/blog/blog.md
- Legacy API terms: https://developers.naver.com/products/terms/
- API HUB migration: https://developers.naver.com/notice/article/32530
- API HUB Blog Search: https://api.ncloud-docs.com/docs/naver-api-hub-search-blog
- API HUB terms: https://www.ncloud.com/policy/terms/opapi

## Contradictions and resolution

- Counter: RSS is an intentionally supported machine-readable surface. Resolution: yes for the described distribution/search scope; no affirmative AI training/RAG grant was found, and the live purpose-specific robots language is adverse.
- Counter: a consenting author owns their posts. Resolution: author-side copyright permission and Naver-side automated access permission are independent gates.
- Counter: an API key authorizes processing. Resolution: the documented API returns search results/snippets and the governing terms do not transfer result-data rights or grant an unrestricted corpus/training use.
- Counter: a public owner export API may exist. Resolution: no public official read/export API was found; this is an absence finding, not proof that no private arrangement exists.

## EXPAND

- LEAD: Ask Naver whether author-enabled RSS permits persistent storage, embeddings and RAG despite the AI/RAG robots language - WHY: public documents conflict by purpose - ANGLE: written product/legal clarification.
- LEAD: Ask whether a consent-based non-public owner export or licensed delivery exists - WHY: public owner PDF is lossy - ANGLE: enterprise/data partnership.
- LEAD: Determine the formal policy deployment date for the AI/RAG robots text - WHY: `Last-Modified` is operational metadata, not a changelog - ANGLE: archived official snapshots or Naver confirmation.
- DEAD END: no public official complete structured owner export found.
- DEAD END: Search API query combinations cannot recover omitted bodies or guarantee account completeness.
- DEAD END: API HUB migration does not broaden corpus-use rights.

## CLAIMS

- C10: Direct automated collection from Naver Blog endpoints requires prior Naver permission under current and prior terms; high risk, supported by two versions of first-party terms.
- C11: Author-enabled RSS is supported only within the stated feed distribution/collection/search scope; AI/RAG ingestion remains unresolved and requires written clarification.
- C12: Blog Search API is not a complete corpus export and its approval does not transfer result-data rights.
- C13: Owner PDF backup is authorized but lossy, bounded and unsuitable as the sole completeness proof.
- C14: Owner copyright consent, Naver platform permission, third-party rights and personal-data legal basis are separate gates.
