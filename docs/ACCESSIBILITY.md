# Accessibility

Target: WCAG 2.2 level AA. This is a self-assessment made during the hackathon, not a formal audit.

## What is implemented

| Area | Implementation |
|---|---|
| Keyboard | Every control is a native link, button, checkbox, `<details>` or `<dialog>`. A skip link is the first focusable element. Map rank markers are real `<button>` elements in the tab order; the map itself supports MapLibre's keyboard pan and zoom. |
| Focus | A 3 px high-contrast focus ring on every focusable element (`:focus-visible`). Opening an evidence panel moves focus to its heading; the Provenance drawer is a modal `<dialog>` that traps focus, closes with Escape and returns focus. |
| Not colour alone | Quality states use shape and pattern as well as colour: VALID = tick icon + solid border, CAUTION = triangle icon + dashed border + dots on the map, EXCLUDED / INSUFFICIENT = barred-circle icon + dotted border + diagonal hatching. Every state is also written as text. The motion colours are the colour-blind-safe Okabe–Ito orange and sky blue, with direction stated in the legend. |
| Map controls and legend | A native `<select>` for the motion layer, a `<details>` with real checkboxes for the other layers, a button group (with `aria-pressed`) for the basemap, and a legend whose symbols are all described in text. |
| Charts | The profile chart is an SVG with a text summary (`role="img"` and label) and gaps drawn for unobserved pixels; the acquisition timeline is an ordered list with text for each mark. |
| Text alternative to the map | A screen-reader summary of the map result (number of zones, top-ranked road, share of excluded pixels) and a full "Queue as a text table" page that contains the whole product without the map. |
| Semantics | Landmarks (`header`, `nav`, `main`, `aside`), one `h1` per view, ordered headings, tables with captions and scoped headers, lists for the queue, `role="alert"` for errors, `role="status"` for loading and notices. Page titles change per view. |
| Contrast | Computed with the WCAG formula (light theme): body text 15.8–17.3:1, muted 6.9–7.5:1, faint 5.0–5.4:1, links 6.1–6.7:1; chips: valid 5.2:1, caution 6.8:1, priority 4.9:1, info 8.0:1; sidebar text 15.6:1 and 8.8:1; queue badge 4.7:1. All text meets the 4.5:1 AA minimum. |
| Motion | `prefers-reduced-motion` removes transitions and makes map moves instant. Nothing auto-plays. |
| Zoom and reflow | Four layouts: desktop (≥ 1281 px), laptop, tablet (641–1100 px) and phone (≤ 640 px). At ≤ 960 px the sidebar becomes an off-canvas menu opened from a top bar (button with `aria-expanded`/`aria-controls`, closes with Escape, the backdrop or navigation). No horizontal scrolling at 375 px (checked by an end-to-end test on four pages); the map legend and attribution collapse on phones; touch targets in the menu are at least 44 px; charts are drawn at the container's real width so labels stay legible. |
| Language | `lang="en-GB"`. |
| High contrast | Borders are restored in forced-colours mode. |

## How it is tested

- `eslint-plugin-jsx-a11y` runs in `npm run lint`.
- Unit tests cover the skip link, tab order to the queue, opening evidence with Enter, focus management, the
  keyboard-operable layer toggles, and the presence of text for each legend symbol (`src/App.test.tsx`).
- The Playwright test opens evidence from a map marker, checks focus, and closes the drawer with Escape.

## Known gaps

- The raster layers themselves cannot be perceived non-visually; the text queue and summaries are the
  alternative, and they contain every number used in the ranking.
- Place-name labels and the motion raster are not exposed to assistive technology (decorative context).
- No testing with real screen-reader users, and no automated contrast audit, has been done.
- Target size of map rank markers is 28 px, above the 24 px AA minimum but below the 44 px AAA guideline.
