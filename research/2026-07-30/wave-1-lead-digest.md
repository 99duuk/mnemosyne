# Wave 1 Lead Digest

This digest records material messages received before workers completed their full memos. Each is a lead, not a final verified conclusion.

## Naver access

- Official NAVER API HUB Blog search documentation was reported to expose search-result metadata, not Blog post bodies or per-blog export.
- Official NAVER notice `https://developers.naver.com/notice/article/32530` was reported to change Search API migration timing. The direct primary notice must be rechecked before use.
- Direct leader search corroborated an official NAVER policy page: `https://policy.naver.com/policy/disclaimer.html` describes a narrow set of conditions for automated collection.
- Direct leader search found an important distinction: `https://help.naver.com/service/5593/contents/15183` says Blog data transfer/backup/ownership transfer is unavailable between same-name IDs, while `https://help.naver.com/service/5593/contents/15293` documents PDF backup of directly authored posts.

## Collection boundary

- `naver_access` directly observed `https://blog.naver.com/robots.txt` and reported explicit AI-training/RAG wording and disallow rules. The separate `robots_boundary` expansion lane was opened to avoid overreading robots.txt as a complete legal conclusion.
- Apple documentation reports user-initiated Safari Share and Shortcuts web-page inputs. This can reduce manual friction but cannot create permission that platform policy or rights holders have not granted.

## Architecture and evaluation

- The RAG architecture and evaluation workers opened dedicated lanes for provenance, temporal metadata, citations, abstention, and evaluation.
- The implementation-pattern worker raised the specific warning that citation prompt formatting alone does not verify citation entailment; a dedicated citation-auditing expansion lane was opened.

## Artifact audit

- `prior_artifacts` identified the prior substantive session at `/home/akinella/workspace/.omo/ulw-research/20260713-071314/` and rendered report evidence under `/home/akinella/workspace/.omo/evidence/naver-persona-report/`.

## Expansion markers received verbatim

- LEAD: NAVER API Hub migration notice — WHY: historical Search API docs may not be a stable integration path — ANGLE: validate current new-project access and terms.
- LEAD: NAVER Blog robots AI-training/RAG directive — WHY: automation design may be expressly restricted — ANGLE: distinguish robots, contract, copyright, and manual capture.
- LEAD: Native Blog backup/transfer paths — WHY: owner-first acquisition may be feature-limited — ANGLE: reconcile per-post PDF backup with non-transferability.
- LEAD: Citation verification — WHY: apparent citations can be unsupported — ANGLE: use entailment/completeness evaluation rather than format checks.
