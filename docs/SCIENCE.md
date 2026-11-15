# Science

A plain-language account of what TriageSAR measures and how. Sources are listed in
`submission/REFERENCES.md`; the code is in `science/triagesar/`.

## SAR

A synthetic aperture radar (SAR) sends microwave pulses to the ground and records the echo. Each pixel of a
SAR image holds an amplitude (how strongly the ground reflects) and a phase (where in its wave cycle the echo
arrives). NISAR's L-band radar has a wavelength of roughly 24 cm, which passes through much vegetation and
stays coherent longer than shorter wavelengths.

## InSAR

If the satellite images the same place twice from nearly the same position, the *difference* in phase between
the two images depends on the change in distance between the radar and the ground. This is interferometry
(InSAR). One full phase cycle (2π) corresponds to half a wavelength of change in one-way distance, because the
signal travels there and back.

The raw phase difference is "wrapped": only known between −π and π. *Unwrapping* adds the missing whole cycles
to produce a continuous field. Unwrapping can fail where the signal is noisy.

## GUNW

The NISAR Level-2 **Geocoded Unwrapped Interferogram** (GUNW) is the product in which this work has already
been done and placed on a map grid (UTM, about 80 m posting for the unwrapped layers). TriageSAR reads:

| Layer | HDF5 dataset | Meaning |
|---|---|---|
| Unwrapped phase | `.../unwrappedInterferogram/<pol>/unwrappedPhase` | radians |
| Coherence | `.../<pol>/coherenceMagnitude` | 0 to 1; how similar the two echoes are |
| Connected components | `.../<pol>/connectedComponents` | label of the region each pixel was unwrapped with; 0 = not reliably unwrapped |
| Mask | `.../unwrappedInterferogram/mask` | water flag and valid sub-swath flags |
| Centre frequency | `.../frequencyA/centerFrequency` | hertz |

The reader does not rely on these exact paths. It finds datasets by name, checks that their shapes match the
coordinate vectors, and records the paths it used (`nisar/hdf5_reader.py`).

## Phase conversion

```
Δr [m] = λ [m] × φ [rad] / (4π)        λ = c / centerFrequency
```

`λ` is derived from the product's own `centerFrequency`; if neither a wavelength nor a centre frequency is
present the reader stops rather than assume a nominal value (`processing/displacement.py`, tested in
`test_displacement.py` and `test_hdf5_reader.py`).

### Sign convention

The GUNW product specification (JPL D-102272 Rev E) does not state the sign convention in words. TriageSAR
derives it from the processing software: ISCE3 forms the interferogram as `reference × conj(secondary)`
(`Crossmul.cpp`), the reference being the **earlier** acquisition, and the algorithm document gives the phase
model `Δφ = (4π/λ) Δr`. With the usual SLC phase of `−4πr/λ` this gives

```
φ = (4π/λ) × (r_secondary − r_reference)
```

so a **positive** phase means the range **increased**: the ground moved **away from** the satellite. That is
what TriageSAR reports as positive. Two safeguards: the ranking uses only the magnitude, so it cannot be
changed by a sign error; and `scripts/evaluate_reference.py` compares against the NASA/JPL map of the same
pair, which uses positive = towards the satellite. On the real pair the correlation is +0.991 when the JPL
values are read as "towards" and −0.991 the other way round, which confirms the convention empirically.

## Line-of-sight displacement

`Δr` is the change in distance **along the radar's viewing direction** (the line of sight, LOS). It is a
projection of the true three-dimensional motion onto one slanted direction.

### Why full 3-D motion is not recovered

Ground motion has three components (east, north, up) but one interferogram gives one number per pixel.
NISAR looks sideways from a near-polar orbit, so it is sensitive to vertical and east–west motion and almost
blind to north–south motion. Separating the components needs at least two viewing geometries (ascending and
descending) and usually extra assumptions. TriageSAR does not attempt this.

### Why values are relative, and the two references used

Unwrapped phase has an arbitrary constant, and that constant differs between connected components, so every
value needs a reference (`processing/clustering.py`).

- **Scene-relative** (the map's surface-motion layer, and a context value on every card): each connected
  component minus its median over the study area.
- **Local** (used for zones and ranking): each pixel minus a plane fitted by least squares to the usable
  pixels of the same component inside a 4 km window centred on it. A locally linear trend is removed exactly,
  so what remains is motion that **differs from the surroundings**. Pixels with less than a quarter of their
  window usable, or whose neighbours are too nearly collinear, are left unreferenced (shown as such, never
  filled in).

Why two: a large earthquake moves whole regions. On the Venezuela pair the coastal range moved by up to about
35 cm relative to the rest of the scene. That motion is real and is shown, but it is smooth over many
kilometres, and smooth motion carries a road along rather than tearing it. What threatens infrastructure is
motion that changes over short distances, which the local field isolates. The scene-relative reference was
the first one used for zones; on real data it made the threshold rise to 46 cm and found nothing (see
`docs/UNCERTAINTY.md`).

## Coherence

Coherence measures how alike the two radar echoes are, from 0 (unrelated) to 1 (identical). Vegetation growth,
water, snow, steep slopes and rapid surface change lower it. Low-coherence phase is noise, so those pixels are
EXCLUDED; moderately coherent pixels are kept and flagged CAUTION. The cut-offs (0.30 and 0.50 by default) are
screening values, documented in `config/triagesar.toml`.

## Connected components

The unwrapper labels each region it could unwrap consistently. Label 0 means "could not be reliably unwrapped"
(NISAR algorithm document, section 5.9.1.7) and is EXCLUDED. Between two different components the phase offset
is unknown, so TriageSAR references each one separately, flags small isolated components as CAUTION, and adds
a caveat to any zone that spans more than one component.

## Deformation zones

A pixel is a candidate when it is VALID or CAUTION and its absolute **local** LOS range change is at least
`max(3 cm, 3 × 1.4826 × MAD)`, where MAD is the median absolute deviation of the local field over the study
area. Touching candidates (8-connectivity) form a zone; zones under 0.5 km² are rejected as isolated pixels.
The 3 cm floor, the factor 3 and the 0.5 km² minimum were fixed before any real data were inspected; the
local reference they are applied to was adopted after the first real run. This is a **screening rule**, not a
detection threshold with a known false-alarm rate. On the real pair the local scatter is 0.54 cm (robust σ),
so the 3 cm floor is the binding term.

## Roads and the inspection priority score

Each zone is intersected with OpenStreetMap roads (motorway to tertiary). For each road that crosses a zone or
passes within 1 km of it, radar evidence is summarised in a 250 m corridor around the road. Six factors, each
between 0 and 1, are combined:

```
Inspection priority score = 100 × Σ (weight × factor)
```

| Factor | Default weight | Definition |
|---|---:|---|
| Observed LOS motion at the road | 0.35 | 90th percentile of \|relative LOS\| in the corridor ÷ largest such value in the event |
| Length of road inside the zone | 0.15 | overlap length ÷ longest overlap in the event |
| Share of valid radar pixels | 0.15 | VALID corridor pixels ÷ all corridor pixels |
| Median coherence | 0.10 | median coherence of corridor pixels |
| Closeness to the zone | 0.15 | 1 if the road crosses the zone, else 1 − distance ÷ 1 km |
| Road class | 0.10 | value configured for the OSM `highway` tag (a network role, not "criticality") |

Weights are perturbed by ±20% (12 one-at-a-time runs and 200 seeded random draws). If the top item changes in
more than 20% of runs, the ranking is labelled UNSTABLE.

## Why deformation is not infrastructure damage

- Ground can move as a block and carry an intact road with it; what harms structures is usually *differential*
  motion over short distances, shaking, liquefaction or landslides, none of which a single 80 m interferogram
  measures directly.
- Structures can be damaged by shaking where the radar sees no permanent ground change at all.
- Excluded pixels are unobserved. The absence of observed motion is not evidence of safety.
- Apparent motion can be atmosphere or an unwrapping error rather than ground movement.

So the output is an **inspection priority**: a reasoned order in which to send people to look. It is not a
damage probability, and nothing in TriageSAR is labelled "confidence".
