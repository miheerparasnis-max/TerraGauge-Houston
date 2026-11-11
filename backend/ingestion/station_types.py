"""HoustonNet station types that change what a GPS rate means.

Deep-seated GNSS stations
-------------------------
"The GNSS antennas at five sites (Addicks (ADKS), -549 m below land surface;
Lake Houston (LKHU), -591 m; Northeast (NETP), -661 m; Clear Lake (TXEX),
-936 m; and Katy (UHKD), -904 m) are mounted on the top of the inner poles of
deep extensometer boreholes." They "were installed to provide stable references
for calculating site deformation at other GNSS sites."
Source: Wang, G., Greuter, A., Petersen, C. M., and Turco, M. J. (2022),
"Houston GNSS Network for Subsidence and Faulting Monitoring: Data Analysis
Methods and Products", J. Surv. Eng. 148(4): 04022008,
doi:10.1061/(ASCE)SU.1943-5428.0000399 (CC BY 4.0); see also Yu et al. (2014).

Such an antenna moves with the borehole anchor, hundreds of metres down. It does
not measure the land surface that a radar sees. A deep-seated station is therefore
never used as evidence that nearby ground is stable (radar reference selection)
and never compared with a radar rate.

Campaign-style (PAM) stations
-----------------------------
PAM stations were "designed as a campaign-style long-term GPS monitoring
solution" (Agudelo et al. 2020, Proc. IAHS 382: 11-18,
doi:10.5194/piahs-382-11-2020); HGSD's 2019 report describes data "for
approximately seven days every two months". Several were later switched to
continuous operation, so they are identified by sampling density
(pre-registration PR-5), not by name.
"""

from __future__ import annotations

from backend.insights import IMPLAUSIBLE_MM_YEAR

DEEP_SEATED_GNSS: dict[str, dict[str, object]] = {
    "ADKS": {"site": "Addicks", "anchor_depth_m": 549},
    "LKHU": {"site": "Lake Houston", "anchor_depth_m": 591},
    "NETP": {"site": "Northeast", "anchor_depth_m": 661},
    "TXEX": {"site": "Clear Lake", "anchor_depth_m": 936},
    "UHKD": {"site": "Katy", "anchor_depth_m": 904},
}
DEEP_SEATED_SOURCE = "Wang et al. (2022), J. Surv. Eng. 148(4): 04022008, doi:10.1061/(ASCE)SU.1943-5428.0000399"


def is_deep_seated(station_id: str) -> bool:
    return station_id in DEEP_SEATED_GNSS


def display_gps_rate(up_mm_year: float | None) -> tuple[float | None, str | None]:
    """Return (rate to show, flag). A rate faster than any plausible Houston GPS
    rate is a data problem in the source release and is never shown as motion."""
    if up_mm_year is None:
        return None, None
    if abs(float(up_mm_year)) > IMPLAUSIBLE_MM_YEAR:
        return None, "implausible_in_source"
    return float(up_mm_year), None
