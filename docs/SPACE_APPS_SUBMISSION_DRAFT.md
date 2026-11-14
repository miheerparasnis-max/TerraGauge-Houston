# TerraGauge — NASA Space Apps Submission Draft

> Before pasting: replace bracketed links and team-member names. Keep the limitations in this document; they are part of TerraGauge's validity, not an apology.

## Project name

**TerraGauge: Evidence Before Disaster**

## 1. High-level project summary

Flood risk is not only about rain and water: when land slowly sinks, the same storm can reach farther and drain less effectively. Yet city planners often must reconcile satellite radar, sparse ground stations, groundwater records, compaction measurements, and flood-zone maps separately. TerraGauge turns those disconnected records into one evidence-first decision map for Houston.

We built a web application and reproducible Python pipeline that analyzes NASA NISAR radar observations and NASA OPERA displacement history alongside HoustonNet GPS, USGS groundwater and extensometer records, and FEMA flood-zone context. For every 1 km cell, TerraGauge explains the evidence, its confidence, and the next appropriate action: investigate, add monitoring, watch, or withhold a conclusion. It explicitly refuses to label a single radar pair as an annual subsidence rate or flood forecast.

Our Houston prototype demonstrates a model that any city can adapt with its own radar coverage, ground stations, water records, and hazard maps. Instead of waiting for damage to reveal a monitoring gap, cities can use TerraGauge to make their next measurement—and ultimately their resilience investment—more intentional.

## 2. Project demonstration

**Public 30-second demo URL:** [PASTE PUBLIC VIDEO URL]

### Final 30-second video script and shot plan

**0:00–0:03 — Houston flood/street image, then map**

Voice: “When the ground sinks, the same storm can become a bigger flood. But cities rarely know where to measure first.”

**0:03–0:07 — TerraGauge title, challenge name, team members on screen**

On-screen: “TerraGauge — Evidence Before Disaster” / “NASA Space Apps: Dancing with the SARs” / [TEAM MEMBER NAMES]

**0:07–0:14 — Show the map changing layers**

Voice: “TerraGauge combines NASA radar with Houston GPS, groundwater, compaction, and flood-zone data into one action map.”

On-screen flow: NASA NISAR + OPERA → GPS + groundwater + compaction + FEMA → investigate | add monitoring | withhold

**0:14–0:21 — Click one evidence card, show confidence and source trail**

Voice: “Every square shows what supports it, what disagrees, and what evidence is still missing—so uncertainty never becomes a false alarm.”

**0:21–0:27 — Show suggested sensor locations and the physical GNSS node**

Voice: “It identifies monitoring gaps, helping agencies place the next ground sensor where it can matter most.”

On-screen qualifier: “GNSS node: bench prototype; no ground-motion claim from weekend recordings.”

**0:27–0:30 — Houston map zooms out to a world map**

Voice: “Built for Houston, TerraGauge is a reusable blueprint for cities facing flooding and land-motion risk worldwide.”

### Video production rules

- Keep the exported video at 30 seconds or less, including title cards.
- Use only real app screenshots, team-recorded hardware footage, public-domain imagery with attribution, or licensed imagery.
- Do not use NASA logos, flags, or mission insignia as decoration.
- If any SI-generated image or video is used, place a visible watermark on that asset. The recommended video uses no SI-generated visual or audio.
- Put “TerraGauge is not a flood forecast or property-risk assessment” in small, readable text on the final frame or evidence-card shot.

## 3. Final project

**Public project URL:** https://github.com/miheerparasnis-max/TerraGauge-Houston

Before submission, change the repository visibility to public and test this URL in an incognito/private browser. If a deployed site is ready, add it as the first line of the README and use its public URL here instead.

## 4. Project details

### What TerraGauge does

TerraGauge is an evidence-first ground-motion monitoring-priority system. It does not promise that every colored map pixel is a disaster prediction. Instead, it answers the operational question a city can act on: **where should we inspect the evidence, deploy the next sensor, or withhold a conclusion?**

The application divides the Houston study area into 1 km cells. Each cell receives an evidence card that records the available satellite observation, quality and water flags, nearby GPS context, groundwater and compaction context, FEMA flood-zone context, confidence, and an action label. The labels are mutually exclusive, in a safety-first order:

1. **Insufficient data** — quality or coverage is inadequate; TerraGauge makes no movement claim.
2. **Add monitoring** — a quality-controlled candidate signal is present but no permanent GNSS station is close enough for follow-up.
3. **Investigate** — a candidate signal has nearby independent ground context and should receive expert review.
4. **Context only** — available records provide context, but do not meet the threshold for a monitoring action.

The map also identifies candidate GNSS deployment locations. This lets a city turn a large, difficult question—“where is the ground moving?”—into a smaller, auditable decision—“where would one more measurement reduce uncertainty most?”

### How it works

**1. Convert raw spaceborne observations into traceable cell evidence.** We ingest NASA NISAR L2 GUNW pairwise line-of-sight displacement data and preserve its projection, wavelength, acquisition dates, coherence/quality information, and atmospheric-correction flags. A structural validation gate rejects malformed or out-of-bounds cells, duplicate cell IDs, missing correction flags, and broken connected components.

**2. Add long-history context.** We ingest 19 NASA OPERA DISP-S1 products from July 2016 to May 2021. Only recommended-quality pixels are aggregated into approximately 1 km cells; water coverage is retained as a review flag. The historical satellite record is cross-checked against held-out HoustonNet GPS stations rather than presented as unquestioned truth.

**3. Explain possible mechanisms and consequences without claiming causation.** USGS groundwater records and USGS/Harris-Galveston Subsidence District extensometer records give local context about aquifer conditions and measured subsurface compaction. FEMA National Flood Hazard Layer polygons provide flood-zone context at each cell. These layers can raise the urgency of a monitoring gap, but they do not turn a correlation into a claim that groundwater caused surface motion or that flooding will occur.

**4. Gate claims by what the data can resolve.** One NISAR radar pair is a relative line-of-sight observation, not vertical subsidence or an annual rate. TerraGauge therefore refuses to emit a rate without a documented stable reference region and a redundant temporal network. In the prototype, five same-track NISAR pairs form a chain but not an independently closed network, so the backend explicitly withholds a NISAR rate. That safeguard is visible in the API and the interface.

**5. Validate the historical layer, not just the visualization.** The included provisional OPERA workflow uses a held-out HoustonNet check. Its current local comparison covers 108 stations, with correlation approximately 0.69 and a typical difference approximately 2.1 mm/year. It remains labelled provisional_unreviewed: the reference choice and nonmatching historical time windows still need expert review before operational use.

### Benefits and intended impact

TerraGauge changes a city’s first question from “where can we draw the most alarming color?” to “where would better evidence change a decision?” That is important because flood-resilience budgets, field crews, and permanent GNSS stations are limited. A transparent monitoring-priority map can help technical teams target field verification, add sensors in underserved areas, and inspect land-motion evidence alongside local hazard exposure.

For Houston, TerraGauge integrates information that is typically separated by discipline: radar scientists, groundwater managers, floodplain staff, and GPS-network operators can see the same evidence card and its limitations. For other cities, the architecture is intentionally modular: replace HoustonNet, USGS, and FEMA layers with equivalent local GNSS, water/compaction, and hazard sources while retaining the same provenance, quality gates, and “withhold when unknown” logic.

TerraGauge has **not** yet measured lives saved, forecast individual floods, or made a deployment decision for an agency. Its impact claim is prospective: by making monitoring gaps visible and evidence auditable, it can support better targeting of the measurements and resilience decisions on which future safety outcomes depend.

### Technology, hardware, and software

- **Backend:** Python 3.11+, standard-library HTTP API, reproducible JSON contracts, unit tests, and source-specific ingestion adapters.
- **Geospatial/scientific ingestion:** NumPy, h5py, and pyproj process HDF5, NetCDF-derived products, coordinate transforms, quality masks, and spatial aggregation.
- **Frontend:** React, TypeScript, Vite, and MapLibre GL render an interactive 1 km evidence map, source cards, uncertainty language, sensor-gap candidates, and a data-ledger view.
- **Hardware:** a Waveshare/Quectel LC29H(BS) dual-band GNSS board was assembled as a GroundTruth Node prototype. Its planned role is stationary repeatability testing and future CORS/RTK validation—not proving subsidence during a weekend. At submission time, the board has no usable observation recording; TerraGauge excludes it from all current movement results.

### What makes TerraGauge innovative

Most risk maps hide uncertainty because ambiguity is visually inconvenient. TerraGauge makes uncertainty actionable. It preserves source metadata, records whether an atmospheric correction has already been applied, keeps water masks as review flags, prevents a relative radar displacement from silently becoming a yearly vertical rate, and exposes the reason a rate was withheld. Its output is not merely a heatmap: it is a defensible next-action recommendation paired with the evidence required to challenge it.

### Development factors considered

- **Scientific validity:** line-of-sight versus vertical motion, reference selection, temporal-network redundancy, quality masks, water/decorrelation, and time-window mismatch.
- **Human impact:** flood-zone context is used to prioritize monitoring gaps, not to label people or properties as unsafe.
- **Transparency:** every major result retains data provenance and a limit on interpretation.
- **Scalability:** the data contracts separate common decision logic from city-specific datasets.
- **Equity and accessibility:** the public-facing map uses plain-language evidence cards rather than expert-only radar jargon.
- **Privacy and safety:** no personal data or individual property-risk score is collected or produced.

## 5. Use of Super Intelligence (SI)

**Select the applicable options for code and written/documentation assistance.**

Paste this disclosure in the SI description field:

> We used a large-language-model assistant for brainstorming, code scaffolding, debugging, and editorial assistance. Team members selected the problem, datasets, methodology, thresholds, and final claims; inspected source data; ran tests; and reviewed generated code and text. The project’s displayed maps, charts, and quantitative outputs are produced from the cited datasets and our code, not generated imagery. We used no SI-generated audio, and we will not include SI-generated visual media unless it carries the required visible watermark.

Add this short notice to the repository README before publishing:

> **SI disclosure:** AI assistance was used for code scaffolding, debugging, and documentation editing. Team members reviewed, tested, and take responsibility for the final implementation and claims.

## 6. NASA data and resources

| Link text | Link URL | How TerraGauge uses it |
|---|---|---|
| NASA NISAR Mission Data | https://nisar.jpl.nasa.gov/data/ | NISAR L2 GUNW pairwise line-of-sight displacement, quality, and correction metadata; used for current mission-era evidence and network diagnostics. |
| NASA JPL OPERA DISP-S1 | https://www.jpl.nasa.gov/go/opera/products/disp-s1/ | 19 quality-masked historical displacement products (frame F38238, July 2016–May 2021) used to build provisional historical context and compare against held-out GPS stations. |
| NASA Earthdata Search | https://search.earthdata.nasa.gov/ | Used to locate and access the NISAR and OPERA source products. |

Do **not** list NASADEM, OPERA DSWx-S1, OPERA DIST-ALERT, or MERRA-2 unless the team finishes ingesting them and they appear in the delivered project results.

## 7. Space agency partner and other data/resources

| Link text | Link URL | How TerraGauge uses it |
|---|---|---|
| HoustonNet 2024 Data Release | https://www.houstonnet.org/ | Historical GNSS vertical-rate context, reference selection support, held-out cross-check, and sensor-coverage analysis. |
| USGS National Water Information System daily values | https://waterservices.usgs.gov/nwis/dv/ | Houston-area groundwater depth records used as local mechanism context, not causal proof. |
| USGS/HGSD Houston compaction data release | https://doi.org/10.5066/P9YGUE2V | Cumulative compaction through 2023 at 14 greater-Houston extensometers. |
| FEMA National Flood Hazard Layer | https://hazards.fema.gov/femaportal/wps/portal/NFHLWMSkmzdownload | Flood-zone polygons used as exposure context and to prioritize monitoring gaps. |
| MapLibre GL JS | https://maplibre.org/maplibre-gl-js/docs/ | Open-source interactive map rendering. |
| OpenFreeMap | https://openfreemap.org/ | Public basemap tiles. |
| React | https://react.dev/ | User-interface framework. |
| TypeScript | https://www.typescriptlang.org/ | Typed frontend development. |
| Vite | https://vite.dev/ | Frontend build tooling. |
| NumPy | https://numpy.org/ | Numerical analysis and aggregation. |
| h5py | https://www.h5py.org/ | NISAR HDF5 inspection and ingestion. |
| pyproj | https://pyproj4.github.io/pyproj/ | Coordinate-reference-system transformations. |
| Waveshare LC29H GPS/RTK HAT documentation | https://www.waveshare.com/wiki/LC29H%28XX%29_GPS/RTK_HAT | Hardware documentation for the prototype GroundTruth Node; it is not used to support current movement results. |

## Final submission checks

- [ ] Replace team-member placeholders in the video.
- [ ] Upload final video and verify it is 30 seconds or less.
- [ ] Test video URL and project URL in a private browser without signing in.
- [ ] Make the GitHub repository public, or publish a public project website.
- [ ] Add the SI disclosure to the README and choose the matching SI options.
- [ ] Confirm all referenced images/video/audio are team-created, public-domain, or properly licensed and attributed.
- [ ] Do not say TerraGauge predicts floods, certifies property risk, proves current subsidence from a NISAR pair, or has validated the GNSS board.
- [ ] Keep provisional and withheld safeguards visible in the demo and detailed description.

