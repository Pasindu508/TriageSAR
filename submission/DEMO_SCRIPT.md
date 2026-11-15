# Demo script: exact clicks and expected screen state

Preparation: `make start`, open http://localhost:8000 at 1440 × 900 or larger, with a network connection if you
want the Terrain basemap (everything else works offline). http://localhost:8000/health should report
`"events_ready": 4`. Total time: about three minutes. Every number below is from `BUILD_REPORT.md`.

**Story.** Four real earthquakes, one method. Kumamoto shows the queue doing its job; Venezuela shows it
refusing to invent priorities; the quality gate and provenance show why it can be trusted.

| # | Action | Expected screen | Say |
|---|---|---|---|
| 1 | Open `/`, then **Case studies** in the sidebar | Four cards, each **FIXTURE READY**: Venezuela, Kumamoto, Panama, Flores. | "Four 2026 earthquakes, each bracketed by a real NISAR interferogram." |
| 2 | Click **Kumamoto Region earthquake** | Dashboard. KPIs: 16 zones, 936 roads to inspect, 25% road pixels unobserved, 37% valid pixels. Map on Terrain: orange/blue motion, hatching, white zone outlines, red numbered road markers. Queue: #1 九州自動車道 (E3), 68.5 priority, CAUTION; a yellow **RANKING UNSTABLE** chip. Evidence strip for #1 below. | "The Kyushu Expressway crosses the largest zone for almost 10 km. It ranks first, but the panel says the ranking is unstable: the top three are within three points." |
| 3 | Point at the evidence strip | Thumbnail, summary, profile chart along the road with the ±3 cm band, NISAR acquisition timeline (21 Jul and 14 Aug filled, earthquake diamond on 28 Jul), key evidence, 31% valid pixels, priority 68.5. | "Every number here was measured; the chart shows the motion along the road, with gaps where the radar saw nothing." |
| 4 | Click **Review evidence** | Drawer: "This is not a damage assessment", four statistics, quality bar, **Why is this ranked #1?** | Open the table: "Six factors, their weights, their points. They add up to 68.5." Press Esc. |
| 5 | Switch the **Motion layer** to *Local motion*, then back | Speckled local field; zones stand out. | "Zones are patches that move differently from their surroundings by 3 cm or more." |
| 6 | Choose **Northern Venezuela** in the case-study selector | KPIs: 3 zones, **0 roads to inspect**, 20% unobserved. Queue: **No road is ranked**, then three zone cards with their nearest road (1.3 km at best). | "A magnitude 7.5, and TriageSAR ranks nothing: the coastal range moved as one block, and the three local patches are more than a kilometre from any mapped road. It says so, and that this is not a clearance." |
| 7 | Open **Scene summary and quality gate** | "Without quality gate: 117 zones … and 76 ranked road segments instead of 0." | "Without the quality gate this would have been 76 'priorities', almost all noise." |
| 8 | Sidebar **Provenance** | Drawer: one section per case study with granule, dates, product version, crop window, build command, checksums. | "Against NASA/JPL's own map of the Venezuela pair our values correlate at 0.991." |
| 9 | Sidebar **Inspection queue** | Text tables of the ranked roads and the zones. | "The whole product works without the map." |
| 10 | Sidebar **Limitations** | "What this tool cannot tell you". | One viewing direction, no atmospheric correction, smooth motion deliberately ignored, never compared with inspections. |

## If asked about Panama or Flores

- **Panama:** 84% of the frame is unobserved (partial frame, vegetation); 18 zones and 72 ranked roads, all with
  CAUTION evidence, and 63% of road pixels unobserved. Present it as weak evidence, which is what the app shows.
- **Flores:** the epicentre was offshore; no zone on land, 0 roads ranked, only 3% of road pixels unobserved.

## Keyboard-only variant

Tab once: "Skip to main content". Tab to a queue or zone card and press Enter to select it; tab to **Review
evidence** and press Enter: focus moves to the evidence heading; Esc closes. Map rank markers are buttons.
