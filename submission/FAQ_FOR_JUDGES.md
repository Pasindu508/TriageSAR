# FAQ for judges

**Is this a damage detector?**
No. TriageSAR has no information about structures. It measures where the ground moved along the radar's line
of sight, and ranks where that evidence meets roads. Ground can move without damaging a road, and a structure
can be damaged where the radar saw nothing. The output is an inspection priority. The phrase "This is not a
damage assessment" is on the case-study page, on every evidence panel and in the API.

**Are the values real?**
Every value in the case study is computed from a crop of a real NISAR GUNW product, and the Provenance drawer
shows the granule, the dates, the crop window, the checksums and the command that produced it. If that
fixture has not been built on the machine in front of you, the application says "No NISAR observations
loaded" and shows no radar values at all. There is a synthetic event for automated tests; it only appears
when a developer switches it on, and then a banner on every page says it is synthetic.

**Where does NISAR enter the pipeline?**
At the first step. The fixture is a bit-for-bit crop of four layers of the NISAR Level-2 GUNW product:
unwrapped phase, coherence, connected components and mask. The radar wavelength used to convert phase to
distance is derived from the product's own centre-frequency metadata. The product was found through the ASF
Search API and read with NASA Earthdata Login.

**How do you treat uncertainty?**
Each pixel is VALID, CAUTION or EXCLUDED according to written rules on coherence, unwrapping status and the
product mask. Excluded pixels are never interpolated; they are drawn as hatching and counted. Each road card
shows how many of its pixels fall in each state. The ranking is re-run under 212 perturbations of the weights
and labelled stable or unstable. Nothing is called "confidence", because nothing here has a formal
statistical meaning.

**Why not just use a GIS dashboard?**
A dashboard shows layers and leaves the reading to an expert. TriageSAR does the reading in a fixed,
inspectable way: quality gate, zones, intersection, ranking, explanation. The result is a short list with
reasons, which is what a planner needs at the start of a response.

**How is this different from existing displacement portals?**
Portals such as the NASA Disasters Mapping Portal publish displacement rasters for experts, and they do that
well. TriageSAR does not replace them. It adds the step after the map: it combines the displacement with its
quality layers and with infrastructure, and produces an ordered, explained queue with provenance.

**Can this operate globally?**
It already runs on four events on three continents with the same settings (Venezuela, Japan, Indonesia,
Panama); adding one is three commands. Nothing is specific to a region. Today it needs a person to choose the event, the granule and the study area, and it handles one
product at a time. It is not an automatic global service.

**What happens when radar quality is poor?**
Poor-quality pixels are excluded and shown as unobserved. A road with too few usable pixels is labelled
INSUFFICIENT, and its motion is shown as "not computed" if nothing usable remains. Lower quality lowers the
score, because the evidence is weaker, so the scene summary also reports what share of road pixels could not
be observed at all. Those roads are unobserved, not cleared.

**What would be required before operational emergency use?**
Comparison with real inspection outcomes over several events; atmospheric correction; ascending and
descending geometries to separate vertical from horizontal motion; authoritative road and bridge inventories;
review by InSAR scientists and structural engineers; and an operating procedure agreed with the responding
agency. None of this has been done.

**Why is there no AI in it?**
Because a ranking that sends people into the field should be something they can check. The score is a
weighted sum of six visible numbers, and the explanations are templates filled with measured values. A
learned model would only make sense after inspection feedback exists to train and test it.

**How do you know the processing is right?**
There are tests with analytically known answers for the phase conversion and its sign, for masking, coordinate
handling, polygon areas, road intersection lengths and the score. The fixture crop is tested for bit-for-bit
equality with its source. Against the NASA/JPL displacement map of the same image pair, the correlation is
0.991 over about 700,000 pixels, with an RMSE of 3.9 cm. That shows two processing chains agree; it does not
show agreement with the ground.

**What is the sign convention, and are you sure?**
Positive means the range increased: the ground moved away from the satellite. The GUNW specification does not
state this in words, so we derived it from the ISCE3 processing code and documented the derivation. The
ranking uses only the magnitude, so it does not depend on the sign. The NASA/JPL map uses the opposite
convention (positive towards the satellite); our values correlate at +0.991 with it when that is accounted
for and −0.991 when it is not, which confirms the sign empirically.

**Which thresholds did you tune?**
No threshold or weight was changed after seeing the data: the coherence cut-offs, the 3 cm floor, the 3σ rule,
the minimum zone area and the weights are as first written. One method choice *was* changed after the first
real run: zones originally used motion relative to the whole scene, and because the earthquake moved the whole
coastal range, that rule found nothing. Zones now use motion relative to each pixel's surroundings. We say this
openly in `docs/UNCERTAINTY.md`, and the original rule is still selectable.

**In Venezuela the earthquake moved the ground by tens of centimetres. Why does TriageSAR rank no road there?**
Because that motion is smooth over many kilometres: a whole mountain range moved together, carrying its roads
with it. TriageSAR looks for patches that move differently from their surroundings, which is what tends to
stress a road. It found three small patches, mostly of moderate radar quality, the nearest 1.3 km from a mapped
road. It also reports that a fifth of road pixels could not be observed. An empty queue is a measured result,
not a clearance, and the interface says so.

**Why do the four case studies look so different?**
Because the ground and the radar did. Kumamoto's rupture was on land under a dense road network (16 zones, 936
ranked road segments). Venezuela moved as a block (3 small zones, nothing ranked). The Flores epicentre was
offshore (no zone on land). Most of the Panama frame is unobserved (84% excluded), so its 72 ranked roads all
carry CAUTION evidence. Same code, same thresholds, four honest answers.

**Kumamoto lists 936 road segments. Is that useful?**
The list is long because the zone covers a dense network and every named road is listed per zone. The order is
what matters, and the app labels it UNSTABLE because the top three scores are within three points of each
other. A planner should read the top of the list together with the evidence, not trust the exact order.
