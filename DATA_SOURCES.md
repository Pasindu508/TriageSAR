# Data sources

Every external dataset used by TriageSAR, with access details. Access date for all entries: **14 November 2026**.
Machine-readable provenance for each built fixture is in `data/fixtures/**/manifest.json` and
`osm_manifest.json`, and is shown in the application's Provenance drawer.

## 1. NISAR Level-2 Geocoded Unwrapped Interferogram (GUNW)

| | |
|---|---|
| **Dataset** | NISAR Provisional Geocoded Unwrapped Interferogram Product (Version 1), short name `NISAR_L2_GUNW_PROVISIONAL_V1` |
| **Provider** | NASA–ISRO NISAR mission, distributed by the NASA Alaska Satellite Facility DAAC (ASF) |
| **Purpose** | Primary scientific input: unwrapped phase, coherence, connected components and mask |
| **Access URL** | https://search.asf.alaska.edu/ · API: https://api.daac.asf.alaska.edu/services/search/param · docs: https://nisar-docs.asf.alaska.edu/gunw/ |
| **Collection identifier** | CMR concept ID `C2854335566-ASF` (https://cmr.earthdata.nasa.gov/search/concepts/C2854335566-ASF.umm_json) |
| **Granules used** | Venezuela: `NISAR_L2_PR_GUNW_022_162_A_007_023_4000_SH_20260613T100656_20260613T100731_20260625T100655_20260625T100730_P05023_N_F_J_001` (ascending track 162, frame 7; 13 → 25 Jun 2026). Kumamoto: `NISAR_L2_PR_GUNW_026_024_A_018_028_4000_SH_20260721T202900_20260721T202934_20260814T202858_20260814T202933_P05023_N_F_J_001` (track 24, frame 18; 21 Jul → 14 Aug 2026). Panama: `NISAR_L2_PR_GUNW_032_076_A_005_033_4000_SH_20261005T105604_20261005T105616_20261017T105604_20261017T105616_P05023_N_P_J_001` (track 76, frame 5, partial frame; 5 → 17 Oct 2026). Flores: `NISAR_L2_PR_GUNW_027_168_A_173_028_4000_SH_20260812T214030_20260812T214104_20260824T214029_20260824T214104_P05023_N_F_J_001` (track 168, frame 173; 12 → 24 Aug 2026). Exact study areas, sizes and URLs: `config/events/*.json`. |
| **Licence / terms** | Free and open data (`FreeAndOpenData: true` in CMR). NASA ESDIS Data Use and Citation Guidance: https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance |
| **Required attribution** | Credit NASA/ISRO NISAR and the ASF DAAC. The UI shows "NISAR L2 GUNW: NASA/ISRO via ASF DAAC". No formal citation string is published for this collection yet. |
| **Maturity** | PROVISIONAL: partially validated, with documented known issues (see `docs/UNCERTAINTY.md`). |
| **Access requirement** | Search needs no account. Download needs a free NASA Earthdata Login (https://urs.earthdata.nasa.gov/). |

**Processing steps**

1. Discovery: `python scripts/discover_nisar.py --bbox -68.5 9.5 -65.5 11.5 --start 2026-06-10 --end 2026-07-05 --product GUNW`
2. Crop to the event's study area (`aoi_bbox_wgs84` in `config/events/<event>.json`) and write one lossless
   GeoTIFF per layer: `python scripts/build_demo_fixture.py --event <event>`
3. Record the other acquisitions of the same track and frame (for the timeline):
   `python scripts/fetch_acquisitions.py --event <event>`
3. No resampling, scaling, interpolation or correction is applied. The exact pixel window, HDF5 source paths,
   processing version and SHA-256 checksums are recorded in the fixture manifest.

The fixture is a small crop of a public NASA product and is redistributed here under the same open-data terms.

## 2. USGS earthquake catalogue (event context only)

| | |
|---|---|
| **Dataset** | USGS Earthquake Hazards Program event catalogue (ComCat), FDSN event web service |
| **Provider** | U.S. Geological Survey |
| **Purpose** | Event time, magnitude and epicentre shown as map context. Not used in any computation. |
| **Access URL** | https://earthquake.usgs.gov/fdsnws/event/1/ |
| **Events** | Kumamoto `us6000tgb9` (M 6.8, 2026-07-28), Panama `us6000u18k` (M 7.7, 2026-10-09), Flores `us6000tkt2` (M 7.8, 2026-08-14), Venezuela `us6000t7zp` (M 7.5, 20 km W of Catia La Mar, Venezuela, 2026-06-24T22:05:04Z) https://earthquake.usgs.gov/earthquakes/eventpage/us6000t7zp · `us6000t7zc` (M 7.2, 20 km E of San Felipe, Venezuela, 2026-06-24T22:04:31Z) https://earthquake.usgs.gov/earthquakes/eventpage/us6000t7zc |
| **Licence / terms** | U.S. Government work, public domain. Catalogue values may be revised by USGS. |
| **Required attribution** | "USGS Earthquake Hazards Program" (shown next to the event information). |
| **Processing steps** | Values copied by hand into `config/events/venezuela-2026-06-24.json`. |

## 3. OpenStreetMap roads and place names

| | |
|---|---|
| **Dataset** | OpenStreetMap ways tagged `highway` = motorway, trunk, primary, secondary, tertiary (and their `_link` variants), and `place` = city or town nodes, inside the study area |
| **Provider** | OpenStreetMap contributors, retrieved through the Overpass API (https://overpass-api.de/) |
| **Purpose** | Infrastructure layer for the intersection and ranking; place names for map orientation |
| **Access URL** | https://www.openstreetmap.org/ · Overpass endpoint https://overpass-api.de/api/interpreter |
| **Licence** | Open Database Licence (ODbL) 1.0, https://opendatacommons.org/licenses/odbl/1-0/ · https://www.openstreetmap.org/copyright |
| **Required attribution** | "© OpenStreetMap contributors" with a link to the copyright page. Shown on the map, in the Provenance drawer and here. |
| **Identifiers** | OSM way ids are kept on every road and shown in the evidence panel. OSM data timestamp: see `osm_manifest.json`. |
| **Processing steps** | `python scripts/fetch_osm_roads.py --event venezuela-2026-06-24`: convert ways to GeoJSON LineStrings, keep only `osm_id`, `highway`, `name`, `ref`, `bridge`, `tunnel`; round coordinates to 6 decimals. |

**ODbL obligations.** The cached extract in `data/fixtures/infrastructure/` is a *derivative database* and is
offered under the ODbL. The maps and rankings drawn from it are *produced works* and carry the attribution
above. No OpenStreetMap raster tiles are used or stored.

## 4. NASA/JPL line-of-sight displacement maps (optional reference, not bundled)

| | |
|---|---|
| **Dataset** | "Line of Sight Surface Displacement Map (NISAR) for the Venezuela Earthquakes", GeoTIFF for ascending track 162, 13–25 June 2026 |
| **Provider** | NASA-JPL/Caltech team and NISAR Operations Science Team, NASA Disasters Mapping Portal |
| **Purpose** | Reference-product consistency evaluation (`scripts/evaluate_reference.py`). Downloaded on 15 November 2026 to the git-ignored `.cache/reference/` (56,554,443 bytes, EPSG:32619, 80 m); results are in `BUILD_REPORT.md`. Not required to run the demo and not redistributed. |
| **Access URL** | Portal item: https://gis.earthdata.nasa.gov/portal/home/item.html?id=9244f7b07fa64d45ae7cb66c34d1696a · GeoTIFF: https://aria-share.jpl.nasa.gov/20260624_Venezuela_EQ/Displacements/NISAR/NISAR_A162_20260613_20260625_displacements_cm_v2.tif |
| **Terms** | NASA data and products are freely available; the portal describes them as experimental or research-grade and possibly not appropriate for operational use. The product page states it is relative, uncalibrated and not yet validated. |
| **Notes** | Derived from the Urgent Response GUNW of the same image pair, in centimetres, positive towards the satellite, with ionosphere and ramp removed and water masked. It is another processing of the same radar data, not ground truth. |

## 5. NASA GIBS basemaps (optional, online only)

| | |
|---|---|
| **Datasets** | "Satellite": NASA Blue Marble Next Generation (August 2004 composite, about 500 m). "Terrain": NASA/METI ASTER GDEM greyscale shaded relief (about 30 m). |
| **Provider** | NASA Global Imagery Browse Services (GIBS), https://gibs.earthdata.nasa.gov/ |
| **Purpose** | Visual context under the analysis layers only. Never used in any computation. |
| **Terms** | NASA imagery is freely available with no restrictions on reuse; credit NASA GIBS and the source product. The map shows the attribution of whichever basemap is visible. |
| **Offline** | Tiles are fetched by the browser at view time and not stored. Without a connection the plain background is shown and every analysis layer still works. |

## 6. Synthetic test data (not a data source)

`tests/support/synthetic.py` generates a small HDF5 file that imitates the *layout* of a GUNW product, with
made-up values located in open ocean near 0° N, 0° E. It exists only for automated tests and UI development,
is labelled `TEST ONLY` everywhere, is never stored in `data/fixtures/`, and is served by the API only when
`TRIAGESAR_INCLUDE_SYNTHETIC=1`, in which case the UI shows a permanent warning banner.
