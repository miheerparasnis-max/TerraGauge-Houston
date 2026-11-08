import tempfile
import unittest
from pathlib import Path

try:
    import numpy as np
    import rasterio
    from rasterio.transform import from_bounds
except ImportError:  # pragma: no cover
    rasterio = None

from backend.ingestion.raster_layers import cell_bounds_lonlat


class CellBoundsTests(unittest.TestCase):
    def test_bounds_are_about_one_km(self):
        west, south, east, north = cell_bounds_lonlat("epsg3857-1km--10641-3476")
        self.assertAlmostEqual(east - west, 1000 / 6378137 * 180 / 3.141592653589793, places=6)
        self.assertTrue(-95.7 < west < -95.5 and 29.7 < south < 29.9)


@unittest.skipIf(rasterio is None, "rasterio is an ingestion-only dependency")
class SampleLayerTests(unittest.TestCase):
    def test_dswx_water_fraction_and_masking(self):
        from backend.ingestion.raster_layers import sample_layer

        cid = "epsg3857-1km--10641-3476"
        w, s, e, n = cell_bounds_lonlat(cid)
        data = np.zeros((10, 10), dtype=np.uint8)
        data[:5, :] = 1      # half open water
        data[9, :] = 253     # one row cloud-masked
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "dswx.tif"
            with rasterio.open(path, "w", driver="GTiff", width=10, height=10, count=1, dtype="uint8", crs="EPSG:4326", transform=from_bounds(w, s, e, n, 10, 10), nodata=255) as dst:
                dst.write(data, 1)
            rows = sample_layer([path], [{"cell_id": cid}], "dswx")
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["water_fraction"], 50 / 90, places=2)


if __name__ == "__main__":
    unittest.main()
