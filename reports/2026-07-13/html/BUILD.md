# Report build and verification

Requirements: Node.js 22 or newer. The lockfile pins the Markdown, browser-driver, PDF parser, and canvas versions.

```bash
cd output/report
npm ci
npx playwright install chromium
npm run verify
```

`playwright install chromium` installs the browser revision paired with the locked Playwright version. On a platform where that bundled browser is unavailable, set `REPORT_CHROME_PATH` to an explicitly managed Chrome/Chromium executable before `npm run verify`; the selected path and font state are recorded in `render-evidence.json`.

The build reads only the repository-owned, reviewed `SYNTHESIS.md` at its fixed path. It is a trusted local documentation input, not an upload or arbitrary Markdown service. Do not point the builder at user-supplied Markdown without adding an allowlist-based HTML sanitizer.

The scripts fail with a non-zero exit when expected headings, citations, sources, viewports, fonts, anchors, console state, page count, or PDF text markers regress. Render locks and same-filesystem atomic renames prevent readers from observing a partially written PDF or evidence directory.
