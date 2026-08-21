# Final runtime audit

Observed: 2026-07-13 KST

## Hypotheses and distinguishing evidence

1. **Source-to-HTML transformation silently omits required content.** Refuted: the source has eight major H2 sections; generated HTML has all eight mapped sections, 40 H2/H3 headings, 38 unique source anchors, 49 citation links and three captioned tables. Build assertions also require exactly one tuning-condition list and two semantically breakable completeness identifiers.
2. **The browser renderer exits successfully despite a viewport, font, anchor, console or cleanup failure.** Refuted: a fresh Chromium 149.0.7827.55 run reports `scrollWidth == clientWidth` at 375/768/1280 and 200% zoom, Korean font loaded, Source 1 anchor visible, zero console/page errors, and no remaining browser/render process or lock/temp/backup file.
3. **PDF generation silently loses Korean text, a page or a repaired section.** Refuted: PDF.js loaded and rendered 17 pages; required acquisition, RAG, generation, threat, evaluation, deletion, operations and robots markers are present; NUL/tofu/replacement-character count is zero. Two independent reviewers inspected HTML 4/4 and PDF 17/17 and returned PASS/HIGH.
4. **The HTML build is stale or nondeterministic.** Refuted: three consecutive builds produced SHA-256 `641d9d8e91e5f8389f3641a46c73e116e0fa5cee0d8c8aa3438eeec9e0be1e00`; final HTML, PDF and evidence mtimes postdate their content, builder and CSS inputs.

## Final evidence

- `npm audit --omit=dev --audit-level=high`: 0 vulnerabilities.
- Node syntax checks: all three `.mjs` files pass.
- HTML SHA-256: `641d9d8e91e5f8389f3641a46c73e116e0fa5cee0d8c8aa3438eeec9e0be1e00`.
- PDF SHA-256: `2aed57e68c6cbde72b3a708e6925a06747a899cfbd3ccdc23b85c8e4d002d2f2`.
- Extracted PDF text SHA-256: `87b13bb6441ee868c7435cf896b9ecd1772ae81f6322633a2f00ac444f974b4f`.

Verdict: **PASS**. These checks validate the research-report pipeline and delivered artifacts, not an unbuilt real persona service or an unperformed target-corpus deletion drill.
