# Verify: Naver Access Surfaces

Observed: 2026-07-13 KST

## Scenario 1 - Blog robots

Invocation: `curl -sS -D - https://blog.naver.com/robots.txt`

PASS observable: HTTP 200 and explicit current directives captured.

Result: PASS. HTTP/2 200, `last-modified: Tue, 21 Oct 2025 11:29:58 GMT`. The response contains a comment that bot access for AI training and RAG is prohibited, followed by site-wide disallow rules for named AI/search bots. The generic `User-agent: *` section has path-specific disallows including `/export/`, `/post/`, `/npost/`, comments and previews.

## Scenario 2 - Blog section robots

Invocation: `curl -sS -L https://section.blog.naver.com/robots.txt`

PASS observable: HTTP 200 and directives captured.

Result: PASS. Named AI bots and generic `User-agent: *` are disallowed site-wide.

## Scenario 3 - Terms

Invocation: `curl -sS -L https://policy.naver.com/policy/service.html` and text extraction.

Result: PASS. Effective 2025-07-10. It states the poster retains IP, downstream users need a legal basis or rightholder permission, and users must not collect IDs/posts through automated means without prior permission or defeat anti-abuse measures.

## Scenario 4 - Official API and owner surfaces

- Blog Search API: 25,000 daily calls; `display` 1-100; `start` 1-1000; item `description` is a search-matched passage. It is not a full-content export.
- Owner PDF backup: 100 posts/PDF, 500MB/PDF, 3GB total, 20 PDFs; several attachment types are omitted and map/video become thumbnails.
- RSS notice: HTTP/1.0 support ended 2025-12-04; HTTP/1.1+ and HTTPS are recommended.

## Verdict

Technical access, platform permission, copyright permission, privacy basis, and corpus completeness are five separate gates. A successful fetch proves only that the response was reachable at the observation time.
