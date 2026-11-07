"""CLI entry points for auditable source-file conversion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .houstonnet import write_velocity_stations
from .nisar import GunwConfig, inspect_hdf5, write_pair_cells
from .opera import OperaConfig, write_disp_cells


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
    opera.add_argument("--cell-pixels", type=int, default=33)
    opera.add_argument("--reference-date", required=True)
    opera.add_argument("--secondary-date", required=True)
    hn = commands.add_parser("houstonnet-velocities", help="normalize a checked HoustonNet velocity CSV")
    hn.add_argument("input")
    hn.add_argument("output")
    hn.add_argument("--column-map", required=True, help="JSON mapping of standard field name to CSV header")
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
        write_disp_cells(args.input, args.output, OperaConfig(crs=args.crs, x_path=args.x_path, y_path=args.y_path, displacement_path=args.displacement_path, recommended_mask_path=args.recommended_mask_path, cell_pixels=args.cell_pixels, reference_date=args.reference_date, secondary_date=args.secondary_date))
    else:
        write_velocity_stations(args.input, args.output, json.loads(args.column_map))


if __name__ == "__main__":
    main()
