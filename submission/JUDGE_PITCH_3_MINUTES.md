# Judge pitch: 3 minutes

Every number below is from the real run (`BUILD_REPORT.md`). Do not quote others.

## 0:00–0:25 · Problem

"After a major earthquake a road agency cannot inspect everything first. On 24 June 2026 an M 7.2 and an M 7.5
earthquake struck northern Venezuela about half a minute apart. Satellite radar can show where the ground
moved. The gap is between that picture and a decision: which road, in what order, and how much should I trust
the evidence?"

## 0:25–0:50 · Why NISAR, why now

"NISAR's calibrated L-band data became public this year, and the Level-2 GUNW product arrives unwrapped and
geocoded. We use one product: ascending track 162, frame 7, 13 and 25 June. We read only a 14-megabyte window
of the 2.3-gigabyte file, remotely, and keep every value exactly as distributed."

## 0:50–1:40 · Demo

*Start with Kumamoto (case-study selector): 16 zones; 936 road segments ranked; #1 Kyushu Expressway (E3),
68.5, CAUTION; RANKING UNSTABLE because the top three are within three points. Open the evidence strip and
"Why is this ranked #1?". Then switch to Venezuela for the steps below.*

1. **Surface motion.** "The coastal range moved away from the satellite by up to tens of centimetres, relative
   to the rest of the scene. That is the earthquake's broad deformation."
2. **Uncertainty.** "Hatching is excluded: water, low coherence, failed unwrapping. Forty-nine per cent of this
   scene. We do not interpolate across it."
3. **Local motion.** "What stresses a road is motion that differs from its surroundings. We compare every
   pixel with a plane fitted to the 4 km around it. The local scatter is about half a centimetre; our
   threshold is 3 cm over at least half a square kilometre."
4. **Zones.** "Three patches pass, each under a square kilometre, mostly of moderate radar quality. The nearest
   is 1.3 km from a mapped road. So no road is ranked, and the interface says exactly that."
5. **Scene summary.** "A fifth of road pixels are unobserved. Without the quality gate: 117 zones and 76
   'priorities'."
6. **Provenance.** "Granule, dates, product version, crop window, checksums, the command that built it."

## 1:40–2:25 · How we kept it honest

- "The wavelength comes from the product's metadata; the code refuses to assume one."
- "No atmospheric correction is applied, and the interface says so."
- "Against NASA/JPL's displacement map of the same pair: correlation 0.991 over 700,000 pixels, RMSE 3.9 cm.
  That also confirmed our sign convention. It is the same radar data, so it is consistency, not ground truth."
- "One thing we changed after seeing real data: zones first used motion relative to the whole scene, and
  because the whole range moved, that found nothing. We switched to the local reference, kept every threshold
  and weight as written, and documented it."

## 2:25–2:50 · Limits, stated plainly

"One viewing direction, so north–south motion is nearly invisible. Motion that is smooth over kilometres is
deliberately not a zone. A provisional product. And no one has yet compared this with what inspectors found."

## 2:50–3:00 · Close

"Portals show experts the raster. TriageSAR is the layer after the map: evidence, quality and provenance,
turned into an inspection order anyone can audit, even when the honest answer is that nothing stands out."
