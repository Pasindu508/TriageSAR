# TriageSAR

**From NISAR surface motion to an evidence-ranked infrastructure inspection queue.**

## Summary

**The problem.** After a major earthquake, emergency planners cannot inspect every road at once. NISAR can
show where the ground moved, but an interferogram is hard to read and a displacement map does not say where
to send the first field team.

**What we built.** TriageSAR is an open-source application that reads a real NISAR GUNW interferogram, rejects
or flags low-quality radar pixels, finds contiguous zones of ground motion, intersects them with roads, and
produces a ranked inspection queue. Every item opens an evidence card: observed line-of-sight motion,
coherence, share of valid pixels, extent, source granule, acquisition dates and limitations.

**How NASA data are used.** The NASA–ISRO NISAR Level-2 Geocoded Unwrapped Interferogram is the scientific
input, discovered through the ASF Search API and accessed with NASA Earthdata Login. Phase is converted to
line-of-sight range change using the wavelength in the product's own metadata. The product's coherence,
connected-component and mask layers drive a three-state quality gate (VALID, CAUTION, EXCLUDED). The case
studies are four real interferograms that bracket 2026 earthquakes: northern Venezuela (M 7.5, 24 June),
Kumamoto, Japan (M 6.8, 28 July), Flores Sea, Indonesia (M 7.8, 14 August) and the Azuero Peninsula, Panama
(M 7.7, 9 October).

**What makes it different.** Most SAR tools stop at the map. TriageSAR is the decision layer after the map,
and it is built to be audited: a deterministic score that is the weighted sum of six visible factors, a
sensitivity test that labels the ranking stable or unstable, a quality gate whose rules and thresholds are in
one configuration file, and provenance from each number back to the granule and the command that produced
the fixture. There is no machine learning and no language model in the ranking.

**What is demonstrably working.** The full pipeline runs on four real NISAR GUNW products, each discovered in the
live ASF catalogue and cropped remotely with Earthdata Login, and the dashboard serves them offline. In Kumamoto
it finds 16 zones under a dense road network and ranks the Kyushu Expressway first, while flagging the ranking as
unstable. In Venezuela it finds three small zones away from roads and ranks nothing, saying why. Where we could
check against an independent processing (NASA/JPL's Venezuela map) our values agree at r = 0.991. Figures:
`BUILD_REPORT.md`.

## What it is not

TriageSAR is **not a damage assessment**. It does not detect structural damage, does not predict casualties,
and does not treat satellite observations as ground truth. Its output is an inspection priority: a reasoned
order in which to send people to look. It has not been compared with field inspection results.

## How it works

1. **Read** unwrapped phase, coherence, connected components and mask from the GUNW product, unchanged.
2. **Convert** phase to line-of-sight range change: Δr = λφ / 4π.
3. **Quality-gate** every pixel. Excluded pixels are shown as unobserved and are never interpolated.
4. **Reference** each pixel to a plane fitted to its surroundings, so only motion that differs locally counts.
5. **Extract zones** of contiguous, quality-approved motion above a screening threshold.
6. **Intersect** zones with OpenStreetMap roads and summarise the evidence in a corridor along each road.
7. **Rank** with a transparent weighted sum, and test the ranking against ±20% changes in the weights.

## Impact

A planner gets a short, explained list instead of a raster: which road segments have the strongest satellite
evidence of ground motion, how good that evidence is, and which roads the radar could not see at all. The same
approach applies to any NISAR interferogram over any road network, and NISAR images most land every 12 days.

## Scientific integrity

- No fabricated numbers: values that were not computed are shown as "not computed".
- No correction is applied silently; available correction layers are listed as not applied.
- Uncertainty is drawn on the map (dots and hatching) and counted on every card.
- An ablation shows what the quality gate changes; a consistency evaluation against the NASA/JPL displacement
  map of the same image pair (r = 0.991) is described as consistency, not validation.
- A change of method made after the first real run is disclosed in `docs/UNCERTAINTY.md`.
- Limitations are documented in full in `docs/LIMITATIONS.md`.

## Technology

Python 3.12 (NumPy, SciPy, h5py, Rasterio, Shapely, pyproj, FastAPI, Pydantic) and TypeScript (React, MapLibre
GL JS, TanStack Query, Vite). Tests: pytest, Vitest, Playwright. Apache-2.0.

## Next steps

Atmospheric correction and a second viewing geometry; comparison with the OPERA Sentinel-1 displacement
products; authoritative road and bridge inventories; and, most importantly, feedback from real inspections to
learn whether the ranking helps. A learned model should only be considered after that evidence exists.

## Data and resources

NISAR L2 GUNW (NASA/ISRO, ASF DAAC); USGS earthquake catalogue; OpenStreetMap (© OpenStreetMap contributors,
ODbL). Full list with URLs and access dates: `submission/REFERENCES.md` and `DATA_SOURCES.md`.
