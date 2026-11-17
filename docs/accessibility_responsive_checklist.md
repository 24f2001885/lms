# Accessibility and responsive checklist

Automated checks (`make a11y` and `make test-ui`) run alongside this manual verification log. Record date, tester, browser, and pass/fail notes for every cell before the viva.

## Responsive matrix

| Width / Browser | Admin (`dashboard`, `examinations`, `examination_detail`, `rubrics`, `bookings`, `charts`) | Examiner (`dashboard`, `slot_form`, `evaluation_form`) | Student (`examinations`, `booking_modal`, `bookings`, `results`) | Public (`login`, `register`) |
|---|---|---|---|---|
| **320 px** (Chrome / Edge / Firefox) | [ ] Pass / Note: | [ ] Pass / Note: | [ ] Pass / Note: | [ ] Pass / Note: |
| **375 px** (Chrome / Edge / Firefox) | [ ] Pass / Note: | [ ] Pass / Note: | [ ] Pass / Note: | [ ] Pass / Note: |
| **768 px** (Chrome / Edge / Firefox) | [ ] Pass / Note: | [ ] Pass / Note: | [ ] Pass / Note: | [ ] Pass / Note: |
| **1024 px** (Chrome / Edge / Firefox) | [ ] Pass / Note: | [ ] Pass / Note: | [ ] Pass / Note: | [ ] Pass / Note: |
| **1280 px** (Chrome / Edge / Firefox) | [ ] Pass / Note: | [ ] Pass / Note: | [ ] Pass / Note: | [ ] Pass / Note: |

## Verification checklists

### Keyboard
- [ ] Every interactive control is reachable and operable via `Tab`, `Shift+Tab`, `Enter`, `Space`, and arrow keys.
- [ ] Visible 3 px focus ring (`#0B5ED7` on light backgrounds, `#FFFFFF` on dark navigation) on every focusable element.
- [ ] First `Tab` stop reveals "Skip to main content" and `Enter` moves focus to `<main id="main-content" tabindex="-1">`.
- [ ] Booking/delete modals and the Admin off-canvas drawer trap focus while open, close on `Escape`, and return focus to the trigger button.

### Screen reader spot checks (NVDA / VoiceOver)
- [ ] Meaningful `<title>` and single `<h1>` announced on navigation.
- [ ] Heading outline (`h1` -> `h2` -> `h3`) never skips levels downward.
- [ ] Landmarks (`header`, `nav` with `aria-label`, `main`, `footer`) are listed cleanly.
- [ ] Form labels (`(required)` / `(optional)`), help text, and `Error:` feedback are announced via `aria-describedby` and `aria-invalid="true"`.
- [ ] Stacked data tables (`.table-stack`) preserve `role="table"`, `role="row"`, `role="columnheader"`, and `role="cell"` semantics below 576 px.
- [ ] Chart cards expose an accessible `<details>` data table fallback (`View data as table`).
- [ ] Flash alerts are announced once via `aria-live="polite"` and `role="alert"`.

### Zoom and reflow
- [ ] 200% and 400% browser zoom and 320 CSS px viewport width produce zero horizontal page scrollbars.
- [ ] Long email addresses, course codes, and examination titles wrap cleanly (`overflow-wrap: anywhere`).

### Colour and contrast
- [ ] Body, muted (`#5C636A`), link (`#1F4E79`), badge (`#FD7E14` / `#0DCAF0` with dark text `#212529`, amber outline `#7A5C00`), and error (`#B02A37`) pairs meet >= 4.5:1 contrast.
- [ ] Form borders (`#6C757D`) and focus rings (`#0B5ED7` / `#FFFFFF`) meet >= 3.0:1 non-text contrast.
- [ ] Status badges and active links never rely on colour alone (text labels, underlines, or left borders are always present).

### Motion, text spacing, touch & forms
- [ ] `prefers-reduced-motion: reduce` disables chart animations and CSS transitions (`0.01ms`).
- [ ] WCAG 1.4.12 text spacing (`line-height: 1.5`, `letter-spacing: 0.12em`, `word-spacing: 0.16em`, paragraph spacing `2em`) clips no text.
- [ ] Touch targets below 768 px are at least 44x44 CSS px.
- [ ] Invalid form submission focuses `[data-error-summary]` with links to each invalid field.

## Known limitations and decisions
- **Admin sidebar**: Collapses into a Bootstrap `offcanvas-lg` drawer below 992 px (covering both `xs`/`sm` and `md` collapsible requirements) and stays a static 240 px column from 992 px upward.
- **Responsive tables**: Data tables transform into labelled cards (`.table-stack` with `td::before` reading `data-label`) below 576 px and use `.table-responsive` horizontal scrolling on `sm` and `md`.
- **Charts**: Require JavaScript (`Chart.js` vendored locally) with an expandable HTML data table and `<noscript>` JSON link fallback.
- **Test-taking pages (Tier 3)**: Optimised for desktop browsers and built only after Gate B.
