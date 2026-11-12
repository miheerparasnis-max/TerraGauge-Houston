# Source verification ledger (2026-11-11)

Audience: the team, the executing agent, and judges checking the science.

This ledger lists every claim the project relies on that was checked against a primary source or our own datasets on this date: the verdict, the evidence, and the action taken. Access date for every web source: 2026-11-11.

> Some rows quote phrases removed from published copy, as evidence. A manual G2 claims sweep should treat those quotes like the ones in `docs/audit/`.

## Verdicts

| # | Claim (where it appears) | Verdict | Evidence | Action |
|---|---|---|---|---|
| 1 | GUNW includes an ionospheric phase screen that is **not applied** by default; troposphere and tide come as lookup tables, also **not removed** (MASTER 4.4, README, CLAUDE.md) | **Confirmed** | ASF NISAR docs, GUNW page: "The estimated ionospheric phase screen is included in the product but not applied to the data layers"; correction lookup tables "are not removed from the interferometric data". | None. Already corrected in `da98c41`. |
| 2 | Wavelength 0.241962 m (center frequency 1.239 GHz) for our granules | **Confirmed** | ASF NISAR docs, frequencies table: the 40+5 MHz mode's frequency A is centered at 1239 MHz. CMR lists all 27 granules at a 40 MHz range bandwidth. c / 1.239 GHz = 0.2419632 m. | None |
| 3 | NISAR GUNW line-of-sight sign convention | **Not found** in public docs | The ASF GUNW page states no sign convention. The only stated convention found is ARIA's Sentinel-1 product, which is not NISAR. | Stays open (plan F-4). Must be read from the GUNW specification or the HDF5 attributes at plan step B1. |
| 4 | OPERA DISP-S1 sign: positive = toward the satellite (`opera_houston_los_velocity_*.json`) | **Supported by data**, document not found | No public page found stating it. Empirically, OPERA LOS rates correlate **positively** with GPS vertical rates (r = +0.660, 106 independent stations; e.g. MRHK GPS −16.5, OPERA −18.8 mm/yr), which is only possible if positive means toward the satellite (uplift). | Recorded here. Confirm in the DISP-S1 Product Specification (JPL D-108772) when it is available. |
| 5 | `PA##` / PAM stations are campaign-style, not continuous (audit A7, PR-5) | **Confirmed** | Agudelo et al. (2020), *Proc. IAHS* 382: 11–18: PAM stations were "designed as a campaign-style long-term GPS monitoring solution". HGSD 2019 report: data "for approximately seven days every two months". Wang et al. (2022): several PAMs were later switched to continuous operation. | None. PR-5 already uses sampling density, not the name. |
| 6 | Houston20 frame: 25 long-history continuous stations outside the subsiding area | **Confirmed** | Agudelo et al. (2020). | None |
| 7 | ADKS, LKHU, NETP are stable surface references (PR-4 v1; provisional website reference) | **False**: they are deep-seated | Wang, Greuter, Petersen & Turco (2022), *J. Surv. Eng.* 148(4): 04022008, doi:10.1061/(ASCE)SU.1943-5428.0000399: ADKS (549 m), LKHU (591 m), NETP (661 m), TXEX (936 m), and UHKD (904 m) are "mounted on the top of the inner poles of deep extensometer boreholes". In our data, the radar sees the ADKS and LKHU cells moving −6.2 and −4.0 mm/yr LOS, while those GPS antennas read −0.5 and −0.2 mm/yr. | Pre-registration amendment A1 (`051ca6c`). Excluded everywhere (`051ca6c`, `3abe067`). |
| 8 | "Faster than anything ever measured in Houston" for rates above 40 mm/yr (website "Check data") | **False** | USGS: the maximum average rate at Pasadena was about 0.12 m/yr over 1964–73 (Gabrysch & Bonnet 1974, USGS OFR 74-123; UNESCO casebook ch. 9.12). | Reworded to cite the fastest **reliable** rate in the 2024 GPS release (P111, −32.2 mm/yr) (`3abe067`). |
| 9 | HoustonNet station rates shown on the site are real motion | **One false case** | P102 is listed at −615.6 mm/yr (2019.6–2022.4) in the 2024 summary, physically implausible. | Withheld on the site, with the reason (`3abe067`). |
| 10 | NETP is "NOAA's NETP reference station" (sensor page) | **Confirmed**, with a caveat | NGS site log: NETP, "Northeast 2250 CORS ARP", Houston. It is also deep-seated (row 7). That is fine as a GNSS processing reference, but not as a surface reference. | None for the sensor page |
| 11 | "NASA OPERA satellite radar" (website data table) | **Misleading** | OPERA is a NASA JPL processing project. The radar data come from the Copernicus Sentinel-1 satellites. | Reworded, and Copernicus credit added (`3abe067`). |
| 12 | "The satellite matches N GPS stations to within about X mm a year" | **Overstated** | X is the **median** absolute difference, not a bound. | Reworded as "typical (median) difference" (`3abe067`). |
| 13 | NISAR archive after 2026-01-01 | **Confirmed** (2026-11-10 inventory) | CMR: 27 track-062 frame-016 pairs on 28 dates through 2026-10-16. | Done earlier (D-006) |
| 14 | The 2026-07-24 → 08-17 24-day NISAR pair | **Explained** | Earthdata alert "Permanent NISAR Instrument Data Gap" (issued 2026-08-28, updated 2026-09-01): a gap from 2026-07-27 22:03:25 UTC to 2026-08-10 00:55:27 UTC. The missing 2026-08-05 pass falls inside it. | Recorded |
| 15 | Provisional production pause | **Confirmed** | Earthdata alert: PR L0B+ production paused 2026-10-23 23:53 UTC; resolved 2026-11-06. | Re-run the inventory at hour 0 (PR-0) |
| 16 | "Our $74 sensor" price; "no recordings yet" | **Not verifiable** from sources | No receipt in the repo. MASTER §4.2 says raw logs exist, while the page says no recordings yet. | A teammate must confirm both (plan E tasks) |

## Robustness finding (not a source claim)

The provisional OPERA datum was the median of the cells nearest to 17–19 stable GPS stations, of which only 4–6 had complete velocities. Removing two deep-seated stations moved the bias against GPS from −0.21 to +2.21 mm/yr LOS, and Urgent squares from 358 to 202.

Re-referenced to the pre-registered region A (59 cells within 3 km of DEN2 or TMCC), the comparison against 106 independent GPS stations gives:

| Reference | r | Median difference | Bias |
|---|---|---|---|
| Region A, 3 km | 0.660 | 1.68 mm/yr | +0.34 mm/yr |
| Region A, 5 km | 0.660 | 1.68 mm/yr | +0.31 mm/yr |

That is the datum the site now uses (`3abe067`), and the one MASTER §6.5 prescribes for OPERA. The mount type of DEN2 and TMCC (building or free-field) is **not verified**. It is a stated limitation.

## Sources

- ASF NISAR documentation: [GUNW product](https://nisar-docs.asf.alaska.edu/gunw/), [frequencies and polarization](https://nisar-docs.asf.alaska.edu/frequencies-polarization), [product known issues](https://nisar-docs.asf.alaska.edu/product-known-issues)
- Earthdata alerts: [Permanent NISAR Instrument Data Gap](https://www.earthdata.nasa.gov/data/alerts-outages/permanent-nisar-instrument-data-gap), [NISAR provisional production paused](https://www.earthdata.nasa.gov/data/alerts-outages/nisar-provisional-data-product-production-paused)
- Wang, G., Greuter, A., Petersen, C. M., & Turco, M. J. (2022). Houston GNSS Network for Subsidence and Faulting Monitoring: Data Analysis Methods and Products. *J. Surv. Eng.* 148(4): 04022008. [doi:10.1061/(ASCE)SU.1943-5428.0000399](https://ascelibrary.com/doi/10.1061/(ASCE)SU.1943-5428.0000399), [HGSD copy](https://hgsubsidence.org/wp-content/uploads/2022/07/2022_HoustonNet_Data_Processing.pdf)
- Agudelo, G., Wang, G., Liu, Y., Bao, Y., & Turco, M. J. (2020). GPS geodetic infrastructure for subsidence and fault monitoring in Houston, Texas, USA. *Proc. IAHS* 382: 11–18. [doi:10.5194/piahs-382-11-2020](https://piahs.copernicus.org/articles/382/11/2020/)
- Yu, J., et al. (2014). Is There Deep-Seated Subsidence in the Houston-Galveston Area? *Int. J. Geophys.* [Wiley](https://onlinelibrary.wiley.com/doi/10.1155/2014/942834)
- HGSD 2019 Annual Groundwater Report, Appendix B: [PDF](https://hgsubsidence.org/wp-content/uploads/2020/06/2019-HGSD-2020-001-AGR-Appendix-B.pdf)
- USGS: [Gabrysch & Bonnet 1974, OFR 74-123](https://pubs.usgs.gov/publication/ofr74123); [Gabrysch 1982, OFR 82-571](https://pubs.usgs.gov/publication/ofr82571); [UNESCO casebook ch. 9.12](https://wwwrcamnl.wr.usgs.gov/rgws/Unesco/PDF-Chapters/Chapter9-12.pdf)
- NGS: [NETP site log](https://www.ngs.noaa.gov/corsdata/station_log/netp.log.txt)
