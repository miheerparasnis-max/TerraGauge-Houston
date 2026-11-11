# Codebase audit against MASTER v3 (2026-11-10)

Audience: team members and the executing agent.
Scope: the files that MASTER workstreams touch (MASTER §0.2). Nothing in the code, data, or website was changed in this session.
Companion plan: `docs/plan/2026-11-10-execution-plan.md`.

> This file quotes claims-policy phrases as audit evidence. Exclude `docs/audit/` from the G2 claims sweep.

> **Update, same day.** The NASA archive inventory (MASTER 6.2, run after this audit was first written) found 27 track-062 frame-016 pairs on 28 dates through 2026-10-16 (finding A0 below). Statements here that assume six epochs are marked where they change. Decisions taken in response are in `docs/decisions.md`; the rules are pre-registered in `docs/preregistration/2026-11-10-preregistration.md` (commit `1c84d17`).

## How the audit was run

- Repository at `5c0513c` (`main`), plus the untracked `CLAUDE.md` and `MASTER.md`.
- Tests were run twice:
  - with the system `python3` (3.15.2, no `h5py` or `pyproj`);
  - in a clean virtual environment (Python 3.14.8, `pip install -r requirements.txt`, which installed numpy 2.5.4, h5py 3.16.0, pyproj 3.8.0).
- Every number below was read from a committed artifact, or computed with repository code from committed artifacts. The source path is given for each.
- `data/raw/` does not exist on the audit machine. Nothing that needs raw HDF5, NetCDF, RINEX, or the HoustonNet archive could be checked (see "Not audited").
- Pre-registration hygiene (MASTER §0.4): the reference-region feasibility count read quality fields only (coherence, valid fraction, connected component). No displacement statistic was computed for any candidate reference cell.

## Summary of findings, most severe first

| ID | Severity | Finding | Evidence | MASTER | Plan task |
|---|---|---|---|---|---|
| A0 | Critical (resolved by decision) | The archive holds **27 pairs on 28 dates** (2025-11-02 to 2026-10-16) for track 062 / frame 016 / ascending, not 6 epochs. The repo has processed only the first 5 pairs (51.2 GB not yet downloaded). The archive is still a simple chain with no loop closures. Frame 016 covers about 58% of the study box. | `data/manifests/nisar_track062_inventory_20261110.json` | G7, 4.2, 5.3 | D-006, D-007; T1.4 |
| A1 | Critical | The repo's only evidence that corrections were "already applied" is four **geocoding** parameter flags. Nothing shows that phase screens were removed from `unwrappedPhase`. Array correction layers are never recorded. | `backend/ingestion/nisar.py:47-70`, `:174`; all five pair artifacts; `README.md:77`, `:356`; `CLAUDE.md` | 4.4, 6.3.1 | F-2, B1 |
| A2 | Critical | The published website breaks the claims policy at scale: 4,892 strings with "sinking" and 4,919 cells carrying 2030/2035/2040 projections | `web/public/data/cells.json`; `web/src/*`; `backend/insights.py:150-158`; `scripts/export_web.py:142` | 20, G2 | W-2 to W-5 |
| A3 | Critical | Three different detectability headlines are in circulation (1.6 yr, 2.2 yr, 2.7 yr), and none uses a measured per-epoch σ | `web/public/data/meta.json` (`nisar.detect`); MASTER 5.3; chain-vs-pair scatter | 5.3, 22 | PR-3, W-5 |
| A4 | High | λ is 0.241962 m (center frequency 1.239 GHz) in the product metadata, not 0.238 m. λ/(4π) = 19.255 mm/rad, not 18.9. | `data/manifests/nisar_gunw_20251102_20251114.json`; `parameters.wavelength_m` in all five pair artifacts; `README.md:108` | B4 | F-3 |
| A5 | High | 207 FEMA cells with no matching polygon are coerced to `flood_exposed: false`. No cell is ever null. | `backend/ingestion/fema.py:223`; `data/derived/fema_nfhl_houston_cell_context_2026-11-07.json` | B8, CLAUDE.md | F-1 |
| A6 | High | MASTER's "8 add-ground-monitoring cells" is actually 820, plus 158 investigate-satellite-signal, from one 12-day pair | `data/derived/provisional/build_report.json` | 4.2 | Errata E1; D |
| A7 | High | 11 of the 37 split stations (19 reference, 18 held-out) are `PA##` sites averaging about 0.14 samples/day (campaign-style). V1 would use them. | `data/derived/houstonnet_2024_summary.json`; `build_report.json` | 6.1, 6.5 V1 | PR-5 |
| A8 | High | A per-cell 2σ test with 6 epochs (4 degrees of freedom) fires by chance about 11.6% of the time: about 545 false "resolved" cells among the 4,694 quality-passing chain cells. With the archive's 28 epochs (df = 26) it is 5.6%, about 263 cells. | Student-t, df = 4; quality count below | 5.2, 6.3.4 | PR-2 |
| A9 | High | No code reads a look vector. LOS↔vertical uses a fixed 38° incidence and ignores horizontal motion. The NISAR sign convention is not recorded or tested. | `backend/ingestion/provisional.py:238-243`; `backend/insights.py:23-35`; `nisar.py:126` | 6.5, B4 | F-4, B2 |
| A10 | High | The website data is stale against the current build: 108 stations and r = 0.694, against 105 and r = 0.664 now | `web/public/data/meta.json` (last touched in `2d44a42`); `build_report.json` (`5c0513c`) | 0.3, G5 | W-1 |
| A11 | High | Published web numbers trace to `data/derived/provisional/` artifacts that have no manifest. Two inputs are gitignored. | `scripts/export_web.py:56-62`; `.gitignore:11-12` | 0.3 | F-9 |
| A12 | Medium | Checksums are missing for 4 of 5 NISAR granules, the whole OPERA catalog, the FEMA overlay, the extensometer table, and OPERA `20160712_20161016`. Most manifests have no access date. | `data/manifests/*` | 6.2, 14 G1 | F-8, T1.3 |
| A13 | Medium | The raw inputs (5 NISAR HDF5 files and the HoustonNet archive) are not on the audit machine | `data/raw/` absent | B1, V1, V3 | T1.4, T1.8 |
| A14 | Medium | MASTER 5.2 labels are not a complete partition, and rule (c) in 6.4 does not say whether validation is per cell or per method | MASTER text | 5.2, 6.4 | PR-1, PR-7 |
| A15 | Medium | The HoustonNet summary holds vertical rates only: no east or north component, no reference frame, no continuity flag | summary keys | 6.5, 6.6 | T1.5, T1.8 |
| A16 | Medium | `h5py` has no binary wheel for Python 3.15 (the default `python3`). The one test skip is `rasterio`, not `pyproj`. | wheel check; test run | 4.1, 15 | T0.2 |
| A17 | Medium | The demo `sample_cells.json` is the API's default dataset, and no guard or test stops it reaching an output | `backend/api.py:17` | 15 | F-5 |
| A18 | Medium | `CLAUDE.md` and `MASTER.md` are untracked, so pre-registrations cannot cite a commit that contains the rules | `git status` | 0.1, 0.4 | T0.1 |
| A19 | Low | Two tests encode the label rule that MASTER 5.2 replaces | `tests/test_backend.py:51`, `:62` | 5.2 | D-3 |
| A20 | Low | `temporal.py` references to a single cell, not a region. No check exists for unwrapping continuity across epochs. | `backend/ingestion/temporal.py:51-59` | 6.3.2, 6.3.3 | B4, B5 |
| A21 | Low | `detectability()` returns `not_available` instead of failing loudly on invalid input | `backend/detection.py:53-54` | B8 | F-6 |
| A22 | Low | The NISAR collection is `NISAR_L2_GUNW_PROVISIONAL_V1`, version `P05023`. Product maturity is not stated anywhere a reader would see it. | NISAR manifests | 4.4 | T1.3, G page |
| A23 | Low | The GroundTruth template defaults (`antenna_fixed: true`, `cors_overlap: true`, heights `0.0`) would pass silently if copied unedited | `data/groundtruth_session_manifest.template.json` | E3 | E-1 |
| A24 | Low | Git commit metadata carries full personal names and handles. This matters for G3 if the repository is made public. | `git log` | G3 | T1.2 |
| A25 | Low | The README "Next backend work" heading is empty, and "Remaining source work" item 2 asks for cross-pairs the archive does not produce | `README.md:80`, `:290` | 15 | F-10 |

## A. Verification of MASTER §4.2 and §4.1

| MASTER statement | Repository value | Source | Status |
|---|---|---|---|
| Five consecutive 12-day pairs, 2025-11-02 to 2026-01-01, zero redundant edges, rate withheld | Same | `data/derived/nisar_track062_network_diagnostic_20251102_20260101.json` | ✓ |
| Product version P05023 | All five granule names end `_P05023_N_F_J_001`. Collection is `NISAR_L2_GUNW_PROVISIONAL_V1`. | `data/manifests/nisar_houston_track062_temporal_download_plan.json` | ✓, plus provisional collection (A22) |
| Reference median −7.37 mm, scatter 8.16 mm, 7 cells | −7.37 mm, 8.16 mm, 7 cells. These come from the **provisional, ramp-removed** build. The committed evidence artifact has 0 reference cells and null statistics. | `data/derived/provisional/build_report.json`; `data/derived/terragauge_houston_evidence_pair_20251102_20251114.json` | ✓ value, location corrected |
| 8 "add ground monitoring" cells | Single pair: 820 add, 158 investigate. Chain: 616 add, 114 investigate. | `build_report.json` | ✗ (A6) |
| About 18 mm noise against about 0.2 mm motion per 12 days | Pair: 19.4 mm against 0.19 mm. Chain: 18.7 mm against 0.92 mm. Each is a cross-cell standard deviation over 2,514 and 2,368 cells. | `web/public/data/meta.json` (`nisar.pair`, `nisar.chain`) | ✓ approximately. It is a spatial scatter, not a per-epoch temporal σ (see B2). |
| σ_v ≈ 130 mm/yr at N = 6 | 131.0 mm/yr | `backend/detection.py:14` | ✓ |
| N ≈ 83 epochs, about 2.7 yr, mid-2028 | N = 84, 2.73 yr, 2028-07-25 | `backend/detection.py:14` (first integer N with 2σ_v ≤ 5 mm/yr) | ✓ (84 after rounding up) |
| OPERA F38238: 449 granules, 2016-07-12 to 2026-03-22 | 449 granules, same span, about 150 GB, no checksums | `data/manifests/opera_disp_s1_f38238_full_catalog_20261108.json` | ✓ |
| Repo processed 2016 to 2021 | 20 products: a 19-product chain 2016-07-12 to 2021-05-05, plus one product 2016-07-12 to 2016-10-16 | `data/derived/opera_disp_houston_*` | ✓ |
| HoustonNet: 257 stations, windows end no later than 2024.07 | 257 stations. The latest end is **decimal year** 2024.071 (about 2024-01-27, not July 2024). 221 stations end in 2022 or later. | `data/derived/houstonnet_2024_summary.json` | ✓ value, reading corrected |
| USGS groundwater 2025-01-01 to 2026-11-07 | 41 series, observations 2025-01-01 to 2026-11-06 | `data/derived/usgs_houston_groundwater_2025-01-01_2026-11-07.json` | ✓ |
| Extensometer and compaction for 2023 | 14 stations, 1973-07-13 to 2023-12-29 (2023 release) | `data/derived/usgs_houston_extensometer_compaction_2023.json` | ✓ |
| FEMA `flood_exposed` may be null | Never null: 6,852 false, 2,259 true. The 207 cells with no polygon are false. | `fema_nfhl_houston_cell_context_2026-11-07.json` | ✗ (A5) |
| GroundTruth: template only | Template only | `data/groundtruth_session_manifest.template.json` | ✓ |
| 48 tests; 3 errors and 1 skip without `pyproj` | 48 tests. The 3 errors are `pyproj`/`h5py` (`test_compaction`, `test_quality` bbox, `test_usgs`). The skip is `rasterio`. A clean 3.14 venv gives 47 pass, 1 skip. | test runs | ✓ with correction (A16) |
| 25 commits, Nov 6 to Nov 9 | 25 commits, 2026-11-06 21:05 to 2026-11-09 07:55 (UTC−6) | `git log` | ✓ |
| The 19 reference and 18 held-out stations come "from `houstonnet_2024_summary.json` and the reference candidates file" | The split is computed at build time by `stable_gps_reference()` (alternating sorted IDs, ≥10 yr history, \|up\| ≤ 1 mm/yr), not from the candidates file. 6 reference and 5 held-out stations are `PA##` campaign-style. | `backend/ingestion/provisional.py:215`; `build_report.json` | Partial (A7) |

## B. Science code (detail)

### B1. Atmospheric and ionospheric corrections (A1)

All five pair artifacts record exactly these flags, as strings:

```
/science/LSAR/GUNW/metadata/processingInformation/parameters/geocoding/azimuthIonosphericCorrectionApplied   = "True"
/science/LSAR/GUNW/metadata/processingInformation/parameters/geocoding/rangeIonosphericCorrectionApplied     = "True"
/science/LSAR/GUNW/metadata/processingInformation/parameters/geocoding/wetTroposphericCorrectionApplied      = "True"
/science/LSAR/GUNW/metadata/processingInformation/parameters/geocoding/hydrostaticTroposphericCorrectionApplied = "True"
```

- These flags sit in the **geocoding** parameter group. Flags in that group most likely describe delay corrections applied to geolocation. That is a different thing from removing a phase screen from `unwrappedPhase`. This must be confirmed against the GUNW specification and `inspect-h5` output on a raw granule.
- `_processing_corrections()` keeps only scalar datasets whose names contain three tokens (`nisar.py:60-63`). Array layers, such as an ionosphere phase screen or tropospheric and tide lookup tables, can never be recorded. The artifacts therefore cannot show whether those layers exist.
- The adapter itself applies no correction (`nisar.py:174`).
- **Conclusion.** As far as the repository can show, no phase correction has been applied to the NISAR values. That matches MASTER 4.4. The "already applied" statements in `README.md:77`, `README.md:356`, and `CLAUDE.md` rest on a misread flag.

### B2. Detectability headline (A3)

| σ per epoch | Where it comes from | N for 2σ_v ≤ 5 mm/yr | Years | Date from 2025-11-02 |
|---|---|---|---|---|
| 8.16 mm | 7-cell provisional reference scatter, single pair (**currently on the website**) | 50 | 1.61 | 2027-06-13 |
| 12.73 mm | 18 mm ÷ √2 (per-acquisition noise, if pair noise is the difference of two epoch noises) | 67 | 2.17 | 2028-01-03 |
| 18.0 mm | MASTER 5.3 planning value | 84 | 2.73 | 2028-07-25 |
| 19.38 mm | Cross-cell standard deviation of the ramp-removed pair | 88 | 2.86 | 2028-09-11 |

All rows assume white noise, 12-day spacing, no gaps, and the repo function `rate_uncertainty_mm_year`.

The 60-day chain sum has almost the same cross-cell scatter as one 12-day pair: 18.7 mm against 19.4 mm. If each pair's noise were independent, a five-pair sum would scatter about √5 × 19.4 ≈ 43 mm. The near-equality points to acquisition-level noise that cancels at the intermediate dates. Under that model the per-epoch σ is closer to 13 mm than 18 mm.

**Update (A0).** With the archive's 28 actual dates, 2σ_v today is about 17 mm/yr (σ = 12.73 mm) to 24 mm/yr (σ = 18 mm). The 5 mm/yr dates in the table barely move. MASTER v3's "130 mm/yr with six epochs" no longer describes the data that exist.

Caveats: this is a spatial statistic, not a temporal one; the fields were ramp-removed; and real correlated noise makes any of these a lower bound. MASTER §22 already requires the headline to come from measured residuals. The point here is that the website's 1.6-year figure must be withdrawn, and the planning estimate must name its σ.

### B3. Wavelength (A4)

The manifest records `center_frequency_hz = 1239000000.0` and `wavelength_m = 0.241962`. The pair artifacts were extracted with 0.241962 m, so the derived displacements are consistent with the metadata. The README example (`README.md:108`) and MASTER B4 use 0.238 m and 18.9 mm/rad. The correct test value for this product is λ/(4π) = 19.255 mm/rad. One full 2π unwrapping error equals 121.0 mm of LOS displacement.

### B4. Per-cell resolution test at low N (A8)

With N = 6 epochs, a straight-line fit leaves 4 degrees of freedom.

- The two-sided chance that |v̂| ≥ 2σ̂_v under zero motion is 0.116 (Student-t, df = 4).
- The 95% critical value at df = 4 is 2.776.
- Across the 4,694 cells that pass quality in all five pairs (coherence ≥ 0.4, valid ≥ 0.5, main connected component), that is about 545 cells "resolved" by chance.

Any label that depends on "resolved at 2σ" needs a pre-registered test that accounts for this.

### B5. Geometry and sign (A9)

- No module reads NISAR incidence, azimuth, or LOS unit-vector layers.
- `compare_opera_gps` multiplies the GPS vertical rate by cos 38° and ignores horizontal motion (`provisional.py:238-243`).
- The website converts every OPERA LOS rate to "vertical" with the same fixed angle (`insights.py:23-35`).
- The OPERA velocity artifact states "Positive = toward the satellite". The NISAR artifacts state no sign convention, and `phase × λ/(4π)` (`nisar.py:126`) has no synthetic-ramp test.
- A sign mismatch would flip the agreement in V1 and V2.

### B6. Reference region feasibility (quality fields only)

These counts were computed during the audit. They are not results and must not be published.

| Quality gate in all 5 pairs | Cells |
|---|---|
| coherence ≥ 0.3 | 4,798 |
| coherence ≥ 0.4 | 4,694 |
| coherence ≥ 0.5 | 4,155 |
| coherence ≥ 0.7 | 680 |

- 28 HoustonNet stations are continuous (≥ 0.5 samples/day), have at least 10 years of history, and have |up| ≤ 1 mm/yr.
- Within 3 km of one of them there are 175 chain-quality cells at coherence ≥ 0.4. Within 5 km there are 452.
- A ≥ 50-cell pre-registered region is therefore feasible.
- Today's 7-cell region exists because `nearest_cell_ids()` takes only the single nearest cell per station (`provisional.py:224-233`), and 12 of those 19 cells fail quality.

### B7. Validation inputs

- **HoustonNet.** `PA##` stations (97 sites) have a median of 0.14 samples/day; the other 160 have 0.94. Campaign-style stations in the current split: reference PA00, PA26, PA32, PA43, PA52, PA58; held-out PA20, PA28, PA39, PA50, PA54. The summary has no east or north component, so a true ENU→LOS projection needs the raw archive (`data/raw/HoustonNet_2024_Data_Release.tgz`; its SHA-256 is in `data/manifests/houstonnet_2024.sha256`).
- **OPERA over the NISAR window.** 12 catalog granules share reference date 2025-09-23, with secondaries every 12 days from 2025-11-10 to 2026-03-22 (about 350 MB each). Six of them (2025-11-10 to 2026-01-09) bracket the NISAR window. Their dates fall 8 days after the NISAR acquisitions, so V2 must compare windows, not pairs. `scripts/fetch_opera_extension.py` downloads a long chain, not this window.

## C. Claims audit (MASTER G2)

Method: a case-insensitive search for every G2 term, plus "forecast" and "projection", over `README.md`, `CLAUDE.md`, `backend/`, `scripts/`, `web/src/`, and `web/public/data/`.

**Affirmative breaches (rewrite or delete):**

- `web/src/labels.ts:11-14`, `:53-60`: priority meanings and the "Sinking about X a year" headline.
- `web/src/App.tsx:23-24`, `:77` ("Where is Houston's ground sinking?"), `:98`, `:118`, `:126`, `:137`: map title, future-year selector, projections.
- `web/src/Card.tsx:13-31`, `:82`, `:91`, `:104` ("Too few passes yet to measure Houston's slow sinking", which is close to the forbidden "NISAR cannot" framing; the policy says it is a time question), `:117`.
- `web/src/Pages.tsx:47`, `:50`, `:65-74` ("Can we predict where it will go?"), `:90`, `:129-141`.
- `backend/insights.py:150-158`: the priority reason strings. These are the source of the 4,892 strings in `cells.json`. Also `:130`, the straight-line projection.
- `scripts/export_web.py:142`, `:179`, `:203`: writes `future` for 4,919 cells and a forecast block.
- `README.md:303-310`: "Future: projection to 2030/2035/2040", "converted to vertical", "why NISAR can't measure this yet". `README.md:285`: "proves" (use "shows").

**Negations.** The meaning is acceptable, but G2 says reword every hit: `README.md:5`, `CLAUDE.md:7`, `web/src/Card.tsx:115` ("does not say this spot will flood"), `web/src/App.tsx:147`, `backend/detection.py:4`, `backend/ingestion/fema.py:123`, `:151`, `:234`, `backend/ingestion/houston.py:133`, `backend/service.py:39`.

**False positive:** `README.md:321` ("approves").

**Related safeguard breach.** The website's "Movement" value is OPERA LOS converted to vertical. The README's own safeguard says LOS motion is not automatically vertical.

## D. Engineering hygiene (MASTER §15)

| Check | Result |
|---|---|
| Clean venv, all tests pass | Python 3.14.8: 48 run, 47 pass, 1 skipped (`test_raster_layers…test_dswx_water_fraction_and_masking`, because `rasterio` is not in `requirements.txt`). Python 3.15: `h5py` has no binary wheel for macOS arm64. |
| `sample_cells.json` cannot reach a published output | `export_web.py` does not read it. However, nothing rejects `dataset_status: demonstration_only_replace_with_source_derived_outputs`, the API serves it by default (`backend/api.py:17`), and `/v1/summary` does not expose `dataset_status`. No test. |
| `data/raw/` gitignored, no raw granule committed | ✓ `.gitignore:5`. No `.h5`, `.nc`, `.tgz`, RINEX, or `.tif` tracked. |
| Derived JSON about 119 MB | ✓ 119 MB across 43 tracked files in `data/derived/`. Of the provisional outputs, `build_report.json`, the OPERA velocity file, and the comparison are tracked. The ramp-removed pairs and evidence files are gitignored but read by `export_web.py`. |
| README "Next backend work" | Empty heading (`README.md:80`) |
| CLAUDE.md correction (4.4) | Not made. The file is also untracked. |

## E. Test coverage against MASTER B8 and §15

| Requirement | Existing test | Status |
|---|---|---|
| Rate withheld when the release rule (6.4) fails | `test_temporal.test_chain_is_explicitly_withheld` (old redundancy rule only) | Missing for 6.4 |
| Cells below 50% valid pixels never receive a positive label | `test_backend.test_low_quality_is_insufficient_data` covers coherence only | Partial |
| A flood null is never coerced | `test_houston_build…withholds_cell_flood_label` covers the join with no context. Nothing covers the FEMA no-match case. | Missing, and the code breaches it (A5) |
| Double application of a correction is rejected | None | Missing |
| Planning equation gives about 130 mm/yr at N = 6 | `test_rate_uncertainty_shrinks_with_more_observations` checks monotonicity only | Missing |
| Detectability fails loudly on invalid input | None. `detectability()` returns a status. | Missing, needs a design decision (A21) |
| λ/(4π) value and sign against a synthetic ramp (B4) | None | Missing |
| Demo data cannot reach an output (§15) | None | Missing |

## F. Proposed errata to MASTER v3 (record in `docs/decisions.md`)

1. **E1** §4.2: the single-pair label summary is 820 add-ground-monitoring plus 158 investigate-satellite-signal cells, not 8.
2. **E2** §4.2: the −7.37 / 8.16 mm / 7-cell statistics come from the provisional, ramp-removed build (`data/derived/provisional/build_report.json`). The committed evidence artifact has no reference region.
3. **E3** §4.2: "2024.07" is a decimal year (about 2024-01-27).
4. **E4** §4.2 and §4.3: `flood_exposed` is currently never null; 207 cells are coerced to false.
5. **E5** §4.1: the skipped test needs `rasterio`, not `pyproj`.
6. **E6** §5.3: the repo function gives N = 84 (2028-07-25). The 18 mm σ is a cross-cell scatter, not a measured per-epoch σ (B2).
7. **E7** §6.5 V1: the 19/18 split is computed by `stable_gps_reference()`, not taken from the candidates file. 11 of the 37 stations are campaign-style.
8. **E8** §8 B1 and B4: λ = 0.241962 m (1.239 GHz) per product metadata, so λ/(4π) = 19.255 mm/rad.
9. **E9** §5.2 and §6.4: a released, resolved rate outside a flood polygon has no label; Investigate and Add need a stated precedence; rule (c) needs a stated scope.
10. **E10** §4.4: the repo-side evidence supports the correction. The flags behind "already applied" are geocoding flags.
11. **E11 to E15** (from the archive inventory): see `docs/decisions.md` D-003. E11, together with E1 and E8, was corrected in MASTER v3.1 (commit `cee7f3c`).

## Not audited

These need raw data, network access, or a person:

- Raw GUNW layers: the correction layers, geometry layers, sign documentation, and whether P05023 fixed the January 2026 sample-data issues.
- ~~ASF holdings beyond the five known granules, and Earthdata alerts.~~ Done the same day: `docs/decisions.md` D-006.
- Newer HoustonNet releases, and campaign-versus-continuous metadata from HGSD.
- The website build (`npm run build`) and runtime UI behavior.
- GroundTruth Node logs.
- Files no workstream touches: `compaction.py`, `usgs.py` internals, `raster_layers.py`, and `cli.py` beyond the flags used.
