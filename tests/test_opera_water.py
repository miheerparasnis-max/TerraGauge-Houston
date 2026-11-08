import unittest

try:
    import numpy as np
except ImportError:  # pragma: no cover - ingestion-only dependency
    np = None


@unittest.skipIf(np is None, "numpy is an ingestion-only dependency")
class OperaWaterMaskTests(unittest.TestCase):
    def test_zero_means_water_per_product_spec(self):
        from backend.ingestion.opera import water_fraction

        land_only = np.ones((3, 3), dtype=np.uint8)
        self.assertEqual(water_fraction(land_only), 0.0)
        mostly_water = np.array([[0, 0, 0], [0, 0, 1], [1, 1, 1]], dtype=np.uint8)
        self.assertAlmostEqual(water_fraction(mostly_water), 5 / 9)


if __name__ == "__main__":
    unittest.main()
