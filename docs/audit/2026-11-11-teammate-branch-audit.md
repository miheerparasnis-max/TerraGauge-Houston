# Audit: branch `reyansh/website-and-fixes` (2026-11-11)

Audience: the team and the executing agent, deciding what to take from the branch before the UI pass.

> Some rows quote phrases from the audited branch as evidence. A manual G2 claims sweep should treat those quotes like the ones elsewhere in `docs/audit/`.

## Scope and method

- **Branch:** `origin/reyansh/website-and-fixes` at `1705aad`, 16 commits on top of `2d44a42`. It does **not** contain `5c0513c` or any of the 28 commits on `chore/audit-baseline-2026-11-10`, so it predates the pre-registration, amendment A1, and the claims fixes.
- **What I ran:**
  - The branch's own tests: 71 run, OK, 2 skipped because scikit-learn is not installed.
  - Our `tests/test_claims_policy.py` against the branch's tree: 2 failures and 1 error.
  - The website build (`tsc` + `vite`): OK. A headless render worked, apart from WebGL, which headless mode disables.
  - A trial merge into our branch: 16 conflicting files.
  - His OPERA data through **our** pipeline rules: this branch's `opera_series`, `region_cell_ids` and `compare_opera_gps`, run on his pair files (a scratch script, not committed).
  - A placebo test of the drought claim.
  - A NASA CMR query for the south-frame products.
  - DOI resolution of the Harvey source.
- **The "4% better":** the forecast benchmark in `ac12ef7`. The chosen method's typical 1–5-year error is 1.50 cm, against 1.56 cm for the long-term rate. That is 3.8% lower, for a forecast, which MASTER §20 forbids.
- **Correction to D-032:** that entry said no new teammate work was on GitHub. This branch received all 16 commits after that check. `5c0513c` was written by a different teammate than this branch's author.

## Verdict

| # | Item (commits) | Verdict | Why |
|---|---|---|---|
| K1 | 11 OPERA F38238 products, 2021-05-05 → 2026-03-22 (`d29e9e2`) | **Take** | See "OPERA extension" below: r 0.660 → 0.800 under our rules. MASTER §5.1 asks for OPERA through March 2026, and V2 needs F38238 products inside the NISAR window. |
| K2 | OPERA frame F38239 for south Houston, plus `merge_frames` (`a32810d`–`1705aad`) | **Take after two fixes** | The alignment is sound: per-product overlap spread is 0.5–1.4 mm after the offset. The merge as written shifts the datum for the whole map, and one product is missing (see "South frame" below). |
| K3 | UI shell: address search, shareable URL state, guided tour, phone bottom sheet, collapsible card, CSV/JSON download, lazy 16 km detail tiles, 2016–2026 time-lapse (`59963a8`, `01c14b2`) | **Take as the UI base** | It builds clean and the layout is good. It needs our copy, and "© OpenStreetMap contributors" credit for Nominatim. |
| K4 | Full 1 km grid (13,299 squares), with the reason each unmeasured square has no reading (`59963a8`) | **Take** | This is honest absence, which MASTER §0.6 asks for. |
| K5 | Faster raster sampler; Earthdata login and download error messages (`a150bf2`, `3f41b18`) | **Take** | Low risk; tests pass. |
| K6 | Harvey check: FEMA zones against USGS Harvey inundation (`5c1ea03`, `01c14b2`) | **Optional context, after fixes** | It is about the past and FEMA only. Its result: movement rate alone did not predict where Harvey flooded. It does **not** show that subsidence leaves flooding unchanged: the fastest-moving squares (northwest: Katy, Cypress) are mostly inland and higher, so location confounds the comparison. Any page copy needs the square counts per class and a significance check, never "fast-moving ground flooded less". The citation is wrong (see the "Harvey" row below). |
| K7 | Seasonal (annual sine/cosine) rate fit | **Park as a pre-registered sensitivity** | Sound for estimating past rates (Blewitt & Lavallée 2002). Here it is used only as a forecast input. |
| X1 | Forecasts to 2031: gradient-boosted ML, then "season-aware + neighbourhood", year-by-year ranges, back-tests, benchmark (`d29e9e2`, `4209e0a`, `d947928`, `ac12ef7`) | **Drop** | MASTER §20 ("TerraGauge predicts future subsidence") and §10 ("No machine-learned component"). This is what W-1 removed. In his own back-test the ML model was worse than "no motion" at every cutoff (for example 2.69 cm against 1.14 cm at 1 year), and at 1 year "no motion" tied the long-term rate. |
| X2 | Flood view, "how much deeper by year Y", with ocean rise of 10 mm/yr (`c4c6726`) | **Drop** | It is a projection, and close to "will flood". |
| X3 | Drought view, with "2018 response predicted 2023's worst-hit squares (AUC 0.81/0.83)" (`c4c6726`) | **Drop the claim** | It fails a placebo test (see "Drought placebo" below). |
| X4 | Ground bending, which "can mark a slipping fault" (`c4c6726`) | **Park** | Naming a fault is diagnosing a cause. Stability between two periods (r 0.51) is not validation against mapped faults. |
| X5 | Rates interpolated into unmeasured squares (3,529 from neighbours, 54 from GPS), which then receive labels (`a150bf2`, `8d08b70`) | **Drop** | 652 of 1,174 "add monitoring" and 55 of 152 "investigate first" labels sit on squares nobody measured. Many suggested node sites are on estimated squares too. This breaks MASTER §0.6. |
| X6 | Rates blended with each square's 3 km neighbourhood ("2.1 → 1.9 mm/yr", `8d08b70`) | **Park** | It was tuned against the same GPS stations used to judge it, and it blurs small subsidence bowls. Pre-register it and score it on held-out stations if wanted. |
| X7 | Labels (`backend/insights.py: action_label`) | **Replace with ours** | "Review disagreement" uses historic GPS rates, which MASTER §5.2 forbids. "GPS confirms it" only checks that a station is within 2 km and doesn't disagree by more than 5 mm/yr. The copy reads "Clearly sinking…" and "faster than anything measured in Houston", which our ledger row 8 found false. |
| X8 | Detectability numbers | **Replace** | NISAR σ = 8.2 mm, taken from the reference-patch scatter of an unregistered reference. That gives "5 mm/yr in 1.9 years", which conflicts with PR-3. GPS "14 weeks" assumes 4 mm white daily noise; annual signals bias rates from spans under about 2.5 years (Blewitt & Lavallée 2002). Node "26 weeks" uses an assumed 10 mm σ, but MASTER §5.4/E6 allows no node detectability number without valid sessions. |
| X9 | Reference and GPS check | **Replace with ours** | The reference includes deep-seated ADKS and LKHU, and the check compares against NETP and TXEX. "131 GPS stations" counts campaign PAMs and stations that share one square (UHC0–UHC3; UHL1/UHWL). |
| X10 | Copy | **Replace** | About 80 G2 hits in `web/src` and the README, 69 of them "sinking". Also "will flood", "measured subsidence", and "proves". The headline "Where is Houston's ground sinking?" is not MASTER §1.1's mission. See "Unsupported copy" below. |

## Evidence

### OPERA extension (K1), through our rules

Our rules here: pre-registered region A, deep-seated stations excluded, no self-filled gaps.

| Run | Dates | Squares with a complete record | Stations | r | Median \|d\| | Bias |
|---|---|---|---|---|---|---|
| Ours as published: 2016-07 → 2021-05 | 20 | 6,491 | 106 | 0.660 | 1.68 mm/yr | +0.34 mm/yr |
| His 31 dates, 2016-07 → 2026-03, our rules | 31 | 5,538 | 102 | **0.800** | **1.00 mm/yr** | **−0.01 mm/yr** |
| The same, plus his F38239 merge as written | 31 | 5,538 | 102 | 0.800 | 1.33 mm/yr | +0.77 mm/yr |
| His rules: old nearest-square reference with deep-seated stations, plus merge | 31 | 5,538 | 99 | 0.796 | 1.10 mm/yr | −0.42 mm/yr |
| His published build: his rules, gap-filling, 131 stations | 31 | — | 131 | 0.738 | 1.17 mm/yr | −0.59 mm/yr |

Units are mm/yr LOS. The longer record leaves fewer squares with every product valid (6,491 → 5,538).

- **Pre-registration:** V3 is registered as OPERA against HoustonNet over 2016–2021. Adopting the 2016–2026 record for V3 is a deviation and must be logged with both results. The website OPERA layer and V2 (F38238 products inside the NISAR window) are not affected.
- **Provenance gaps:** `source_file` holds absolute home-directory paths, there are no source checksums, and there are no manifest or freeze entries yet.

### South frame (K2)

- **Bug 1, reference contamination.** `merge_frames` adds F38239 rows for squares that F38238 lacks, including squares inside the reference region. The per-product reference offsets then move by up to 4.5 mm. The last product has no F38239 data, so it does not move. The net effect is about +0.78 mm/yr on every square's rate.
  - **Fix:** take reference offsets from the primary frame only, then merge.
- **Bug 2, missing product.** NASA CMR (queried 2026-11-11) has no F38239 product from 2025-09-23 to 2026-03-22. The latest F38239 secondary date for that reference is 2026-02-14. F38238 has 2026-03-10 and 2026-03-22.
  - His base lacks `5c0513c`, so south squares were filled with their own fitted rate for that interval. That fill is what lets "GPS-only estimates" fall from 1,383 to 54.
  - **Fix:** either give south squares a rate over 2016-07 → 2025-09, labeled with that window, or wait for the product.
- **Sound:** the per-product offsets range from −39 to +26 mm, but the robust spread over 1,085–1,448 overlap squares is 0.5–1.4 mm. Each frame's UTM zone is read from the file.

### Drought placebo (X3)

`backend/hazards.drought_backtest`, using the 2018-08-13 residual and run against every later epoch in turn instead of only the drought epoch 2023-10-04:

- 2023-10-04 (drought): AUC 0.83.
- Non-drought epochs, about as high: 2021-02-04 → 0.85; 2020-05-04 → 0.80; 2020-02-04 → 0.77.
- Other epochs: as low as 0.07 (2021-05-05).
- Across all 20 later epochs the AUC ranges from 0.07 to 0.85.

The 2023 test was one epoch chosen after looking, and the score is not specific to droughts.

### Unsupported copy (X10)

- **"Some areas dropped over 9 feet in four decades."** USGS gives "more than 9 feet and possibly as much as 10 feet" at Pasadena over **1906–1978** (Gabrysch 1982, OFR 82-571), and 7.5 ft over 1943–1973 (Gabrysch & Bonnet 1974, OFR 74-123).
- **Harvey citation.** The cited "Garvin (2018), Flood inundation geospatial data…" is wrong. doi:10.5066/F7VH5N3N resolves to Watson, K.M. (2018), *Data Used to Characterize Peak Streamflows and Flood Inundation Resulting from Hurricane Harvey of Selected Areas in Southeastern Texas and Southwestern Louisiana, August–September 2017*, USGS data release.
- **"Most at-risk areas … −12.5 cm by 2031"** is a projection.

### Repository hygiene

- `web/tsconfig.tsbuildinfo` is committed with changes.
- 1.1 MB of back-test `.npy` files are committed.
- Added data: 50 MB (`data/derived/opera_f38239/`) and 17 MB (`web/public/data/details/`).
- `requirements.txt` adds scikit-learn, which is only needed for X1.

## Recommended integration

Do not merge the branch. It conflicts in 16 files, and its base predates the pre-registration and every fix. Port the following onto `chore/audit-baseline-2026-11-10`, in this order:

1. **K1 data.**
   - Copy the 11 F38238 products and rebuild under region A.
   - Replace the absolute `source_file` paths with granule IDs.
   - Refresh the manifests and the freeze.
   - Log V3 as a deviation, with results under both windows.
2. **K2 south frame**, with both fixes and a test that the reference offsets are identical with and without the merge.
3. **K3, K4 and K5 during the UI pass:**
   - Carry over the components (`Search.tsx`, `Tour.tsx`, `url.ts`, `geo.ts`, `places.ts`, the detail tiles, the bottom-sheet CSS).
   - Use our copy, labels, and `meta` contract.
   - Keep `tests/test_claims_policy.py` green, and add an OpenStreetMap credit.
4. **Leave out X1–X10.** If K6 (Harvey) is wanted, add it later as FEMA context only, with the corrected citation.

## Sources

- NASA CMR granule search, `OPERA_L3_DISP-S1_V1`, frames F38238 and F38239 (queried 2026-11-11).
- Watson, K.M. (2018), USGS data release, [doi:10.5066/F7VH5N3N](https://doi.org/10.5066/F7VH5N3N).
- Gabrysch, R.K. (1982), [USGS OFR 82-571](https://pubs.usgs.gov/publication/ofr82571); Gabrysch, R.K. & Bonnet, C.W. (1974), [USGS OFR 74-123](https://pubs.usgs.gov/publication/ofr74123).
- Blewitt, G. & Lavallée, D. (2002), Effect of annual signals on geodetic velocity, *JGR* 107(B7), doi:10.1029/2001JB000570.
- Wang et al. (2022), *J. Surv. Eng.* 148(4): 04022008 (deep-seated stations; see `docs/factcheck/2026-11-11-source-verification.md`).
