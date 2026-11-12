# Pre-registration v1 (2026-11-10)

Audience: the team, the executing agent, and judges checking that rules came before results.
Machine-readable copy: `config/preregistration.json`. The code must read thresholds from there, not from literals.
Commit hash: recorded in `docs/decisions.md` (D-005 for v1; D-032 for amendment A1), because a file cannot contain its own hash.

## Amendment A1 (2026-11-11), made before any governed result

**What changed.** Deep-seated GNSS stations are removed from reference selection, from the held-out stable check, and from every radar comparison. Those stations are ADKS, LKHU, NETP, TXEX and UHKD. They are removed *after* the v1 alternating split, so no other station changes side.

| Item | v1 | v1.1 |
|---|---|---|
| Reference stations (PR-4) | ADKS, DEN2, NETP, TMCC | DEN2, TMCC |
| Held-out stable stations (PR-5) | COH2, LKHU, THSU | COH2, THSU |
| Region A on 5-pair quality (3 km) | 103 cells | 52 cells |
| Region B on 5-pair quality (5 km) | 289 cells | 146 cells |
| V1 candidates | 63 | 62 |

**Why.** HGSD's own methods paper says these five antennas "are mounted on the top of the inner poles of deep extensometer boreholes", with anchors 549–936 m below land surface. They "were installed to provide stable references for calculating site deformation at other GNSS sites" (Wang et al. 2022, *J. Surv. Eng.* 148(4): 04022008, doi:10.1061/(ASCE)SU.1943-5428.0000399).

Such an antenna moves with the deep anchor, so its near-zero rate does not show that the land surface around it is stable. The radar measures the land surface. For example, the Addicks extensometer recorded 3.88 ft of compaction since 1973, while ADKS, 30 m away, shows −0.5 mm/yr.

**Timing.** No NISAR displacement statistic for any reference cell and no per-cell NISAR rate existed when this amendment was made. It is therefore an amendment, not a deviation.

**What did not change.** Every other rule and threshold is exactly as in v1, and every remaining station keeps its v1 side of the split. (Excluding first and then re-splitting would have swapped COH2/THSU with DEN2/TMCC; that was rejected as a larger change than the physical reason requires.) If region A has fewer than 50 cells after quality over the full epoch set, the pre-registered fallback to region B applies.

## What had been seen when this was written

- **NASA CMR metadata** for every NISAR GUNW granule over the study box (`data/manifests/nisar_track062_inventory_20261110.json`). No granule after 2026-01-01 has been downloaded or opened.
- **Quality fields only** (coherence, valid fraction, connected component) of the five existing pair artifacts, used to check the station and region rules below for feasibility.
- **Metadata only** from the HoustonNet 2024 summary (positions, history, sample counts, rates) and the FEMA cell-context zones.
- **Prior exposure, disclosed.** The provisional build (`data/derived/provisional/build_report.json`) already computed reference statistics and labels for the first pair and the 5-pair chain, using a different, 7-cell reference. Those numbers are superseded and must not be used to tune anything below.

Any change below after a governed result exists is a **deviation** (MASTER §0.4). Log it in `docs/decisions.md` with the old rule, the new rule, the reason, and results under both.

## PR-0. Epoch set

- **Primary:** `NISAR_L2_GUNW_PROVISIONAL_V1`, track 062, frame 016, ascending, HH, product version 1.0.11 (`P05023`). That is the 27 granules in the inventory above: 28 dates, 2025-11-02 to 2026-10-16.
- **Hour-0 additions.** Granules published after this inventory (for example the 2026-10-28 and 2026-11-09 passes delayed by the 2026-10-23 to 11-06 production pause) may be added only at the hour-0 input freeze. Re-run `scripts/nisar_inventory.py`, commit the new inventory, and name it in the run. Nothing is added after hour 0.
- **Partial processing.** If not every granule is processed by the hour-16 checkpoint, use the longest contiguous chain starting 2025-11-02 and report N. No other subset may be chosen.
- **Out of primary scope:** frame 017 (33% of the study box), tracks 134 A, 113 D and 12 D, and the beta collection. Each may appear only as a labeled extension.

## PR-1. Release rule (replaces the loop-closure gate; MASTER 6.4)

A NISAR LOS rate for a cell is **released** only if all of the following hold. The failing part is named whenever a rate is withheld.

- **(a) Quality in every pair used:** the cell is in the main connected component, `coherence_median ≥ 0.40`, and `valid_fraction ≥ 0.50`.
- **(b) Unwrapping continuity:**
  - the main-component condition holds in every pair; and
  - no re-referenced pair displacement has |d| ≥ 60.5 mm. That is half of one 2π cycle, (λ/2)/2 at λ = 0.241962 m. Real 12-day motion in Houston is about 1 mm, so a step of that size is treated as an unwrapping or noise failure.
- **(c) Validation:**
  - **(c1) Method level.** V2 passes under PR-8, and so does V1 whenever V1 is run. A V1 failure fails c1 regardless of V2.
  - **(c2) Cell level.** If a V1 station lies within 1 km of the cell, that station's comparison must pass. Cells with no co-located check are released only when c1 passes. They are marked `method_validated_not_cell_validated`.
- **Strict rule.** The original loop-closure gate is kept as a diagnostic. Under it every cell is `withheld_insufficient_redundancy`. Both results are always reported, and each label names the rule that produced it.

## PR-2. Per-cell resolution test

- Fit cumulative re-referenced LOS displacement against time on the actual acquisition dates (decimal years) by ordinary least squares.
- Residual σ: σ̂ = √(RSS / (N − 2)). Rate uncertainty: σ̂_v = σ̂ / √Σ(t − t̄)².
- **Resolved** iff |v̂| ≥ t₀.₉₇₅,N−2 · σ̂_v, using the two-sided Student-t critical value at α = 0.05: 2.056 at N = 28, and 2.776 at N = 6.
- Every count of resolved cells is reported next to its **expected chance count**: quality-passing cells × 0.05.
- **Sensitivity row:** MASTER's |v̂| ≥ 2σ̂_v.
- **Caveat:** residual σ assumes white noise. Correlated atmospheric noise makes σ̂_v an underestimate, so every resolution statement is a lower bound on the uncertainty.

## PR-3. Headline number

- **Measured σ:** σ_ref is the median per-cell residual σ̂ over the PR-4 reference-region cells.
- **Headline:** the date by which 2σ_v ≤ 5 mm/yr in LOS at σ_ref. Compute it from 2025-11-02 by extending the actual date list at a 12-day cadence with no further gaps. State it as a lower bound.
- **Also report:** today's 2σ_v at σ_ref with the actual N.
- **Planning estimate,** labeled as such: σ = 13 to 18 mm gives today (N = 28) 2σ_v ≈ 17 to 24 mm/yr, and 5 mm/yr resolvable around 2028-01 to 2028-08.
- **Retired:** the website's 8.2 mm / 1.6-year figure and MASTER v3's "130 mm/yr with six epochs". The archive holds 28 epochs.
- **LOS by default.** A vertical-equivalent number may appear only with per-cell incidence and the words "assuming vertical-only motion".

## PR-4. Reference region (MASTER 6.3.2)

- **Stable continuous stations** (HoustonNet 2024 summary), all of:
  - at least 0.5 samples/day averaged over the history;
  - at least 10 years of history;
  - an end date of 2021.0 or later;
  - |up| ≤ 1.0 mm/yr;
  - a cell passing 5-pair quality within 1 km.
- Seven stations qualify. Sort them by ID and alternate:
  - **reference:** ADKS, DEN2, NETP, TMCC;
  - **held-out stable:** COH2, LKHU, THSU.
- **Region A (primary):**
  - cells passing PR-1(a) in every pair of the PR-0 epoch set;
  - within 3 km of a reference station;
  - excluding FEMA `OPEN WATER` cells and cells with OPERA water fraction > 0.5 where that is known.

  Feasibility on 5-pair quality: 103 cells.
- **Region B (alternative):** the same rules at 5 km (289 cells on 5-pair quality).
- **Fallback.** If region A has fewer than 50 cells after quality over the full epoch set, region B becomes primary and A is reported as sensitivity.
- **Re-referencing.** Subtract the region median from every pair. Raw values stay in `pair_los_displacement_raw_mm`.
- **Freeze before measuring.** The region's cell IDs are frozen in a committed data file (plan step B3) after the quality fields are extracted and before any displacement statistic of the region is computed.
- **Limitations:** "away from infrastructure" cannot be checked from the available data. The four reference stations cluster in a few areas, which the methods page states.

## PR-5. Validation stations

- **V1 set:** continuous stations (≥ 0.5 samples/day) with a quality cell within 1 km, excluding the four reference stations. The 2024 summary gives 63 candidates. V1 needs daily ENU for the NISAR window from the newest HoustonNet release; the 2024 release ends around January 2024.
- **HGSD flag.** If HGSD supplies a continuous-versus-campaign flag, it replaces the samples/day proxy. Log the change.
- **Zero-motion check.** For the held-out stable stations (COH2, LKHU, THSU), the NISAR rate in their cell is compared with the GNSS rate under the PR-8 criterion and reported separately.
- **Exclusions.** Campaign-style stations (< 0.5 samples/day) are excluded from V1 and V3. Never mix HoustonNet releases.

## PR-6. Corrections and ramp removal

- **Inventory first.** At plan step B1, list for every granule each correction layer present: ionospheric phase screen, wet troposphere, hydrostatic troposphere, solid-Earth tide. Record the metadata stating whether each is already applied to `unwrappedPhase`.
- **Primary configuration:**
  - apply every correction that the product supplies as a layer and does not mark as applied, exactly once;
  - record `ionosphere_applied`, `troposphere_applied`, `tide_applied`, and the source of each;
  - never apply a correction that an artifact records as applied;
  - a cell whose correction layer is invalid in any pair fails quality;
  - **no plane removal.** Removing a plane from every pair would also remove the planar part of the real regional velocity field over the 28 epochs.
- **Sensitivity:** no corrections; each correction dropped one at a time; primary plus per-pair plane removal.

## PR-7. Labels: a complete partition, evaluated in this order

| Rule ID | Label | Condition |
|---|---|---|
| TG-L1 | Insufficient Radar Evidence | Fails PR-1(a) in any pair of the epoch set |
| TG-L2 | Review Mismatch | A time-matched V1 comparison at the cell disagrees beyond 2σ_comb. Historic velocities never trigger it. |
| TG-L3 | Add Ground Monitoring | Released, resolved (PR-2), overlapping a FEMA SFHA polygon (`flood_exposed is True`), and no continuous GNSS station within 2 km |
| TG-L4 | Investigate Satellite Signal | Released, resolved, `flood_exposed is True`, and a continuous GNSS station within 2 km |
| TG-L5 | Context Only | Everything else. A reason code is required: `rate_withheld:<part>`, `not_resolved`, `resolved_outside_flood_polygon`, or `flood_context_unknown` (`flood_exposed is null`). |

- A null `flood_exposed` never counts as exposed or not exposed.
- The single-pair rule survives only as a labeled sensitivity function and is never exported.
- Flood overlap is part of TG-L3 and TG-L4 because the stated purpose is infrastructure and flood-resilience triage. The card and the methods page say so.

## PR-8. Validation metrics, written before computing

Every validation is reported with: n, exclusions with reasons, median |Δv|, robust scatter (1.4826 × MAD), and Pearson r when n ≥ 30 (V2) or n ≥ 10 (V1). Δv is the rate difference and σ_comb = √(σ_v,a² + σ_v,b²).

- **Pass:** at least 80% of comparisons have |Δv| ≤ 2σ_comb, with n ≥ 10 for V1 and n ≥ 30 for V2. The 80% threshold sits below the ideal 95% to allow for underestimated σ.
- **Informative:** only if the median 2σ_comb ≤ 10 mm/yr. Otherwise the result is reported as "run, not informative" and cannot satisfy PR-1(c1).
- **V2 (cross-sensor):**
  - OPERA DISP-S1 F38238 products available at hour 0 whose dates fall inside the NISAR window;
  - each re-referenced to the PR-4 region;
  - LOS trends fitted over each product's own dates within the common window;
  - each converted to vertical-equivalent with its own incidence, and labeled "assuming vertical-only motion";
  - co-located cells only.
- **V1 (time-matched GNSS):**
  - the station's daily ENU, taking the median within ±1 day of each NISAR date, projected onto NISAR LOS with the cell's look vector;
  - the same OLS fit on the same dates, compared with the NISAR cell rate;
  - the sign convention checked against a synthetic ramp before any comparison is computed.
- **V3 (fallback only):** OPERA against HoustonNet over 2016 to 2021 with the PR-5 exclusions and per-product look vectors. Labeled "method check on OPERA, not NISAR".
- **C4 baseline:** Spearman correlation with V1 GNSS LOS rates for (i) the released NISAR rates and (ii) the raw end-to-end cumulative NISAR displacement with no gates. The designed rule "beats the baseline" only if (i) > (ii). Otherwise that is stated.

## PR-9. Sensitivity

- **Tier 1 (must run):**
  - coherence 0.30 / 0.40 / 0.50 at the primary configuration;
  - region A against region B;
  - primary against no corrections, and against each correction dropped;
  - primary against plane removal;
  - the PR-2 test against MASTER's 2σ test.
- **Tier 2 (if time):** the full cross-product.
- **Reporting:** the percentage of cells whose label changes against primary, by label.
- **Scope cut:** Tier 2 is cut first (MASTER §18).
