"""CLI entry points for auditable source-file conversion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .houstonnet import write_velocity_stations
from .fema import write_cell_center_flood_context, write_merged_nfhl_geojson_tiles, write_nfhl_point_join, write_nfhl_zone_overlay
from .gnss import write_groundtruth_report
from .houston import write_houston_evidence
from .reference import write_reference_review_candidates
from .nisar import GunwConfig, inspect_hdf5, write_pair_cells
from .opera import OperaConfig, write_disp_cells
from .usgs import write_groundwater_daily
from .temporal import write_network_diagnostic
from .quality import write_pair_integrity_report
from .compaction import write_extensometer_csv, write_usgs_2023_release
from .opera_temporal import invert_opera_files


def main() -> None:
    parser = argparse.ArgumentParser(description="TerraGauge source-data ingestion")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect-h5", help="list datasets before choosing paths")
    inspect.add_argument("input")
    nisar = commands.add_parser("nisar-gunw", help="extract quality-masked GUNW pair cells")
    nisar.add_argument("input")
    nisar.add_argument("output")
    nisar.add_argument("--wavelength-m", type=float, required=True)
    nisar.add_argument("--crs", required=True, help="e.g. EPSG:32615, verified from product metadata")
    nisar.add_argument("--x-path", required=True)
    nisar.add_argument("--y-path", required=True)
    nisar.add_argument("--phase-path", default=None)
    nisar.add_argument("--coherence-path", default=None)
    nisar.add_argument("--components-path", default=None)
    nisar.add_argument("--cell-pixels", type=int, default=13)
    nisar.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"), help="optional WGS84 bounds for a compact study-area artifact")
    nisar.add_argument("--reference-date", required=True)
    nisar.add_argument("--secondary-date", required=True)
    opera = commands.add_parser("opera-disp", help="extract quality-masked OPERA pair cells")
    opera.add_argument("input")
    opera.add_argument("output")
    opera.add_argument("--crs", required=True)
    opera.add_argument("--x-path", default="/x")
    opera.add_argument("--y-path", default="/y")
    opera.add_argument("--displacement-path", default="/displacement")
    opera.add_argument("--recommended-mask-path", default="/recommended_mask")
    opera.add_argument("--water-mask-path", default="/water_mask")
    opera.add_argument("--cell-pixels", type=int, default=33)
    opera.add_argument("--bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"), help="optional WGS84 bounds for a compact study-area artifact")
    opera.add_argument("--reference-date", required=True)
    opera.add_argument("--secondary-date", required=True)
    hn = commands.add_parser("houstonnet-velocities", help="normalize a checked HoustonNet velocity CSV")
    hn.add_argument("input")
    hn.add_argument("output")
    hn.add_argument("--column-map", required=True, help="JSON mapping of standard field name to CSV header")
    usgs = commands.add_parser("usgs-groundwater", help="normalize downloaded USGS NWIS daily groundwater JSON")
    usgs.add_argument("input")
    usgs.add_argument("output")
    fema = commands.add_parser("fema-nfhl-join", help="join saved FEMA NFHL point responses to USGS evidence locations")
    fema.add_argument("groundwater")
    fema.add_argument("responses")
    fema.add_argument("output")
    zones = commands.add_parser("fema-nfhl-overlay", help="download tiled FEMA NFHL flood-zone polygons for a study area")
    zones.add_argument("output")
    zones.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    zones.add_argument("--tile-degrees", type=float, default=0.10)
    merge_zones = commands.add_parser("fema-merge-tiles", help="merge saved FEMA GeoJSON tiles into one provenance-tracked overlay")
    merge_zones.add_argument("tile_directory")
    merge_zones.add_argument("output")
    merge_zones.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    merge_zones.add_argument("--tile-degrees", type=float, default=0.10)
    merge_zones.add_argument("--max-allowable-offset-degrees", type=float, default=0.001)
    flood_cells = commands.add_parser("fema-cell-context", help="classify NISAR cell centers against a saved FEMA polygon overlay")
    flood_cells.add_argument("nisar")
    flood_cells.add_argument("overlay")
    flood_cells.add_argument("output")
    evidence = commands.add_parser("build-houston-evidence", help="join checked Houston artifacts into honest pairwise cell evidence")
    evidence.add_argument("nisar")
    evidence.add_argument("houstonnet")
    evidence.add_argument("groundwater")
    evidence.add_argument("fema")
    evidence.add_argument("output")
    evidence.add_argument("--reference-bbox", nargs=4, type=float, metavar=("WEST", "SOUTH", "EAST", "NORTH"), help="independently justified stable-reference region; omitted means no signal threshold is calculated")
    evidence.add_argument("--cell-flood-context", default=None, help="output of fema-cell-context; omitted means no cell-level flood label is assigned")
    evidence.add_argument("--compaction", default=None, help="normalized USGS extensometer-compaction summary; adds mechanism context only")
    evidence.add_argument("--opera-historic-pair", default=None, help="quality-masked OPERA historical pair; adds context only, never a rate")
    groundtruth = commands.add_parser("groundtruth-report", help="validate GroundTruth Node session artifacts")
    groundtruth.add_argument("manifest")
    groundtruth.add_argument("output")
    reference = commands.add_parser("reference-review-candidates", help="rank review candidates without certifying a stable radar reference region")
    reference.add_argument("nisar")
    reference.add_argument("houstonnet")
    reference.add_argument("output")
    temporal = commands.add_parser("temporal-network-diagnostic", help="check date graph redundancy before reference selection or inversion")
    temporal.add_argument("output")
    temporal.add_argument("inputs", nargs="+", help="pair-cell JSON artifacts in chronological order")
    integrity = commands.add_parser("validate-nisar-pair", help="write a structural integrity report for a compact NISAR pair artifact")
    integrity.add_argument("input")
    integrity.add_argument("output")
    compaction = commands.add_parser("usgs-extensometer", help="normalize an explicitly mapped USGS/HGSD cumulative-compaction CSV")
    compaction.add_argument("input")
    compaction.add_argument("output")
    compaction.add_argument("--column-map", required=True, help="JSON mapping for station_id, longitude, latitude, date, cumulative_compaction")
    compaction.add_argument("--unit", default="ft")
    compaction_release = commands.add_parser("usgs-extensometer-release", help="normalize the official USGS 2023 TABLE1/TABLE2-15 extensometer release")
    compaction_release.add_argument("directory")
    compaction_release.add_argument("output")
    opera_temporal = commands.add_parser("opera-temporal-invert", help="invert a redundant multi-year OPERA network after stable-reference review")
    opera_temporal.add_argument("output")
    opera_temporal.add_argument("--reference-cell", required=True)
    opera_temporal.add_argument("inputs", nargs="+")
    args = parser.parse_args()
    if args.command == "inspect-h5":
        print(json.dumps(inspect_hdf5(args.input), indent=2))
    elif args.command == "nisar-gunw":
        kwargs = {"wavelength_m": args.wavelength_m, "crs": args.crs, "x_path": args.x_path, "y_path": args.y_path, "cell_pixels": args.cell_pixels, "acquisition_dates": (args.reference_date, args.secondary_date)}
        if args.bbox:
            kwargs["bounding_box"] = tuple(args.bbox)
        if args.phase_path: kwargs["phase_path"] = args.phase_path
        if args.coherence_path: kwargs["coherence_path"] = args.coherence_path
        if args.components_path: kwargs["connected_components_path"] = args.components_path
        write_pair_cells(args.input, args.output, GunwConfig(**kwargs))
    elif args.command == "opera-disp":
        write_disp_cells(args.input, args.output, OperaConfig(crs=args.crs, x_path=args.x_path, y_path=args.y_path, displacement_path=args.displacement_path, recommended_mask_path=args.recommended_mask_path, water_mask_path=args.water_mask_path, cell_pixels=args.cell_pixels, reference_date=args.reference_date, secondary_date=args.secondary_date, bounding_box=tuple(args.bbox) if args.bbox else None))
    elif args.command == "usgs-groundwater":
        write_groundwater_daily(args.input, args.output)
    elif args.command == "fema-nfhl-join":
        write_nfhl_point_join(args.groundwater, args.responses, args.output)
    elif args.command == "fema-nfhl-overlay":
        write_nfhl_zone_overlay(tuple(args.bbox), args.output, args.tile_degrees)
    elif args.command == "fema-merge-tiles":
        write_merged_nfhl_geojson_tiles(args.tile_directory, tuple(args.bbox), args.tile_degrees, args.max_allowable_offset_degrees, args.output)
    elif args.command == "fema-cell-context":
        write_cell_center_flood_context(args.nisar, args.overlay, args.output)
    elif args.command == "build-houston-evidence":
        write_houston_evidence(args.nisar, args.houstonnet, args.groundwater, args.fema, args.output, tuple(args.reference_bbox) if args.reference_bbox else None, args.cell_flood_context, args.compaction, args.opera_historic_pair)
    elif args.command == "groundtruth-report":
        write_groundtruth_report(args.manifest, args.output)
    elif args.command == "reference-review-candidates":
        write_reference_review_candidates(args.nisar, args.houstonnet, args.output)
    elif args.command == "temporal-network-diagnostic":
        write_network_diagnostic(args.inputs, args.output)
    elif args.command == "validate-nisar-pair":
        write_pair_integrity_report(args.input, args.output)
    elif args.command == "usgs-extensometer":
        write_extensometer_csv(args.input, args.output, json.loads(args.column_map), args.unit)
    elif args.command == "usgs-extensometer-release":
        write_usgs_2023_release(args.directory, args.output)
    elif args.command == "opera-temporal-invert":
        invert_opera_files(args.inputs, args.output, args.reference_cell)
    else:
        write_velocity_stations(args.input, args.output, json.loads(args.column_map))


if __name__ == "__main__":
    main()
