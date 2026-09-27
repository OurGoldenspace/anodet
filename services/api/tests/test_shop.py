import os
import tempfile
import unittest
from pathlib import Path


class ShopScopeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["ANODET_DB"] = str(Path(self._folder.name) / "shop.db")
        os.environ["SHOP_ID"] = "alpha"
        from app.store import init_db

        init_db()

    def tearDown(self) -> None:
        self._folder.cleanup()
        os.environ.pop("ANODET_DB", None)
        os.environ["SHOP_ID"] = "sample"

    def test_fixes_do_not_cross_shops(self) -> None:
        from app.store import list_fixes, save_fix

        save_fix(
            unit_id=31,
            cycle=189,
            signature=[{"key": "s8", "name": "NRf", "direction": "high"}],
            manual_section="4.2 Hot-section wear",
            decision="modify",
            steps=["Check bleed first."],
            cause="Wear",
            resolved=True,
            note="",
            author="Pat",
            outcome="worked",
        )
        self.assertEqual(len(list_fixes()), 1)
        os.environ["SHOP_ID"] = "beta"
        self.assertEqual(list_fixes(), [])
        os.environ["SHOP_ID"] = "alpha"
        self.assertEqual(list_fixes()[0]["author"], "Pat")

    def test_passphrase_hint_is_off_by_default(self) -> None:
        from app.auth import passphrase_hint

        previous = os.environ.pop("SHOP_PASSPHRASE_HINT", None)
        try:
            self.assertIsNone(passphrase_hint())
            os.environ["SHOP_PASSPHRASE_HINT"] = "1"
            self.assertEqual(passphrase_hint(), "sample-shop")
        finally:
            if previous is None:
                os.environ.pop("SHOP_PASSPHRASE_HINT", None)
            else:
                os.environ["SHOP_PASSPHRASE_HINT"] = previous


if __name__ == "__main__":
    unittest.main()
