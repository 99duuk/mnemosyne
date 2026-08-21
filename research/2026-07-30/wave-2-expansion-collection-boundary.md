# Wave 2 Expansion: Collection Boundary

## Lead L-02: robots and automated access

- Direct worker observation of `https://blog.naver.com/robots.txt` reported AI-training/RAG-specific agent restrictions.
- Direct leader observation of [NAVER's legal notice](https://policy.naver.com/policy/disclaimer.html) independently states that automated access/collection is prohibited outside explicit permission/pre-approval, compliant API use, or permitted guide/robots scope.
- Resolution: robots.txt is a machine-readable technical directive, not the complete legal analysis. The implementation consequence is still decisive: no autonomous crawler is a default input path. Only exact written permission can open a new collection-design review.

## Lead L-03: owner acquisition path

- [NAVER's Blog transfer help](https://help.naver.com/service/5593/contents/15183?lang=ko&osType=COMMONOS) says Blog data transfer/backup/ownership transfer is unavailable even between same-name IDs.
- [NAVER's Blog backup guide](https://help.naver.com/service/5593/contents/15293?lang=ko&osType=PC) and [PDF procedure](https://help.naver.com/service/5593/contents/15295?lang=ko&osType=PC) independently document an owner-operated per-post PDF backup flow.
- Resolution: no account-transfer/archive claim. An owner can provide a PDF snapshot of directly authored posts, within documented limits; it is an lossy evidence source, not a general third-party export API.

## Lead L-04/L-06: manual capture boundary

- [Apple Shortcuts](https://support.apple.com/en-gb/guide/shortcuts-mac/apd7644168e1/mac) and [Safari Share](https://support.apple.com/en-euro/guide/safari/sfri40722/mac) document user-mediated webpage/article/PDF handoff.
- Resolution: user action can reduce clerical effort only after a collection path is authorized. It cannot cure a missing platform permission, copyright basis, privacy basis, or identity consent.

## EXPAND

none - source discovery produced no separate, documented NAVER Blog body-export/API route in reviewed official pages. This is recorded as a limited counter-search result, not proof that no such route exists anywhere.
