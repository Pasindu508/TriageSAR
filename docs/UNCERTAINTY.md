# Uncertainty

How TriageSAR handles what it does not know. Nothing in the application is called "confidence", because no
quantity here has a formally justified statistical meaning.

## Quality states

| State | Rule (defaults from `config/triagesar.toml`) | Treatment |
|---|---|---|
| EXCLUDED | no phase or coherence value; coherence < 0.30; connected component 0 or fill; product mask says fill, water or invalid sub-swath | not used, never interpolated, drawn as grey hatching, counted |
| CAUTION | 0.30 ≤ coherence < 0.50; or the pixel belongs to a connected component smaller than 2,000 pixels | used, flagged, drawn as yellow dots |
| VALID | everything else | used |

Each pixel also keeps a bit mask of *why* (`QualityReason`), and the API reports the count for each reason.
The cut-offs are screening values chosen for a prototype. They are not physical truths, and they were set
before any real data were inspected.

For each road corridor and each zone the application keeps the valid, caution and excluded pixel counts, the
valid fraction, a five-number coherence summary and the connected components involved. A corridor's card
label is VALID (at least 75% valid pixels), CAUTION (at least 50% usable) or INSUFFICIENT.

## Current NISAR caveats and what TriageSAR does about them

The demo granule belongs to `NISAR_L2_GUNW_PROVISIONAL_V1`. ASF describes provisional data as partially
validated. Its known-issues page for provisional products (updated 30 July 2026) lists, among others:

| Documented issue | Effect on GUNW | Mitigation in TriageSAR |
|---|---|---|
| Ionospheric effects | decorrelation bands and phase residuals, mainly at high latitudes | none applied (no ionosphere correction); stated in the UI; low coherence is excluded |
| Phase residuals where local geometric distortion is large | false phase in steep terrain | not corrected; steep-terrain caveat in the UI |
| Radio-frequency interference filtering | residual interference or removed features | not detectable here; relies on coherence gating |
| Incomplete raw data in about 1–2% of products | defocus and decorrelation | coherence gating; mask anomaly bits are counted and reported |
| Mixing product maturities | inconsistent calibration | one granule only is used |

Also relevant: a permanent instrument data gap from 27 July to 10 August 2026 (after this image pair), and
the earlier pre-calibration "beta" issues (ionosphere-layer artefacts, mask misalignment at frame edges).

## What is **not** quantified

- **Atmosphere.** Tropospheric delay can produce centimetre-scale apparent motion over tens of kilometres.
  GUNW ships troposphere layers but does not remove them from the phase, and neither does TriageSAR. The
  robust (MAD-based) threshold raises itself when the scene is noisy, but it cannot tell atmosphere from
  ground motion.
- **Unwrapping errors.** A missed cycle shifts a region by half a wavelength (about 12 cm). Referencing each
  connected component separately removes offsets *between* components, not errors *within* one.
- **Geometry.** One line of sight. North–south motion is nearly invisible.
- **The reference level.** Values are relative. Zones use a local 4 km reference, so motion that is smooth over
  several kilometres is not reported as a zone however large it is; the scene-relative layer shows it.
- **Road data.** OpenStreetMap may miss or misplace roads. Road-crossed pixels with no usable observation are
  reported as a share ("unobserved roads") so that silence is not read as safety.

## Checks that are available

- **Masking ablation**: the same pipeline with every pixel treated as valid; the change in zone count, zone
  area and top-ranked roads is shown in the scene summary.
- **Ranking sensitivity**: ±20% weight perturbations; UNSTABLE label when the top item changes too often.
- **Reference-product consistency** (`scripts/evaluate_reference.py`): correlation, differences and zone
  overlap against the NASA/JPL map of the same pair. Both come from the same radar data, so agreement shows
  consistent processing, not agreement with the ground.

## The first real run, and what changed because of it

Disclosed in full because it is a change of method made after seeing real data.

**What happened.** The first analysis of the real 13–25 June 2026 pair used the original reference: each
unwrapped region minus its study-area median, with a threshold of `max(3 cm, 3 × robust σ)` of that field. The
coastal range had moved as a block by up to about 35 cm relative to the rest of the scene, so the robust σ was
large, the threshold rose to 46 cm, and no zone was found. Without the quality gate, the same rule found 17
zones over 104 km², which shows the rule was measuring the broad earthquake field and noise, not local
anomalies.

**What was changed.** The reference used for zones and ranking became a local plane fitted to each pixel's
surroundings (4 km window, same unwrapped region). The window was chosen to be several times wider than a road
corridor (500 m) and the smallest zone (about 0.7 km across), and much narrower than an earthquake's regional
field. The threshold rule, the 3 cm floor, the 0.5 km² minimum, the coherence cut-offs and the weights were
**not** changed. The original method remains selectable in `config/triagesar.toml`, and a regression test
reproduces its failure on a synthetic scene with a broad regional field.

**What it means.** The local reference cannot see motion that is smooth across several kilometres. That is a
deliberate choice (smooth motion is less likely to harm roads than abrupt motion), but it is a choice, and a
road crossing a wide, gently deforming zone would not be ranked.

**Result after the change.** Local scatter 0.54 cm; threshold 3 cm (floor); 3 zones of 0.6–0.9 km², mostly
CAUTION quality; none within 1 km of a mapped road; queue empty. The numbers are in `BUILD_REPORT.md`.

## Per-event notes

| Event | Pair length | Excluded pixels | Notes |
|---|---:|---:|---|
| Venezuela | 12 days | 49% | Smooth regional motion; local scatter 0.54 cm; consistency with NASA/JPL r = 0.991 |
| Kumamoto | 24 days | 41% | Longer pair, more decorrelation and non-seismic change; ranking UNSTABLE (top item changes in 42% of weight perturbations) |
| Panama | 12 days | 84% | Partial frame (`_P_` in the granule name) plus vegetation; threshold set by the robust rule (3.1 cm); all ranked roads carry CAUTION evidence |
| Flores | 12 days | 47% | Offshore epicentre; no zone on land |
