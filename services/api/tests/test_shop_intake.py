import unittest
from pathlib import Path

from app.shop_intake import (
    _heuristic_map,
    _looks_like_nasa,
    _read_table,
    _score_shop_group,
    _shop_work,
    _split_manual,
    check_healthy_window,
)

DIESEL = Path(__file__).resolve().parents[3] / "data" / "shop" / "marine-diesel-sample.csv"


class ShopIntakeTest(unittest.TestCase):
    def test_maps_diesel_headers(self) -> None:
        raw = DIESEL.read_text(encoding="utf-8")
        frame = _read_table(raw)
        mapping = _heuristic_map(frame)
        self.assertEqual(mapping["unit"], "unit")
        self.assertEqual(mapping["cycle"], "hour")
        names = {item["column"] for item in mapping["sensors"]}
        self.assertIn("oil_temp", names)
        self.assertIn("oil_pressure", names)

    def test_diesel_is_not_nasa(self) -> None:
        raw = DIESEL.read_text(encoding="utf-8")
        self.assertFalse(_looks_like_nasa(_read_table(raw)))

    def test_later_hours_do_not_change_healthy_scores(self) -> None:
        raw = DIESEL.read_text(encoding="utf-8")
        mapping = _heuristic_map(_read_table(raw))
        work, keys = _shop_work(raw, mapping)
        unit = work[work["unit"] == 1].sort_values("cycle")
        early = _score_shop_group(unit[unit["cycle"] <= 20], keys, 1, 20)
        full = _score_shop_group(unit, keys, 1, 20)
        early_scores = early.sort_values("cycle")["if_score"].to_numpy()
        full_scores = full[full["cycle"] <= 20].sort_values("cycle")["if_score"].to_numpy()
        self.assertEqual(len(early_scores), len(full_scores))
        self.assertTrue(max(abs(left - right) for left, right in zip(early_scores, full_scores)) < 1e-6)

    def test_rejects_a_short_healthy_window(self) -> None:
        check_healthy_window(1, 30)
        with self.assertRaises(ValueError):
            check_healthy_window(1, 7)
        with self.assertRaises(ValueError):
            check_healthy_window(20, 24)

    def test_splits_a_numbered_procedure(self) -> None:
        parsed = _split_manual(
            "1. Read oil temperature on wing.\n2. Confirm oil pressure dropped.\n3. Open the case only if both agree."
        )
        self.assertEqual(len(parsed["steps"]), 3)
        self.assertTrue(parsed["steps"][0].startswith("Read oil"))


if __name__ == "__main__":
    unittest.main()
