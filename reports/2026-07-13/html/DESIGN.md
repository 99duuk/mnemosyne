# Persona Proxy Research Report Design System

## 0. Research Log

- Embedded refs: shortlisted `notion.md`, `wired.md`, `claude.md` -> picked `minimalist-skill.md` + `notion.md` because this is a long Korean technical report that needs paper-like warmth, strong hierarchy, and quiet evidence surfaces rather than a marketing aesthetic.
- Lazyweb: ran 2 desktop queries (`technical research report documentation`, `legal compliance report knowledge base`), viewed 0 screens because the read-only endpoint returned `MCP_PRO_REQUIRED`; no purchase or bypass was attempted.
- Imagen drafts: skipped. This is a dense, print-first technical document rather than an expressive product surface; a raster concept would add no information and would weaken PDF accessibility and reproducibility.
- Distinctive direction: a calm evidence dossier on warm paper. The signature is the repeated “gate” language: restrained navy rules, dated source labels, and clearly separated allowed/blocked decisions.

## 1. Atmosphere & Identity

The report must feel like a careful technical and legal dossier: calm, explicit, and inspectable. Warm paper surfaces and whisper borders reduce fatigue; navy is reserved for links, focus, and verified structure; amber and red appear only for uncertainty and stop conditions. The memorable moment is the opening decision panel that makes the safe product boundary unmissable.

## 2. Color

| Role | Token | Value | Usage |
|---|---|---:|---|
| Canvas | `--surface-canvas` | `#f4f1ea` | Browser surround |
| Paper | `--surface-paper` | `#fffdfa` | Main report |
| Soft | `--surface-soft` | `#f7f4ee` | Alternate sections, code |
| Code surface | `--surface-code` | `#f1eee7` | Code/schema blocks |
| Ink | `--text-primary` | `#242321` | Headings and body |
| Muted | `--text-secondary` | `#625f59` | Metadata and captions |
| Code ink | `--text-code` | `#302f2c` | Code/schema text |
| Border | `--border-default` | `#ded9cf` | Whisper divisions |
| Accent | `--accent-primary` | `#184e77` | Links, verified markers, focus |
| Accent hover | `--accent-hover` | `#123c5c` | Link hover |
| Success | `--status-success` | `#276749` | Allowed / verified |
| Warning | `--status-warning` | `#8a5a12` | Conditional / provisional |
| Error | `--status-error` | `#9b2c2c` | Stop / blocked |

Rules: color communicates status or interaction only. The print version keeps all status distinctions legible in grayscale through labels, borders, and text.

## 3. Typography

| Level | Size | Weight | Line height | Usage |
|---|---:|---:|---:|---|
| Display | `clamp(2rem, 4.8vw, 3.5rem)` | 760 | 1.12 | Report title |
| H1 | `2rem` | 740 | 1.2 | Major chapter |
| H2 | `1.45rem` | 700 | 1.3 | Section |
| H3 | `1.1rem` | 680 | 1.45 | Subsection/card |
| Lead | `1.08rem` | 450 | 1.75 | Executive summary |
| Body | `1rem` | 400 | 1.72 | Reading text |
| Small | `0.875rem` | 450 | 1.55 | Captions and metadata |
| Mono | `0.86rem` | 430 | 1.62 | Code and schemas |

- Primary and code-safe CJK fallback: bundled `Report Noto Sans KR` 400/700 (SIL OFL 1.1), then `Noto Sans KR`, `Apple SD Gothic Neo`, `Malgun Gothic`, system sans-serif. Code blocks prioritize this bundled face because a missing system CJK monospace must never produce tofu.
- Display: the same bundled family at 700. This avoids a system-dependent Korean serif fallback and guarantees consistent HTML/PDF glyph coverage.
- Mono: `D2Coding`, `Noto Sans Mono CJK KR`, `DejaVu Sans Mono`, monospace.
- Korean body copy uses `word-break: keep-all`, `overflow-wrap: break-word`, and balanced headings where supported.

## 4. Spacing & Layout

Base unit is 4px. Tokens: `--space-1` 4px, `--space-2` 8px, `--space-3` 12px, `--space-4` 16px, `--space-5` 20px, `--space-6` 24px, `--space-8` 32px, `--space-10` 40px, `--space-12` 48px, `--space-16` 64px, `--space-20` 80px.

- Browser max width: 1120px; readable measure: 74ch.
- Mobile: 375px single column, 20px outer gutter.
- Tablet: 768px single content column with two-column summary cards.
- Desktop: 1280px fixed table of contents rail plus reading column.
- Print: A4, 17mm side margins, 18mm top and 20mm bottom; tables and code blocks avoid splitting when practical.

## 5. Components

### Report navigation

- Structure: landmark `<nav>` with chapter anchors.
- States: default, hover underline, focus 3px navy outline, current section via `aria-current` when scripted; no disabled/loading states because the document is static.
- Responsive: sticky rail on desktop; compact horizontal index on narrow screens.

### Decision callout

- Structure: semantic section with eyebrow, verdict, rationale, and scope label.
- Variants: allowed, conditional, blocked.
- States: static; status is expressed by text plus color, never color alone.

### Evidence card

- Structure: heading, claim, evidence class, qualification.
- Variants: verified, provisional, design-only.
- States: static; links receive hover/focus states.

### Decision table

- Structure: captioned `<table>` with real headers and responsive scroll wrapper.
- Variants: standard, compact.
- States: keyboard-focusable wrapper on narrow screens; print expands at full width.

### Code/schema block

- Structure: labeled `<pre><code>` with wrapping disabled in browser and enabled in print when required.
- States: focusable for keyboard scrolling; no copy button to keep the report JavaScript-free.

### Source list

- Structure: ordered list with source title and direct URL. The shared research/access date appears once in the report header; issuer/type is encoded in the source title where needed rather than repeated as unverifiable metadata.
- States: visible underline on hover and focus; URLs remain printable.

## 6. Motion & Interaction

No decorative motion. Anchor scrolling uses the browser default. Link and focus transitions use only color and outline over 120ms; `prefers-reduced-motion` disables smooth behavior if it is enabled by the user agent. The report remains fully usable with JavaScript disabled.

## 7. Depth & Surface

Strategy: borders-only with tonal shift. Paper sits on a warm canvas; sections alternate between paper and soft surfaces; cards use one-pixel borders and no shadows. This preserves print fidelity and avoids decorative depth that competes with evidence.

## 8. Accessibility Constraints & Accepted Debt

- Target: WCAG 2.2 AA, 4.5:1 body contrast, visible keyboard focus, semantic landmarks and tables, meaningful link text, 200 percent zoom without horizontal page overflow except intentional code/table scroll regions.
- Personas: Korean mobile reader at 375px; legal/engineering reviewer scanning sources at desktop; low-vision reader at 200 percent zoom; print/PDF reader who needs selectable Korean text and page numbers.
- COGA: plain labels (`허용`, `조건부`, `중단`), one idea per paragraph, reasons adjacent to decisions, no unexplained aggregate score.

### Accepted Debt

| Item | Location | Why accepted | Owner / Exit |
|---|---|---|---|
| None | - | Critical and major findings must be fixed before delivery. | - |
