# TERRAGAUGE HOUSTON: MASTER EXECUTION PROMPT (v3.1)

Supersedes v3 (2026-11-10 corrections; see the changelog at the end and `docs/decisions.md`). v3 superseded v2. Audience: the executing agent (Claude Code) and every team member.
Scope: NASA Space Apps 2026 only ("Dancing with the SARs", Houston Local Event). Veritas is removed from this project.
Out of scope until the science is locked: new UI views or visual redesign. Website changes only where copy must be corrected to meet the claims policy.

---

## 0. Operating rules

1. Read `CLAUDE.md` and the README "Science safeguards" section before changing anything. They are binding, except where Section 4.4 below corrects them. Update those files in the same commit as any change in behavior.
2. Do not re-audit the whole repository. Audit only the files a workstream touches.
3. Every number in any output (JSON, slide, page, script) must trace to an artifact in `data/derived/` with a manifest entry in `data/manifests/`. Untraceable numbers do not ship.
4. Pre-register before you look. Every threshold, reference region, held-out list, gate rule, or metric is written to a file and committed before the result it governs is computed. Record the commit hash in the output. Changing a gate after seeing results is allowed only if it is logged as a deviation with the reason and the results under both the old and new rule.
5. Small verified steps. Run `python3 -m unittest discover -s tests -v` after each change. Never weaken or skip a test to make it pass.
6. Never fabricate a result. Missing data produces "withheld" with the reason. Honest absence is an accepted result.
7. Prefer deleting an overclaim to softening it.
8. End every session with the worklog defined in Section 17.

---

## 1. Mission and win thesis

### 1.1 Plain-language mission (use this wording wherever outsiders read)

NASA's new radar can see parts of Houston's ground moving. One radar image cannot tell you how fast the ground is moving or whether the movement is real. TerraGauge tells you how long NASA's radar, and independent GPS, would need to answer that question here, and where to look first.

### 1.2 Win thesis

A quantified, honest answer to "how long until this NASA radar signal can be trusted?", backed by real NISAR data, an explicit validation result (or an explicit statement that validation was not possible yet), and a clear account of what the number cannot mean.

Target awards:
- **Best Use of Science** (primary): NISAR time series, quality gating, detectability, validation.
- **Local Impact** (primary): a Houston decision question, stakeholder feedback, and a result a Houston analyst can act on.
- **Best Use of Data** (secondary): NISAR + OPERA + HoustonNet + USGS + FEMA combined with provenance and explicit time-matching.

Do not optimize for Best Use of Technology.

### 1.3 Realistic target ladder

1. Local award at the Houston event.
2. Global Nominee (roughly top 11% of submissions in 2025).
3. Best Use of Science or Best Use of Data shortlist.
4. Global Winner is a tail outcome. Do not plan the schedule around it.

---

## 2. Judging criteria mapped to deliverables

| Criterion | What judges look for | Required artifact | Status (as of v3) |
|---|---|---|---|
| Relevance | Uses the challenge's NASA data for its question | NISAR is the observation layer of the time series | **Weak.** NISAR is currently a quality preview |
| Validity | "Scientifically valid? Works in the real world?" | Validation result, or a stated validation limit, plus a detectability number | **Weak.** No validated NISAR rate |
| Influence | Would someone act on it | A named Houston decision and stakeholder feedback | **Missing** |
| Creativity | Fresh framing | "How long until NASA radar can confirm this?" as the central number | **Present in plan; not yet in results** |
| Presentation | Clear to a non-expert in 30 seconds and on the page | Outsider script, glossary, standalone project page | **Not started** |

---

## 3. Eligibility gates

### G1. Pre-event work

The team is running a pre-kickoff sprint hosted by an intern. The git history contains 25 commits from Nov 6 to Nov 9. Whether pre-event code is allowed for Global Judging is the rule question, and an internal sprint does not answer it. Action: get the organizers' answer in writing (one email, by Nov 12), save it to `docs/rules/`, and disclose the pre-event history in a "Development history" section on the project page regardless of the answer.

Fallback if the answer is no: at kickoff, create a clean public repository `terragauge-houston`, re-run the pipeline from raw downloads, carry forward only pre-event documentation labeled as such, and disclose the prior work.

### G2. Official challenge statement

Read the official "Dancing with the SARs" statement and resources (official resources were scheduled for Nov 13). Save to `docs/rules/challenge-statement-2026.md` with the access date. Confirm the project answers the statement as written.

### G3. Under-18 likeness and voice rule

Recognizable names, voices, and likenesses of persons under 18 are excluded. Assume the team is under 18.
- Default format: slide deck, at most seven slides including the title. No faces, no team voice recordings.
- If a video is required, it must be voiceless or use a method the Local Lead approves in writing.
- The deck template asks for team member names. Resolve the conflict with the Local Lead before the title slide is built.

### G4. Team roster

Space Apps allows 1 to 6 members, all registered and listed before submission closes. Record each member's registration status and role in `docs/team.md`.

### G5. Scope decision (resolved)

Veritas is removed. This repository and the entire submission are Space Apps only. No Veritas code, write-up, or video will be produced from this project.

### G6. AI disclosure

The team builds with AI-assisted coding. Disclosure is mandatory under Space Apps rules: list every AI tool, where and how it was used, and acknowledge AI-assisted code and data work in the text. Draft `docs/ai-use.md` now and maintain it.

### G7. NISAR data status (researched; see Section 6)

Two facts settle the plan:
- NISAR GUNW products are generated for nearest-neighbor 12-day pairs only. The product specification says only co-polarized nearest-neighbor (12-day) GUNW products are generated as part of the mission. Cross-pairs (24-day, 36-day) are therefore not in the archive, and the loop-closure gate in the repo cannot be satisfied from the archive. ASF staff have acknowledged this in public forum threads and said a roadmap would appear in the next NISAR data user guide update. Do not plan on it.
- [v3.1] Resolved 2026-11-10: the archive holds 27 track-062 frame-016 ascending pairs on 28 dates, 2025-11-02 to 2026-10-16 (`data/manifests/nisar_track062_inventory_20261110.json`). All are nearest-neighbor; two 24-day pairs bridge missed acquisitions, so it is still a chain with no loop closures. The repo has processed only the first five pairs. Provisional production paused 2026-10-23 to 2026-11-06, so later passes may still appear; re-run the inventory at the hour-0 freeze.

---

## 4. Current state (superficial read, plus research)

### 4.1 What exists

- Dependency-free Python API (`backend/`) with explainable rules, quality-gate enforcement, GNSS session-noise math, and a NISAR temporal-network diagnostic.
- Ingestion adapters (`backend/ingestion/`) for NISAR GUNW, OPERA DISP-S1, HoustonNet, USGS groundwater and extensometer, FEMA NFHL, GNSS, and raster layers. Each writes provenance JSON.
- A temporal gate that withholds a rate unless the network has at least two independent loop-closure edges.
- A provisional build that prioritizes using OPERA-based velocities, flagged `provisional_unreviewed`.
- 48 tests. Three errored and one was skipped in a shell without `pyproj`. This is an environment dependency and must be fixed by installing requirements in a clean virtual environment.

### 4.2 Key numbers (verify each against its artifact)

- **NISAR track 062, frame 016, direction A (Houston):** five consecutive 12-day pairs covering 2025-11-02 to 2026-01-01 have been processed. Zero redundant edges. Rate status: `withheld_insufficient_redundancy`. [v3.1] The archive holds 27 pairs on 28 dates through 2026-10-16 (see G7).
- **First NISAR pair reference statistics:** reference median −7.37 mm, reference scatter 8.16 mm, from only 7 reference cells. [v3.1] The provisional label summary contains 820 "add ground monitoring" and 158 "investigate satellite signal" cells from a single 12-day pair (`data/derived/provisional/build_report.json`). Those labels are not publishable.
- **Per-pair noise versus signal (CLAUDE.md):** about 18 mm noise per pair versus about 0.2 mm expected motion over 12 days (about 6 mm/yr).
- **OPERA DISP-S1, frame F38238:** the repo processed the 2016 to 2021 stack. The full catalog manifest lists 449 granules spanning 2016-07-12 to 2026-03-22. Only the early portion has been used. Rates require re-referencing the full series to a reviewed stable patch and validation against co-temporal GNSS.
- **HoustonNet (2024 release):** 257 station velocities in `houstonnet_2024_summary.json`. Station windows end no later than 2024.07. No daily series in the repo; the raw archive is gitignored and local-only.
- **USGS:** groundwater records 2025-01-01 to 2026-11-07; extensometer and compaction record for 2023.
- **FEMA:** station-point join and polygon overlay exist; `flood_exposed` may be null.
- **GroundTruth Node:** hardware has arrived and raw logs exist (per the team). The repository holds only a template manifest; the session logs, RINEX files, and static solutions still need to be processed and recorded.

### 4.3 Gaps that matter most

1. The primary science is OPERA, not NISAR. The challenge is about NISAR.
2. The loop-closure gate cannot pass from the NISAR archive (see G7). The gate needs to be replaced with a rule that can pass, with its change logged as a deviation.
3. No validation is time-matched to NISAR yet.
4. The reference region has 7 cells. It needs to be expanded and pre-registered.
5. The labeling rule is scientifically fragile (Section 5.2).
6. No stakeholder feedback.
7. No outsider-facing narrative yet.
8. [v3.1] Resolved: the archive continues to 2026-10-16 (G7). The gap is now processing: 22 pairs (about 51 GB of the 62.7 GB set) are not yet downloaded or ingested.

### 4.4 Corrections to CLAUDE.md and the README

- **Atmospheric corrections.** CLAUDE.md states that NISAR GUNW products "already include tropospheric/ionospheric corrections." The product specification says the estimated ionospheric phase screen is included but not applied to the data layers by default, and that lookup tables for solid Earth tides and hydrostatic and wet tropospheric phases are included but not removed. This is a correction that matters for the science. Replace the sentence with: "GUNW includes an ionospheric phase screen and tropospheric and tide lookup tables that are not applied by default. TerraGauge applies each correction exactly once, records which were applied in the artifact, and never applies a correction that the artifact already records as applied." Update the code to write the applied-correction flags explicitly.
- **Sample-data caveats.** NISAR's January 2026 sample release reported three GUNW issues: the wrapped interferogram was misgeoreferenced (the unwrapped layers were not affected), ionosphere-layer edge artifacts, and no rubbersheeting for local distortion. Confirm whether the Houston production granules (granule names carry product version P05023) have these fixed, and record the product version used.

---

## 5. Strategic decisions (recommended; log each in `docs/decisions.md` with date)

### 5.1 Observation architecture

- **NISAR** is the observation layer of the time series. The chain of 12-day pairs is the only NISAR network the archive provides, so the time series is built from consecutive pairs.
- **OPERA DISP-S1** is the long-history and cross-sensor check, including 2025 to March 2026 over the same window.
- **HoustonNet (newest release)** is the GNSS reference for time-matched validation.
- **USGS** provides mechanism context only.
- **FEMA** provides exposure context only.

### 5.2 Labeling rules (replace the single-pair rule)

Labels apply only to cells that pass the quality gate and whose rate status is released (Section 6.5).

- **Investigate Satellite Signal:** the cell's NISAR rate is resolved at 2σ (|v_LOS| ≥ 2σ_v), stable under coherence checks (0.3, 0.4, 0.5), validated under the release rule, and overlapping an FEMA flood polygon. State on the card and the methods page that flood overlap is included because the purpose is infrastructure and flood-resilience triage.
- **Add Ground Monitoring:** the same, with no permanent GNSS station within 2 km.
- **Context Only:** historic OPERA, groundwater, compaction, or flood context exists but the NISAR rate is not released.
- **Insufficient Radar Evidence:** fails the quality gate.
- **Review Mismatch:** reserved for a time-matched GNSS comparison that disagrees beyond uncertainty. It is never shown from historic velocities.

Each label carries its rule identifier, every threshold, the source values with units and dates, and the limitation string.

### 5.3 Headline number

The headline is a detectability time computed from data.

Planning estimate (replace with measured values once computed):
- σ_v = (σ/Δt)·√(12/(N(N²−1))), σ = 18 mm per epoch, Δt = 12 days ≈ 0.0329 years, white-noise assumption.
- For 2σ_v ≤ 5 mm/yr, N ≈ 83 epochs, about 2.7 years.
- Starting from the first pair on 2025-11-02 and assuming gap-free 12-day acquisitions, the planning estimate for the earliest resolvable 5 mm/yr is about mid-2028. Correlated atmospheric noise makes the real date later. State this as a lower bound.
- [v3.1] With six epochs (N = 6) the formula gives σ_v ≈ 130 mm/yr, but the archive now holds 28 epochs. On the actual dates, σ = 18 mm gives σ_v ≈ 11.8 mm/yr (2σ_v ≈ 24 mm/yr), and σ = 13 mm gives 2σ_v ≈ 17 mm/yr. The 5 mm/yr date stays around 2028 (early to mid). The pre-registered headline (`docs/preregistration/`, PR-3) uses the measured σ, not these planning values.

Outsider wording: "At today's NASA radar noise, a slow Houston rate of 5 mm per year would need roughly 2.7 years of observations before we could be confident it is real. If the satellite keeps imaging every 12 days, that point arrives around mid-2028."

### 5.4 GroundTruth Node

Report honestly. If the session logs, RINEX files, and at least three valid static solutions exist by the hour-24 checkpoint, publish the vertical repeatability with its conditions. If not, publish the prototype limitation with no detectability number. The node never measures land motion in any output.

---

## 6. NISAR and HoustonNet: the research-based path

This section answers the two questions the team could not settle. The evidence comes from the NISAR product documentation, ASF forum statements, the NISAR sample-data release notice, and HGSD and Fort Bend Subsidence District publications. Verify the items marked [VERIFY] before relying on them.

### 6.1 What the evidence says

**NISAR archive structure.**
- GUNW products are generated only for co-polarized, nearest-neighbor 12-day pairs (NISAR documentation, nisar-docs.asf.alaska.edu/gunw).
- ASF staff confirm that GUNW products are primarily generated for 12-day pairs. Users have requested 24-day and 36-day pairs for SBAS (forum.earthdata.nasa.gov, "Will ASF HyP3 support NISAR?"). A roadmap was promised for the next data user guide update. [VERIFY current status.]
- Consequence: the archive cannot provide the loop-closure redundancy that the current gate requires. The gate must be changed by a logged, pre-registered deviation, and the change must be justified by something other than convenience (see 6.4).

**NISAR corrections.**
- The ionospheric phase screen is included but not applied by default. Tropospheric and tide lookup tables are included but not removed. (Product overview, GUNW specification.)
- The January 2026 sample-data notice listed GUNW limitations: misgeoreferenced wrapped interferogram (unwrapped layers unaffected), ionosphere edge artifacts, no rubbersheeting. [VERIFY whether Houston production granules have these fixed.]

**NISAR processing caveats.**
- The GUNW product is provided as is. Users apply their own masking and unwrapping-error checks. Coherence and connected components are the quality markers.

**HoustonNet.**
- Daily East-North-Up time series and velocities are released through HGSD. Processing is done by the University of Houston Geodetic Laboratory. The network is reprocessed every few years with updated software and reference frames.
- The recommended reference frame for delineating subsidence is Houston20 (realized by about 25 long-history stations outside the subsiding area). GOM20 is recommended for Gulf Coast and sea-level work.
- The authors recommend using the most recent release and not mixing old and new positions.
- Fort Bend Subsidence District states that some of its GPS observations are collected for about seven days every two months. Those stations do not provide continuous daily series and must not be treated as continuous in time-matched comparisons.
- News coverage from July 2026 reports that the HGSD 2025 report used data from nearly 190 GPS stations, so a release covering 2025 and 2026 exists or is being prepared. [VERIFY.]

**Existing district work (relevant to originality).**
- HGSD and Fort Bend use Sentinel-1 satellite data to map regional surface movement. Judges may ask what TerraGauge adds. The answer must be specific: NISAR-based, detectability-first, and explicit about validation and what the labels do not mean. TerraGauge does not replace district monitoring.

### 6.2 Path A: NISAR archive inventory (do first; about 10 minutes)

Owner: science lead. Output: `data/manifests/nisar_track062_inventory_YYYYMMDD.json`.

1. In ASF Vertex (or the ASF Search Python module), search: product NISAR L2 GUNW, track 062, frame 016, direction A (ascending), start 2025-11-01, end today, Houston bounding box (about −95.95, 29.4, −94.8, 30.2).
2. Record every granule: ID, reference date, secondary date, processing version, creation date, file size, and checksum.
3. Answer two questions in writing:
   - Are there granules with dates after 2026-01-01? If yes, list them.
   - Are there any non-consecutive pairs (for example 2025-11-02 to 2025-11-26)? If yes, list them. The product documentation says none are generated, so expect none.
4. Check the Earthdata or ASF alerts page for any NISAR data gap or production pause affecting Houston dates after 2025-11-01. Record the alert text and date.
5. Record the answers in `docs/decisions.md`.

Decision tree:
- If 2026 granules exist: download them, ingest with the existing `nisar-gunw` adapter, extend the chain. Continue to 6.3.
- If they do not exist: the NISAR time series stops at six epochs. Present the 130 mm/yr result honestly as the current state and the 2028 planning date as the forward path. Continue to 6.3 with the six-epoch chain. Do not invent epochs.

### 6.3 Path B: NISAR processing decisions (pre-register before running)

1. **Corrections.** Apply the ionospheric phase screen once (it is provided in the product). Apply the tropospheric and tide lookup tables once. Record in every artifact: `ionosphere_applied`, `troposphere_applied`, `tide_applied`, and the source of each. Make the applied-correction flags part of the artifact contract and add a test that rejects double application. Run the analysis with and without each correction to show the sensitivity. [This is the correction the existing repo has to implement; see 4.4.]
2. **Reference region.** Expand from 7 cells to at least 50. Pre-register a rule: high coherence in every pair of the chain, away from water and infrastructure, and within or adjacent to the Houston20 long-history stations' stable area. Commit before running per-cell rates. Test at least two alternative reference regions and report label stability.
3. **Time series.** For each quality-passing cell, build cumulative LOS displacement relative to the first epoch by summing re-referenced pair values along the chain. Check that unwrapping is continuous across epochs using connected-component and coherence continuity.
4. **Rate fit.** Linear least-squares rate over the epochs, with uncertainty from the residuals. Compute σ_v from the fit using the actual N and Δt. Report the detectability N for 2σ at 5 mm/yr.

### 6.4 Gate change (logged deviation)

The redundancy gate was designed for a network with independent loop closures. The archive does not provide loop closures, so the gate cannot pass for any cell. This is a real change, and it must be disclosed as one.

The replacement rule, written before any rate is computed:

A NISAR rate is released for a cell only if all of the following hold:
- (a) the quality gate passes on every epoch used;
- (b) the connected-component and coherence checks show no unwrapping discontinuity along the chain;
- (c) the rate passes at least one independent validation test in Section 6.5, within its stated uncertainty.

The redundancy gate remains in the code as a diagnostic that is reported alongside the new rule. Results are shown under both rules: strict (withheld, because there are no loop closures) and validated (released only when 6.5 passes). The page must say which rule produced each label.

Why this is defensible rather than convenient: a chain has no internal check on unwrapping errors, so the release now depends on an external check (GNSS or OPERA). That is a stronger safeguard in some respects, because it checks the result against independent measurements.

### 6.5 Validation tests (choose by data availability, then run all that are available)

**Test V1: time-matched GNSS (preferred).**
- Requires HoustonNet daily ENU from the most recent release covering 2025-11-02 to 2026-01-01 (and later if NISAR continues).
- Project the station's ENU displacement over each NISAR pair interval onto the NISAR line of sight using the product's look vector (incidence and azimuth from the geometry layers). Verify the sign convention against a synthetic ramp.
- Compare with the NISAR cell displacement over the same interval. Use only stations with continuous daily data. Exclude campaign-style stations.
- Use the pre-registered 19 reference and 18 held-out stations (from `houstonnet_2024_summary.json` and the reference candidates file). If the newer release changes the station list, re-register the split before computing.
- Report: station count, median absolute residual, correlation (only if n is large enough), excluded cells and reasons, and the baseline (rank by radar magnitude alone).

**Test V2: cross-sensor check with OPERA DISP-S1 over the overlap.**
- Requires OPERA granules covering 2025-11 to 2026-03 for frame F38238 (manifest says available).
- Re-reference the OPERA series to the same reference region used for NISAR (or a documented equivalent).
- Compare LOS-projected trends of NISAR and OPERA over the overlapping window at co-located cells. Use each product's own look vector. Report the agreement and the residual scatter.
- Limitation: different wavelengths, different acquisition geometry, different processing chains. Agreement is a consistency check, not proof of ground truth. Disagreement is a finding and must be reported.

**Test V3: historical method check (fallback only).**
- OPERA against HoustonNet over the historic overlap (for example 2016 to 2021), using the same projection and reference-tie method. This validates the method on OPERA, not on NISAR. Use it only if V1 and V2 cannot be run in time, and label it that way.

### 6.6 HoustonNet data request (start immediately)

Owner: validation lead. Output: `docs/stakeholders/hgsd-data-request.md` and the received data with its release identifier.

1. Contact HGSD (subsidence.org). Ask for:
   - the most recent HoustonNet release identifier and processing date;
   - daily ENU time series in Houston20 (or GOM20 with the transformation documented) for stations within the NISAR Houston footprint, covering at least 2025-11-01 to 2026-01-15, and ideally through today;
   - station metadata with the continuity flag (continuous versus campaign);
   - the reference-frame description and any outlier-removal policy.
2. Ask the same people for 15 minutes of feedback on the project's question (as in Section 13). Record the answer and whether they consent to quotation.
3. If HGSD is unreachable by Nov 13, use the 2024 release only for the historic V3 check and state that the NISAR window cannot be validated with GNSS.
4. Do not mix the 2024 and newer releases in any comparison. Record the release used for each artifact.

### 6.7 Acceptance criteria for Section 6

- The inventory artifact exists, with every granule and a written answer to the two questions in 6.2.
- The correction flags are written in every NISAR artifact, and a test rejects double application.
- The reference region is pre-registered, with a commit hash, and at least 50 cells.
- Results are reported under both the strict and validated rules, with the rule named on each label.
- At least one of V1 or V2 has been run, or the page states exactly which validation could not be performed and why.
- The detectability number is computed from measured residuals for the epochs that exist, and the planning estimate is labeled as a planning estimate.

---

## 7. Workstream A: Governance (Nov 10 to 13)

Deliverables:
- `docs/rules/` with written answers to G1, G2, G3, and G6, dated and sourced.
- `docs/decisions.md` with every decision in Sections 5 and 6, dated.
- `docs/team.md` with roles, registrations, and one accountable owner per output.
- `docs/ai-use.md`.
- `docs/kickoff-plan.md` with the clean-repository fallback steps.
- The NISAR inventory artifact (6.2) and the HoustonNet request (6.6).

Acceptance: no open gate older than the Nov 12 decision deadline.

---

## 8. Workstream B: NISAR time series (core science)

Covers Sections 6.3 and 6.4 in implementation form.

B1. Build the chain from all granules in the inventory. Verify every granule's HDF5 paths with `inspect-h5`; do not assume paths, CRS, or wavelength. [v3.1] Product metadata gives 0.241962 m; the README's former 0.238 m was wrong.

B2. Implement correction flags (6.3 item 1) and the double-application test.

B3. Commit the reference-region rule and cell list (6.3 item 2) before per-cell results.

B4. Re-reference each pair. Keep raw values in `pair_los_displacement_raw_mm`. Convert phase to displacement with dLOS = phase × λ/(4π). [v3.1] Test λ/(4π) ≈ 19.255 mm per radian at λ = 0.241962 m (center frequency 1.239 GHz, from product metadata). Document and test the sign convention against a synthetic ramp.

B5. Build cumulative time series and check unwrapping continuity (6.3 item 3). Output per cell: epochs, cumulative displacement, continuity flags.

B6. Fit rate, σ from residuals, σ_v, N, Δt, detectability (6.3 item 4). Withhold where the release rule (6.4) fails and state which part failed.

B7. Sensitivity: coherence 0.3, 0.4, 0.5; two reference regions; with and without each correction. Report label-change percentages.

B8. Tests to add:
- rate withheld when the release rule (6.4) fails;
- cells below 50% valid pixels never receive a positive label;
- a flood null is never coerced to exposed or not exposed;
- double application of a correction is rejected;
- the planning equation reproduces σ_v ≈ 130 mm/yr for N = 6, σ = 18 mm, Δt = 12 days;
- the detectability function fails loudly on invalid input.

Acceptance: per-cell output with rate (or withheld reason), σ_v, residual scatter, N, Δt, correction flags, release-rule status, and limitation text.

---

## 9. Workstream C: Validation

Implements 6.5.

C1. Run V1 if HoustonNet newer release is received. Pre-register metrics before computing.
C2. Run V2 with OPERA over the overlap.
C3. Run V3 only as a labeled fallback.
C4. Baseline: rank by radar magnitude alone and compare agreement with GNSS. Report whether the designed rule beats the baseline. If it does not, say so.

Acceptance: a validation report that states what was tested, what passed, what failed, and what could not be tested, with the release identifiers.

---

## 10. Workstream D: Decision logic (backend)

- Implement 5.2 and the release rule (6.4) in `backend/decision.py`.
- Keep the single-pair rule only as a labeled sensitivity comparison, never as a public label.
- Every label carries rule ID, thresholds, source values with units and dates, the applied-correction flags, the validation status, and the limitation string.
- Tests for each label, including: quality-OK but unreleased; flood overlap with no GNSS; released rate with nearby GNSS.
- No machine-learned component.

Acceptance: all tests pass; a generated decision file lists every cell with a rule trace.

---

## 11. Workstream E: GroundTruth Node

Hardware has arrived and raw logs exist.

E1. Confirm raw logs under `data/raw/groundtruth/` (gitignored) and produce RINEX under `data/derived/groundtruth/`.
E2. Process each two-hour session in static mode against the nearest NGS CORS station (NETP is the planned reference). Record processing settings.
E3. Fill `data/groundtruth_session_manifest.template.json` with real sessions, durations, and checksums. Do not fill it with placeholder values.
E4. Pass conditions (README): non-empty raw log, non-empty RINEX, overlapping reference data, at least three valid static solutions, antenna fixed throughout, settings published, reproducible scatter calculation.
E5. If it passes: publish the vertical repeatability as "fixed-antenna repeatability under these conditions." Use the lower-bound wording from the README. Do not describe it as land motion.
E6. If it fails: publish the prototype limitation, the setup photo (no identifiable people under 18), and no detectability number.

Acceptance: either a passing repeatability result with full provenance or a limitation statement with photo. Nothing in between.

---

## 12. Workstream F: Outsider understanding (demo-critical)

Requirement: a judge with no radar, geodesy, or subsidence background must be able to state, after the 30-second story or the first screen of the page, (a) what the project measures, (b) what the headline number means, and (c) what it does not claim.

F1. Glossary (at most 12 terms, one sentence each): NISAR, InSAR, line-of-sight, GNSS/GPS, coherence, reference region, rate, uncertainty, detectability (time-to-detection), noise floor, lower bound, label.

F2. Analogies (check each for accuracy before use):
- Line-of-sight: a radar gun aimed straight ahead can tell you whether a car is coming closer, but not whether it is drifting sideways.
- Coherence: matching two beach photos taken a week apart. Sand shifts, rocks stay recognizable. Where nothing matches, the answer is unreliable.
- Reference region: zeroing a bathroom scale on an empty floor. The zero is arbitrary; readings are meaningful only relative to it.
- Detectability: watching a jittery clock hand to see whether it is drifting. You must watch long enough for the drift to rise above the jitter.
- Lower bound: "this trip takes at least two hours." Traffic can make it longer, never shorter.

F3. Label decoder (text, for slides and page): each label gets one sentence on what it means and one on what it does not mean. Example: Investigate Satellite Signal means the radar shows a resolved, validated rate in a flood-zone overlap; it does not mean the ground is sinking or that flooding will occur.

F4. The 30-second story (three beats):
1. Problem (5 s): Houston's ground has moved for decades. NASA's radar now watches it from space. How do we know when a new reading is real?
2. New thing (12 s): we measured how long NASA's radar needs to confirm a slow 5 mm/yr rate, checked it against GPS (or the cross-sensor test), and show the headline number and map.
3. Answer and limit (13 s): the map shows where to look first and why. It does not predict floods and does not say what caused the motion.

Any historic subsidence figure used must be verified against a USGS or district source and dated before use. Unverifiable figures are cut.

F5. Jargon budget: at most three technical terms per slide, each defined on first use. Numbers always carry units and a time window.

F6. The "one question" test: every slide and page section answers one question a Houston official could act on. Otherwise it is cut.

F7. Outsider test: three testers outside computer science, geology, and math (family, teachers from other subjects, classmates who don't take STEM electives). Show the 30-second story and the first screen of the page. Ask them, without help: what the map shows, what the headline number means, what the project does not claim. Record verbatim in `docs/outsider-test/`. Acceptance: at least two of three answer the first two correctly, and at least two state a limitation. If not, rewrite and retest.

F8. Visual rules: one idea per slide; chart titles state the finding; the headline number is large with units and window beneath it; no code or JSON screenshots in the deck; red and orange are used for "bad" only when the legend says so in words on the same slide.

---

## 13. Workstream H: Local Impact and stakeholders

- Email HGSD and the Fort Bend Subsidence District (requesting 15 minutes and the HoustonNet data, Section 6.6). Ask two questions: what would make a NISAR signal useful to a district, and what would make them distrust it.
- Log every response in `docs/stakeholders/` with date and quotation permission.
- If a quote is permitted, put it on the page with the speaker's role.
- If no response by the hour-24 checkpoint, say so on the page. Do not imply a conversation that did not happen.

---

## 14. Workstream G: Submission package (Nov 14 to 15)

### G1. Project page (most of the judging weight)

In order:
1. Summary in plain language (mission sentence, then the headline number).
2. Demo: deck link (video only if G3 permits).
3. Live app link (static).
4. The question and why it matters for Houston.
5. Method with numbers, units, pre-registration commit hashes, corrections applied, and the reference region.
6. Results: the detectability result, validation results (V1, V2, or the statement that they could not be run), label counts, stability table, and the release rule.
7. NASA data: each NISAR granule (or the statement of what exists), with dates, product version, and checksums; OPERA frame F38238 with dates.
8. Partner data: HoustonNet (release identifier), USGS, FEMA, NOAA NGS, each with access date.
9. Local impact: quoted stakeholder feedback, with permission.
10. Use of AI (`docs/ai-use.md`).
11. Limitations, in a visible section.
12. Development history (G1 in Section 3).

### G2. Claims audit

Search repository docs, web copy, deck, and page for these terms (case-insensitive) and rewrite or remove every hit: "sinking," "will flood," "caused by," "caused the," "measured subsidence," "our node measured," "predicts," "prediction," "definitely," "proves," "NISAR cannot," "annual subsidence rate" (when describing one pair), "works everywhere," "first ever," "AI predicted."

Allowed substitutes: "NISAR observed relative line-of-sight displacement over this interval"; "this cell is prioritized for investigation under our stated rules"; "HoustonNet provides historic motion context"; "the fixed GNSS prototype showed X repeatability under these conditions"; "at today's measured noise, resolving this rate would take about N months."

### G3. Deck

At most seven slides including the title. Exceeding this removes the project from global judging.
Suggested sequence: 1 title and team (no faces; names only per G3 of Section 3); 2 the question in plain language; 3 data and method, one diagram; 4 the detectability result (headline number); 5 the validation result with baseline and limitation; 6 the map and one evidence card in plain language; 7 what the project does not claim, and the next step (for example, NISAR's next 12-day acquisitions and station placement).

### G4. Reproducibility

`docs/reproduce.md` lists every command from raw data to every artifact in the page. Confirm that a fresh clone reproduces the headline number from committed inputs within stated tolerance.

### G5. Submission checks

Repository public; README current; ledger matches manifests; every link tested in a private window; demo link public without login; all datasets and tools credited with access dates; no prohibited content.

---

## 15. Engineering hygiene

- Clean virtual environment with `pip install -r requirements.txt`. All 48 tests pass. Do not silence the `pyproj`-dependent errors.
- Confirm `data/sample_cells.json` cannot reach a published output. Check `scripts/export_web.py` for the guard and add a test if none exists.
- Confirm `data/raw/` is gitignored and no raw granule is committed.
- Derived JSON artifacts total about 119 MB. Do not delete committed derived artifacts without agreement. Document regenerable ones.
- Fix the CLAUDE.md correction (4.4) and the README "Next backend work" section.
- Small descriptive commits. Tag the submission commit.

---

## 16. Timeline

### Pre-kickoff (Nov 10 to 13)

- **Nov 10 to 11:** G1 written question to organizers; NISAR inventory (6.2) by the science lead; HoustonNet request (6.6); start the correction fixes (4.4) and the correction-flag tests (6.3 item 1); draft `docs/decisions.md`; email stakeholders.
- **Nov 11 to 12:** inventory decision tree (6.2) decided; release rule (6.4) drafted and committed; reference region rule (6.3 item 2) drafted; environment setup; E1 and E2 raw-to-RINEX check on the node.
- **Nov 12:** all gate decisions (Section 3) recorded; kickoff plan finalized.
- **Nov 13:** official resources reviewed; reference-region rule and validation metrics committed; decision on which validation tests can run.

### Event (Nov 14 to 15), hours from kickoff

- **Hours 0 to 2:** if the node is logging, keep it running (or confirm the processed sessions). Create the clean repository if the fallback applies. Run tests.
- **Hours 2 to 8:** B1 to B4 (chain build, corrections, re-referencing); commit reference-region cell list before per-cell results.
- **Hours 8 to 16:** B5 to B6 (time series, rate fit, detectability); V2 (OPERA cross-sensor); B7 sensitivity; draft the outsider script and glossary.
- **Hour 16 checkpoint:** a NISAR time series exists for the cells, with a detectability number under both rules, and at least one validation test has run or has an explicit reason it cannot. If not, the scope-cut order (Section 18) begins.
- **Hours 16 to 24:** D (decision logic and tests); V1 if the HoustonNet release arrived; E3 to E6 node result; H stakeholder log.
- **Hours 24 to 32:** C4 baseline; B8 tests complete; stability table; methods page.
- **Hours 32 to 40:** F7 outsider test (start with the draft); G1 project page; G2 claims audit; G3 deck.
- **Hours 40 to 46:** revise the deck from outsider feedback; G4 reproducibility check.
- **Hours 46 to 48:** G5 checks; submit; test all links from a private window; final claims audit.

If the local event is shorter than 48 hours, compress each block proportionally and keep the checkpoint at the same fraction.

---

## 17. Work-session report (required each session)

Write to `docs/worklog/YYYY-MM-DD-session-N.md`:
1. Goal, in one sentence.
2. Files changed, with a one-line reason each.
3. Tests run and results with counts.
4. Numbers produced, each with artifact path and units.
5. Claims check: new phrasing that touches the claims policy, and its resolution.
6. Pre-registrations set in the session, with commit hashes.
7. What is withheld and why.
8. Open questions and blockers.
9. Next three actions, in order.

---

## 18. Scope-cut order

If the hour-16 checkpoint fails, cut in this order:
1. Sensitivity runs beyond 0.3, 0.4, 0.5.
2. Second reference-region alternative (keep one defensible region).
3. OPERA context beyond the overlap window.
4. Visual polish of anything.
5. Node status beyond the final result (keep the limitation statement).
6. Extra NASA context layers.
7. Demo video (the deck is the default).

Never cut:
- The NISAR time series and the release rule with its deviation disclosure.
- The detectability number with units and lower-bound wording.
- At least one validation result, or the explicit statement of why none was possible.
- The reference-region pre-registration and its commit.
- The correction flags and their tests.
- Label rules with tests, and a rule trace on every label.
- The limitations section.
- The data ledger and reproducibility path.
- The outsider script and at least two outsider tests.
- The AI-use disclosure.
- Written eligibility decisions.

---

## 19. Risk register

| Risk | Effect | Mitigation | Owner |
|---|---|---|---|
| Pre-event work disqualifies | Global judging lost | G1 written answer; clean-repository fallback prepared | Science lead + Product lead |
| [v3.1] 22 newer granules (about 51 GB) not downloaded and ingested by hour 0 | Shorter chain than the archive allows | Download from Nov 11; pre-registered partial-processing rule (longest contiguous chain from 2025-11-02); never invent epochs | Science lead |
| Gate change perceived as moving goalposts | Credibility loss with experts | Logged deviation; results shown under both rules; rationale in 6.4 | Science lead |
| Newer HoustonNet release not obtained | No time-matched GNSS validation | V2 cross-sensor; V3 labeled fallback; stated limitation | Validation lead |
| Double-applied corrections | Biased displacement | Applied-correction flags and a rejecting test | Science lead |
| Reference region too noisy | Thresholds unstable | Expanded pre-registered region; sensitivity and label-change reporting | Science lead |
| Single-pair labels leak into output | Overclaiming | Removed from public output; claims audit | Product lead |
| Node produces no valid result | Hardware section weak | Honest prototype limitation with photo | Validation lead |
| No stakeholder feedback | Local Impact weaker | Honest outreach log; no implied conversations | Product lead |
| Outsiders cannot explain the result | Presentation score low | F7 tests; rewrite until two of three pass | Product lead |
| Under-18 likeness rule violated | Ineligible for global judging | G3 default deck; no faces or voices | Team |
| District already publishes similar Sentinel-1 maps | Originality questioned | Position as NISAR-based, detectability-first, validation-explicit; not a replacement | Product lead |
| Data changes after snapshot | Irreproducible numbers | Checksums; freeze inputs at hour 0 | Science lead |

---

## 20. Claims policy (binding)

Allowed:
- "NISAR observed relative line-of-sight displacement over this interval."
- "This cell passed our published radar-quality gate."
- "This cell is prioritized for investigation under our stated rules."
- "At today's measured noise, resolving a 5 mm per year rate here would take about N months (lower-bound planning estimate)."
- "HoustonNet provides historic motion context."
- "USGS records show groundwater and compaction context at the nearest monitoring site."
- "Our fixed GNSS prototype showed X mm session-to-session vertical scatter under these conditions."

Never:
- "This property is sinking" or "this location is sinking vertically."
- "This location will flood."
- "Groundwater pumping caused this signal."
- "Our node measured subsidence."
- "This NISAR pair is an annual subsidence rate."
- "NISAR cannot see Houston subsidence." (It is a time question.)
- "TerraGauge predicts future subsidence."
- "AI predicted..." anything.
- "First ever" or any uncited novelty claim.

Every number carries units, a date range, a source, and where needed a limitation.

---

## 21. Open questions (answer in `docs/decisions.md`)

1. Written answer from the organizers on pre-event work (G1).
2. Does the Local Lead accept the deck format and the team-name approach (G3)?
3. Result of the NISAR inventory (6.2): any Houston granules after Jan 1, 2026? Any non-consecutive pairs?
4. Does the Earthdata or ASF alert list a data gap or pause for Houston dates?
5. Which HoustonNet release is current, and can HGSD provide daily ENU for the NISAR window (6.6)?
6. Have the production granules fixed the January 2026 sample-data limitations? What is the product version?
7. Who contacts HGSD and Fort Bend, and by when?
8. Accountable owner for each deliverable in Section 2.

---

## 22. Final check before submission

- Every label has a rule trace, correction flags, validation status, and limitation.
- Every number has units, a window, a source, and a limitation where needed.
- The headline number is computed from measured residuals for the epochs that exist; the planning estimate is labeled as such.
- Results appear under both the strict and validated rules, with the rule named.
- At least one validation test has been run, or the page states exactly what could not be tested and why.
- The outsider test has been run and passed.
- The deck has at most seven slides and no identifiable minors.
- The AI-use disclosure is complete.
- The claims audit has no forbidden phrases.
- CLAUDE.md and the README reflect the atmospheric-correction correction (4.4).
- The project page stands alone for a reader who has not seen the demo.
- A fresh clone reproduces the headline number.
- Every gate in Section 3 has a dated written decision.

---

## Changelog

- **v3.1 (2026-11-10).** Corrected three facts that would otherwise steer the work: the NISAR archive extent (G7, §4.2, §4.3 item 8, §5.3, §19), the radar wavelength (B1, B4), and the provisional label count (§4.2). Edits are marked [v3.1]. Further errata, the decisions taken, and the pre-registration are in `docs/decisions.md`, `docs/audit/2026-11-10-codebase-audit.md`, and `docs/preregistration/2026-11-10-preregistration.md`.
