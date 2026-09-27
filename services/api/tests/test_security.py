import os
import tempfile
import unittest
from pathlib import Path


class SecurityTest(unittest.TestCase):
    def setUp(self) -> None:
        self._folder = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.environ["ANODET_DB"] = str(Path(self._folder.name) / "shop.db")
        os.environ["SHOP_ID"] = "alpha"

    def tearDown(self) -> None:
        self._folder.cleanup()
        os.environ.pop("ANODET_DB", None)
        os.environ["SHOP_ID"] = "sample"
        os.environ.pop("DEMO_TOOLS", None)
        os.environ.pop("SHOP_LEAD", None)
        from app import auth

        auth._SIGN_IN.clear()

    def test_wrong_passphrase_is_rejected(self) -> None:
        from app.auth import sign_in

        with self.assertRaises(ValueError):
            sign_in("Pat", "wrong-pass")

    def test_sign_in_rate_limit(self) -> None:
        from app.auth import allow_sign_in

        for _ in range(8):
            self.assertTrue(allow_sign_in("127.0.0.1"))
        self.assertFalse(allow_sign_in("127.0.0.1"))

    def test_demo_tools_default_on(self) -> None:
        from app.auth import demo_tools_enabled

        os.environ.pop("DEMO_TOOLS", None)
        self.assertTrue(demo_tools_enabled())
        os.environ["DEMO_TOOLS"] = "0"
        self.assertFalse(demo_tools_enabled())

    def test_member_token_is_shop_scoped(self) -> None:
        from app.store import init_db, member_from_token, open_member

        init_db()
        member = open_member("Pat")
        self.assertEqual(member["shopId"], "alpha")
        self.assertEqual(member["role"], "lead")
        self.assertIsNotNone(member_from_token(str(member["token"])))
        os.environ["SHOP_ID"] = "beta"
        self.assertIsNone(member_from_token(str(member["token"])))

    def test_second_name_is_technician(self) -> None:
        from app.store import init_db, open_member

        init_db()
        open_member("Pat")
        tech = open_member("Alex")
        self.assertEqual(tech["role"], "technician")

    def test_named_lead_wins(self) -> None:
        os.environ["SHOP_LEAD"] = "Alex"
        from app.store import init_db, open_member

        init_db()
        first = open_member("Pat")
        named = open_member("Alex")
        self.assertEqual(named["role"], "lead")
        os.environ.pop("SHOP_LEAD", None)
        self.assertIn(first["role"], {"lead", "technician"})


if __name__ == "__main__":
    unittest.main()
