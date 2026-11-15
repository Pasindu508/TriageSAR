# Limitations

This document is meant to be unusually blunt. Read it before using any output of TriageSAR.

## What TriageSAR is not

- It is **not a damage detector**. It has no information about structures.
- It does **not predict casualties**, losses or exposure.
- Its inputs are **not ground truth**, and its score is **not a probability, accuracy or confidence**.
- It is **not operational**. It is a hackathon prototype that no emergency agency has reviewed.

## It has never been validated against reality

Nobody has compared a TriageSAR queue with what inspectors actually found. We do not know whether highly
ranked roads are more likely to need attention than lowly ranked ones. Every weight and threshold is an
informed guess written down before looking at the data. The available checks (tests, ablation, sensitivity,
comparison with another processing of the same radar data) show that the software does what it says. They do
not show that what it says is useful.

## Measurement limits

1. **One viewing direction.** A single interferogram measures motion along one slanted line of sight. Motion
   along the satellite track (roughly north–south) is nearly invisible. A road can shift by a metre
   northwards and show almost nothing.
2. **Relative, not absolute, and local.** Zones measure motion that differs from the surrounding 4 km. Motion
   that is smooth over several kilometres, such as most of an earthquake's broad deformation, is shown on the
   map but never becomes a zone. In the Venezuela case the coastal range moved by tens of centimetres and no
   road was ranked; a reader who expected "big motion = high priority" should know this is by design.
3. **Atmosphere is not removed.** Tropospheric and ionospheric delays can look like centimetres of motion.
   No correction is applied.
4. **Unwrapping can be wrong.** Errors come in steps of half a wavelength (about 12 cm) and can create or
   hide apparent motion. Very large gradients near a fault rupture decorrelate entirely and are excluded,
   so the places that moved most may be exactly the ones with no data.
5. **Twelve days, not one event.** The image pair spans 13 to 25 June 2026. Anything that changed the ground
   in that window is included: both earthquakes, aftershocks, landslides, rain, farming.
6. **80 m pixels, 250 m corridors.** A bridge or a short damaged section is far smaller than the measurement.
   Corridor statistics describe the neighbourhood of a road, not the road itself.
7. **Provisional product.** The NISAR release used is partially validated and has documented known issues.
8. **Decorrelation is not random.** Vegetation, steep slopes, water and built-up change lose coherence. Roads
   in forested mountains, often the most vulnerable, are the most likely to be unobserved.

## Method limits

- The screening threshold (`max(3 cm, 3 × robust σ)`) is a convention. In a noisy scene it rises and real
  motion is missed; in a quiet scene the 3 cm floor may admit atmosphere.
- The reference method was changed after the first real run found nothing with the original one (see
  `docs/UNCERTAINTY.md`). It has been tried on exactly one real interferogram.
- The ranking has been exercised on two real events (Kumamoto and Panama). In Kumamoto it is labelled UNSTABLE:
  the top three scores are within three points, so their order should not be over-read.
- The Kumamoto pair spans 24 days, so it includes more non-earthquake change than a 12-day pair. The Panama
  product is a partial frame and 84% of the study area is unobserved.
- Two of the six score factors are normalised by the largest value **in the same event**, so scores cannot be
  compared between events, and a score of 90 in a quiet event means less motion than 90 in a violent one.
- Lower radar quality lowers a road's score, because the evidence is weaker. A badly observed road may be
  the one that most needs a visit. The "unobserved roads" figure exists to make this visible; the queue alone
  does not.
- Road class from OpenStreetMap is a rough stand-in for importance. Nothing about traffic, alternatives,
  hospitals served or population is included.
- Roads are grouped by name or reference tag. Unnamed roads are ranked way by way; long named roads appear
  once per zone.
- Only roads are ranked. Bridges are noted only where OpenStreetMap tags them.

## Data limits

- OpenStreetMap can be incomplete, out of date or misaligned by tens of metres.
- The study area is one crop of one frame. There is no global or automatic coverage.
- Building a fixture needs a NASA Earthdata account and a person to choose the event, the granule and the
  area.

## Before anyone relies on this

Comparison with field outcomes over several events; atmospheric correction; two viewing geometries;
authoritative asset inventories; review by InSAR scientists and structural engineers; and an agreed operating
procedure with the responding agency that treats the queue as one input among several.
