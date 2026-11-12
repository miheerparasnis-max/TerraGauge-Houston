import json
import tempfile
import unittest
from pathlib import Path

from backend.ingestion.nisar import GunwConfig, extract_pair_cells, phase_to_los_mm, resolve_wavelength, wavelength_from_center_frequency

ROOT_PATH = "/science/LSAR/GUNW/grids/frequencyA"
LAYER = f"{ROOT_PATH}/unwrappedInterferogram/HH"


class WavelengthTests(unittest.TestCase):
    def test_phase_conversion_matches_product_wavelength(self):
        # MASTER B4 (v3.1): lambda/(4 pi) = 19.255 mm per radian at 0.241962 m.
        self.assertAlmostEqual(phase_to_los_mm(1.0, 0.241962), 19.255, places=3)
        self.assertAlmostEqual(phase_to_los_mm(2 * 3.141592653589793, 0.241962), 120.98, places=2)

    def test_center_frequency_gives_wavelength(self):
        self.assertAlmostEqual(wavelength_from_center_frequency(1.239e9), 0.241963, places=6)
        with self.assertRaises(ValueError):
            wavelength_from_center_frequency(1.239)  # GHz passed as Hz

    def test_metadata_wins_and_records_its_source(self):
        value, record = resolve_wavelength(None, [("/x/centerFrequency", 1.239e9)])
        self.assertAlmostEqual(value, 0.241963, places=6)
        self.assertEqual(record["source"], "product_metadata")
        self.assertEqual(record["metadata_paths"], ["/x/centerFrequency"])

    def test_cli_value_that_disagrees_with_metadata_is_rejected(self):
        with self.assertRaises(ValueError):
            resolve_wavelength(0.238, [("/x/centerFrequency", 1.239e9)])

    def test_cli_value_that_agrees_is_accepted_and_metadata_is_used(self):
        value, record = resolve_wavelength(0.241962, [("/x/centerFrequency", 1.239e9)])
        self.assertAlmostEqual(value, 0.241963, places=6)
        self.assertEqual(record["source"], "product_metadata_cli_agrees")

    def test_cli_value_without_metadata_is_marked_unverified(self):
        value, record = resolve_wavelength(0.241962, [])
        self.assertEqual(value, 0.241962)
        self.assertEqual(record["source"], "cli_unverified")

    def test_no_wavelength_anywhere_fails_loudly(self):
        with self.assertRaises(ValueError):
            resolve_wavelength(None, [])

    def test_inconsistent_metadata_frequencies_fail_loudly(self):
        with self.assertRaises(ValueError):
            resolve_wavelength(None, [("/a", 1.239e9), ("/b", 1.257e9)])


class SyntheticGunwTests(unittest.TestCase):
    """End-to-end extraction from a tiny synthetic GUNW (needs h5py and pyproj)."""

    def write_gunw(self, path, with_frequency=True):
        import h5py
        import numpy as np

        with h5py.File(path, "w") as f:
            f[f"{LAYER}/xCoordinates"] = 278000.0 + 80.0 * np.arange(26)
            f[f"{LAYER}/yCoordinates"] = 3290000.0 - 80.0 * np.arange(26)
            f[f"{LAYER}/unwrappedPhase"] = np.ones((26, 26))
            f[f"{LAYER}/coherenceMagnitude"] = np.full((26, 26), 0.8)
            f[f"{LAYER}/connectedComponents"] = np.ones((26, 26), dtype="uint16")
            f["/science/LSAR/GUNW/metadata/processingInformation/parameters/geocoding/wetTroposphericCorrectionApplied"] = "True"
            if with_frequency:
                f[f"{ROOT_PATH}/centerFrequency"] = 1.239e9

    def config(self, wavelength_m=None):
        return GunwConfig(wavelength_m=wavelength_m, crs="EPSG:32615", x_path=f"{LAYER}/xCoordinates", y_path=f"{LAYER}/yCoordinates", acquisition_dates=("2025-11-02", "2025-11-14"))

    def test_extraction_uses_metadata_wavelength_and_writes_correction_record(self):
        from backend.ingestion.quality import validate_pair_artifact

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "gunw.h5"
            self.write_gunw(source)
            artifact = extract_pair_cells(source, self.config())
            self.assertEqual(artifact["wavelength"]["source"], "product_metadata")
            self.assertEqual(len(artifact["cells"]), 4)
            for cell in artifact["cells"]:
                self.assertAlmostEqual(cell["pair_los_displacement_mm"], 19.255, places=2)
            for name in ("ionosphere", "troposphere", "tide"):
                self.assertIsNone(artifact["applied_corrections"][f"{name}_applied"])
            artifact["parameters"]["bounding_box"] = [-96.0, 29.0, -94.0, 31.0]
            out = Path(directory) / "pair.json"
            out.write_text(json.dumps(artifact), encoding="utf-8")
            self.assertTrue(validate_pair_artifact(out)["pass"], validate_pair_artifact(out)["findings"])

    def test_extraction_rejects_a_wrong_cli_wavelength(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "gunw.h5"
            self.write_gunw(source)
            with self.assertRaises(ValueError):
                extract_pair_cells(source, self.config(0.238))

    def test_extraction_without_frequency_needs_an_explicit_wavelength(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "gunw.h5"
            self.write_gunw(source, with_frequency=False)
            with self.assertRaises(ValueError):
                extract_pair_cells(source, self.config())
            artifact = extract_pair_cells(source, self.config(0.241962))
            self.assertEqual(artifact["wavelength"]["source"], "cli_unverified")


if __name__ == "__main__":
    unittest.main()
