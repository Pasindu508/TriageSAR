# Judge pitch: 90 seconds

Every number below is from the real runs (`BUILD_REPORT.md`). Do not add others.

**0–15 s · The human problem**

"After a big earthquake a road agency has hundreds of kilometres of road and a few inspection teams. Where
do they go first?"

**15–30 s · Why NISAR changes what is possible**

"NISAR, the NASA–ISRO radar, sees through cloud, day and night, and its interferograms show where the ground
moved. But a colourful map is not a plan, and it does not say how far to trust each colour."

**30–55 s · Live workflow** *(Kumamoto, then Venezuela)*

"This is the real NISAR pair over the Kumamoto earthquake of 28 July. TriageSAR gates every pixel for quality,
finds 16 patches that moved differently from their surroundings, and ranks the roads through them. First: the
Kyushu Expressway, ten kilometres inside the largest zone. And it tells you the ranking is unstable, because
the top three are close. Now Venezuela, a magnitude 7.5: the whole coast moved as one block, so TriageSAR ranks
no road and says why."

**55–75 s · Scientific integrity**

"Without the quality gate, Venezuela would have produced 76 'priorities' from noise. Our values match NASA/JPL's
own map of that pair at 0.99. Every number traces to its granule and the command that built it. Unobserved roads
are reported, not hidden, and this is not a damage assessment."

**75–90 s · Impact and next steps**

"TriageSAR is the layer after the map: an inspection order you can audit, including when the honest answer is
'nothing stands out'. Next: atmospheric correction, a second viewing angle, and feedback from real
inspections. Open source, Apache 2.0."
