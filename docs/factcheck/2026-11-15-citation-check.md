# Citation check (2026-11-15)

Audience: the team and judges checking where each number on the website comes from.

Every source the website cites now lives in `web/src/sources.ts` as an APA 7 reference with a link. The landing's in-text citations and both Sources lists render from that one file. This ledger records what each source was checked against on 2026-11-15, and what changed.

## Facts on the landing

| Claim on the site | Source | Verdict | Change |
|---|---|---|---|
| 10+ ft of sinking near Pasadena, 1906–95; about 3,200 sq mi dropped at least 1 ft | Stork & Sneed (2002), USGS Fact Sheet 110-02: more than 10 ft near Pasadena during 1906–95; almost 3,200 mi² subsided more than 1 ft | Confirmed (via search excerpts; pubs.usgs.gov refuses automated reading) | "at least a foot" became "more than a foot", as the source says |
| Brownwood "~10 ft", destroyed by Alicia (1983), now a nature center | ABC13 Houston (2021, June 26), quoting HGSD's general manager: "an estimated 9 to 13 feet". Bernal (2019), *Houston History Magazine*: Alicia "delivered the final deathblow"; the city "created the Baytown Nature Center". Bernal gives no depth. | Depth corrected | "~10 ft" became "9–13 ft"; both sources cited |
| 28 in at a Jersey Village GPS station over 26 years | Holt (2021, April 29), *Community Impact*, quoting HGSD: "71 centimeters, or 28 inches of subsidence over 26 years" | Confirmed | "as pumping moved northwest" (unsourced) became "one of the fastest-sinking areas today" (the article's headline) |
| $125B Harvey damage; almost 34 in of rain on Harris County in four days | Blake & Zelinsky (2018), NHC report AL092017: "The latest NOAA damage estimate from Harvey is $125 billion". Lindner & Fitzgerald (2018), HCFCD final report: 1 trillion gallons over 4 days, "an average of 33.7 inches" across Harris County | Confirmed | Reworded as a county average |
| Ship Channel sinking "largely stopped" after late-1970s pumping cuts | Stork & Sneed (2002): since the late 1970s subsidence "largely has been abated" along the ship channel and in Baytown and Pasadena because pumping was reduced | Overstated | Now "has largely eased" |
| Addicks gauge recorded almost 4 ft | Our extensometer data (Ramage & Shah, 2024): Addicks 3.88 ft, 1974–2023 | Confirmed | None |

## Data sets

| Source | Identifier checked | Note |
|---|---|---|
| OPERA DISP-S1 v1 | doi:10.5067/SNWG/OPL3DISPS1-V1 (data.gov, AWS registry); NASA release news 2025-05-22 | Radar is Copernicus Sentinel-1. "NASA radar satellites" corrected everywhere (also flagged in the 2026-11-11 ledger, row 11, but not fixed in every place). |
| NISAR L2 GUNW provisional v1 | Earthdata catalog `asf-nisar-l2-gunw-provisional-v1-1` | No DOI could be confirmed for the provisional collection (catalogs disagree: NIL1GUNW-P1 and NIL2GUNW-B1 both appear), so the catalog page is cited with our retrieval date. |
| HoustonNet / Wang et al. (2022) | doi:10.1061/(ASCE)SU.1943-5428.0000399; HGSD-hosted PDF read in full | Daily positions: "2–4-mm RMS ... horizontal and 5–8-mm ... vertical". The site's 4 mm assumption was replaced by 6.5 mm (D-051). Deep-seated stations confirmed. |
| HoustonNet 2024 release | houstonnet.org (from the submission draft); archive SHA-256 in `data/manifests/houstonnet_2024.sha256` | No public landing page for the 2024 release was found; cited as the HGSD/UH network site. |
| USGS NWIS | doi:10.5066/F7P55KJN, the USGS-recommended citation | Retrieval date 2026-11-07 (from our manifest) |
| USGS extensometer release | doi:10.5066/P9YGUE2V, version 6.0, September 2024 | Author list differs between records (Ramage & Shah on USGS and ScienceBase; Adams & Ramage on a TACC mirror). The USGS record is followed. |
| Garvin (2018) Harvey inundation | doi:10.5066/F7VH5N3N | Confirmed |
| FEMA NFHL | msc.fema.gov/nfhl | No official citation format; retrieval date from our manifest |
| NASADEM | doi:10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001 | Confirmed |
| OPERA DSWx-S1 v1 | doi:10.5067/OPDSWS1-L3V1 (PO.DAAC, released 2024-10-25) | Confirmed |
| OPERA DIST-ALERT-HLS v1 | doi:10.5067/SNWG/OPERA_L3_DIST-ALERT-HLS_V1.001 (LP DAAC, March 2024) | Confirmed |
| Black Marble (globe) | Román et al. (2018), doi:10.1016/j.rse.2018.03.017; 34 authors, APA lists 19, an ellipsis, then the last | Author list matches the CIRA record |
| scikit-learn | Pedregosa et al. (2011), JMLR 12, 2825–2830 | Used by the forecast benchmark |

## Hardware page

| Source | Verdict |
|---|---|
| Hohensinn et al. (2022), *Remote Sensing* 14(20), 5100 | The page described it as "low-cost GPS receivers for ground-movement monitoring". It is about the u-blox ZED-F9P for *kinematic* monitoring with real-time PPP, finding about 1 cm precision. The page now says exactly that, as support for the 10 mm planning guess only. |
| NOAA CORS (NETP, ZHU1) | noaa-cors-pds bucket; NETP has no data after 2026-11-14 19:00 UTC (D-050) |
| CNES PPP-Wizard products | ppp-wizard.net, file cnt24446 |
| RTKLIB-EX 2.5.1 | github.com/rtklibexplorer/RTKLIB (local build, commit 755e637, 2026-11-06) |

## Could not be read automatically

pubs.usgs.gov returned HTTP 403 to automated reading, and going around the refusal was declined. The USGS fact sheet's two sentences were confirmed from search-engine excerpts quoting it. A person should open https://doi.org/10.3133/fs11002 once and confirm the wording.
