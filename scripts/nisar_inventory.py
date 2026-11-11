"""Inventory NISAR L2 GUNW granules over the Houston study area (MASTER 6.2, Path A).

Queries NASA CMR (public, read-only metadata; no Earthdata login) and writes a
manifest listing every granule for the target track/frame, plus a coverage
summary for every other track/frame that intersects the study box.

    python3 scripts/nisar_inventory.py \
        --out data/manifests/nisar_track062_inventory_YYYYMMDD.json

Re-run it at the hour-0 input freeze: production resumes after pauses and
backfills, so the archive can grow between runs.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CMR = "https://cmr.earthdata.nasa.gov/search"
USER_AGENT = "terragauge-houston-inventory"
BBOX = (-95.95, 29.4, -94.8, 30.2)
NEAREST_NEIGHBOR_DAYS = 12


def _get_json(url: str) -> tuple[dict[str, Any], dict[str, str]]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8")), dict(response.headers)


def gunw_collections() -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"short_name": "NISAR_L2*GUNW*", "options[short_name][pattern]": "true", "page_size": 50})
    payload, _ = _get_json(f"{CMR}/collections.json?{query}")
    return [{"concept_id": e["id"], "short_name": e.get("short_name"), "version_id": e.get("version_id"), "time_start": e.get("time_start")} for e in payload["feed"]["entry"]]


def granules(concept_id: str, bbox: tuple[float, float, float, float], start: str, end: str) -> tuple[list[dict[str, Any]], int]:
    query = urllib.parse.urlencode({
        "collection_concept_id": concept_id,
        "bounding_box": ",".join(str(v) for v in bbox),
        "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z",
        "page_size": 2000,
        "sort_key": "start_date",
    })
    payload, headers = _get_json(f"{CMR}/granules.umm_json?{query}")
    hits = int({k.lower(): v for k, v in headers.items()}.get("cmr-hits", len(payload["items"])))
    if hits > len(payload["items"]):
        raise RuntimeError(f"{concept_id}: {hits} hits exceed one page; add paging before trusting this inventory")
    return [item["umm"] for item in payload["items"]], hits


def granule_record(umm: dict[str, Any]) -> dict[str, Any]:
    attrs = {a["Name"]: a["Values"][0] if len(a["Values"]) == 1 else a["Values"] for a in umm.get("AdditionalAttributes", [])}
    h5 = [f for f in umm["DataGranule"]["ArchiveAndDistributionInformation"] if f["Name"].endswith(".h5")]
    checksum = (h5[0].get("Checksum") or {}) if h5 else {}
    reference, secondary = attrs["REFERENCE_ZERO_DOPPLER_START_TIME"][:10], attrs["SECONDARY_ZERO_DOPPLER_START_TIME"][:10]
    return {
        "granule_id": umm["GranuleUR"],
        "track": int(attrs["TRACK_NUMBER"]),
        "frame": int(attrs["FRAME_NUMBER"]),
        "direction": attrs["ASCENDING_DESCENDING"],
        "reference_date": reference,
        "secondary_date": secondary,
        "span_days": (date.fromisoformat(secondary) - date.fromisoformat(reference)).days,
        "product_version": attrs.get("PRODUCT_VERSION"),
        "full_frame": attrs.get("FULL_FRAME"),
        "polarization": attrs.get("FREQUENCY_A_POLARIZATION"),
        "range_bandwidth_mhz": attrs.get("FREQUENCY_A_RANGE_BANDWIDTH"),
        "production_datetime": umm["DataGranule"].get("ProductionDateTime"),
        "size_bytes": h5[0]["SizeInBytes"] if h5 else None,
        "checksum": {"algorithm": checksum.get("Algorithm"), "value": checksum.get("Value")} if checksum else None,
        "download_url": next((u["URL"] for u in umm.get("RelatedUrls", []) if u.get("Type") == "GET DATA" and u["URL"].endswith(".h5")), None),
        "footprint": [(p["Longitude"], p["Latitude"]) for p in umm["SpatialExtent"]["HorizontalSpatialDomain"]["Geometry"]["GPolygons"][0]["Boundary"]["Points"]],
    }


def chain_report(pairs: list[tuple[str, str]], nominal_days: int = NEAREST_NEIGHBOR_DAYS) -> dict[str, Any]:
    """Describe the pair graph: dates, gaps, non-nominal spans, redundancy.

    A pair spanning more than `nominal_days` is only a redundant edge if it
    skips a date that is itself in the graph; otherwise it bridges a missed
    acquisition and the graph is still a chain.
    """
    if not pairs:
        raise ValueError("no pairs to analyse")
    dates = sorted({d for pair in pairs for d in pair})
    day = date.fromisoformat
    unique_pairs = sorted(set(pairs))
    long_pairs = [p for p in unique_pairs if (day(p[1]) - day(p[0])).days != nominal_days]
    skipping = [p for p in unique_pairs if any(p[0] < d < p[1] for d in dates)]
    gaps = [{"from": a, "to": b, "days": (day(b) - day(a)).days} for a, b in zip(dates, dates[1:]) if (day(b) - day(a)).days > nominal_days]
    redundant = len(unique_pairs) - (len(dates) - 1)
    return {
        "pair_count": len(pairs),
        "duplicate_pairs": len(pairs) - len(unique_pairs),
        "date_count": len(dates),
        "first_date": dates[0],
        "last_date": dates[-1],
        "acquisition_dates": dates,
        "non_nominal_span_pairs": [list(p) for p in long_pairs],
        "pairs_skipping_an_available_date": [list(p) for p in skipping],
        "gaps_longer_than_nominal": gaps,
        "redundant_edges": max(0, redundant),
        "is_simple_chain": redundant == 0 and not skipping,
    }


def bbox_coverage(footprint: list[tuple[float, float]], bbox: tuple[float, float, float, float], steps: int = 40) -> float:
    """Fraction of a lon/lat box inside a footprint polygon (grid sampling)."""
    west, south, east, north = bbox

    def inside(x: float, y: float) -> bool:
        result = False
        for (x1, y1), (x2, y2) in zip(footprint, footprint[1:] + footprint[:1]):
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                result = not result
        return result

    grid = [(west + (east - west) * i / steps, south + (north - south) * j / steps) for i in range(steps + 1) for j in range(steps + 1)]
    return sum(inside(x, y) for x, y in grid) / len(grid)


def build_inventory(track: int, frame: int, direction: str, start: str, end: str, collection_short_name: str) -> dict[str, Any]:
    collections = gunw_collections()
    hits_by_collection: dict[str, int] = {}
    records_by_collection: dict[str, list[dict[str, Any]]] = {}
    for collection in collections:
        umms, hits = granules(collection["concept_id"], BBOX, start, end)
        hits_by_collection[collection["short_name"]] = hits
        records_by_collection[collection["short_name"]] = [granule_record(u) for u in umms]
    if collection_short_name not in records_by_collection:
        raise RuntimeError(f"collection {collection_short_name} not found in CMR")
    records = records_by_collection[collection_short_name]
    target = sorted((dict(r) for r in records if r["track"] == track and r["frame"] == frame and r["direction"].upper().startswith(direction.upper())), key=lambda r: (r["reference_date"], r["secondary_date"]))
    if not target:
        raise RuntimeError("no granules for the target track/frame; check the parameters")

    in_repo = set(json.loads((ROOT / "data/manifests/nisar_houston_track062_temporal_download_plan.json").read_text(encoding="utf-8"))["granules"])
    first = json.loads((ROOT / "data/manifests/nisar_gunw_20251102_20251114.json").read_text(encoding="utf-8"))
    for row in target:
        row["in_repo"] = f"{row['granule_id']}.h5" in in_repo
        if f"{row['granule_id']}.h5" == first["artifact"]:
            row["repo_sha256"] = first["sha256"]
        row.pop("footprint")

    coverage = []
    for short_name, rows in records_by_collection.items():
        groups: dict[tuple[int, int, str], list[dict[str, Any]]] = {}
        for row in rows:
            groups.setdefault((row["track"], row["frame"], row["direction"]), []).append(row)
        for (trk, frm, drn), group in sorted(groups.items()):
            report = chain_report([(r["reference_date"], r["secondary_date"]) for r in group])
            coverage.append({
                "collection": short_name, "track": trk, "frame": frm, "direction": drn,
                "granule_count": len(group), "first_date": report["first_date"], "last_date": report["last_date"],
                "date_count": report["date_count"], "redundant_edges": report["redundant_edges"],
                "study_box_fraction_covered": round(bbox_coverage(group[0]["footprint"], BBOX), 2),
                "product_versions": sorted({str(r["product_version"]) for r in group}),
            })

    report = chain_report([(r["reference_date"], r["secondary_date"]) for r in target])
    later = [r["granule_id"] for r in target if r["secondary_date"] > "2026-01-01"]
    return {
        "artifact_type": "nisar_gunw_archive_inventory",
        "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "query": {"endpoint": f"{CMR}/granules.umm_json", "bounding_box_wgs84": list(BBOX), "temporal": [start, end], "collections": collections, "hits_by_collection": hits_by_collection},
        "target": {"collection": collection_short_name, "track": track, "frame": frame, "direction": direction},
        "answers": {
            "granules_after_2026_01_01": {"exist": bool(later), "count": len(later)},
            "non_consecutive_pairs": {
                "pairs_skipping_an_available_date": report["pairs_skipping_an_available_date"],
                "non_nominal_span_pairs_bridging_missed_acquisitions": report["non_nominal_span_pairs"],
                "is_simple_chain": report["is_simple_chain"],
            },
        },
        "chain": report,
        "granules": target,
        "coverage_all_tracks": coverage,
        "limitations": [
            "CMR metadata only; granule contents were not opened by this script.",
            "Checksums are the archive's own (MD5); repo_sha256 is the team's local hash where one exists.",
            "study_box_fraction_covered samples the declared footprint polygon on a 41 x 41 grid; it ignores no-data areas inside the footprint.",
            "Production can pause and backfill; re-run before freezing inputs.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    parser.add_argument("--track", type=int, default=62)
    parser.add_argument("--frame", type=int, default=16)
    parser.add_argument("--direction", default="A")
    parser.add_argument("--start", default="2025-10-01")
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--collection", default="NISAR_L2_GUNW_PROVISIONAL_V1")
    args = parser.parse_args()
    inventory = build_inventory(args.track, args.frame, args.direction, args.start, args.end, args.collection)
    Path(args.out).write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    json.dump({"answers": inventory["answers"], "dates": inventory["chain"]["date_count"], "redundant_edges": inventory["chain"]["redundant_edges"]}, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
