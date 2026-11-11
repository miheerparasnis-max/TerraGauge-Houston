import unittest

try:
    import numpy as np
    import sklearn  # noqa: F401
except ImportError:  # pragma: no cover
    np = None


@unittest.skipIf(np is None, "numpy and scikit-learn are forecast-only dependencies")
class ForecastTests(unittest.TestCase):
    def test_learns_slowing_and_beats_persistence(self):
        from backend.forecast import train_and_forecast

        rng = np.random.default_rng(1)
        dates = [f"{2016 + i // 3}-{1 + 4 * (i % 3):02d}-01" for i in range(30)]
        years = np.array([2016 + i / 3 for i in range(30)])
        cells = []
        for k in range(600):
            lon, lat = -95.9 + (k % 30) * 0.035, 29.5 + (k // 30) * 0.03
            early = -rng.uniform(0, 20)
            late = early * 0.5  # every cell slows down by half after 2021
            series = np.where(years < 2021, early * (years - 2016), early * 5 + late * (years - 2021)) * np.cos(np.radians(38))
            series = series + rng.normal(0, 1, 30)
            cells.append({"cell_id": f"c{k}", "longitude": lon, "latitude": lat, "opera_series_mm": series.tolist()})
        result = train_and_forecast({"dates": dates, "cells": cells}, "2021-01-01")
        self.assertLess(result["scores"]["model"]["median_abs_error"], result["scores"]["past_rate_continues"]["median_abs_error"])
        self.assertEqual(len(result["cell_forecasts"]), 600)
        self.assertIn("passes", result)


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(np is None, "numpy is a forecast-only dependency")
class SeasonalAreaTests(unittest.TestCase):
    def test_recovers_trend_despite_seasonal_swing(self):
        from backend.forecast import seasonal_area_rates

        dates = [f"{2016 + i // 4}-{1 + 3 * (i % 4):02d}-15" for i in range(36)]
        years = np.array([2016 + i / 4 + 0.04 for i in range(36)])
        cells = []
        for k in range(30):
            vertical = -12 * (years - 2016) + 15 * np.sin(2 * np.pi * years)
            cells.append({"cell_id": f"c{k}", "longitude": -95.4 + k * 0.001, "latitude": 29.7, "opera_series_mm": (vertical * np.cos(np.radians(38))).tolist()})
        rates = seasonal_area_rates({"dates": dates, "cells": cells})
        self.assertAlmostEqual(rates["c0"], -12, delta=0.3)
