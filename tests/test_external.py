"""ADR-0021 — 외주 경로 코어 테스트."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import external, paths  # noqa: E402


class ValidateProjectNameTest(unittest.TestCase):
    def test_valid_names_pass(self):
        for name in ("lskun-kit", "proj_1", "a", "P123"):
            external.validate_project_name(name)  # no raise

    def test_traversal_blocked(self):
        for bad in ("..", ".", "../etc", "a/b", "a..b", ".hidden", "", "a\x00b"):
            with self.assertRaises(ValueError, msg=f"{bad!r} should raise"):
                external.validate_project_name(bad)


class ExternalRootTest(unittest.TestCase):
    def test_external_root_under_company(self):
        root = external.external_root("Acme", "lskun-kit")
        expected = paths.company_root("Acme") / "external" / "lskun-kit"
        self.assertEqual(root, expected)

    def test_external_root_is_relative_to_company(self):
        co = paths.company_root("Acme").resolve()
        root = external.external_root("Acme", "lskun-kit").resolve()
        self.assertTrue(root.is_relative_to(co))

    def test_external_root_rejects_bad_project(self):
        with self.assertRaises(ValueError):
            external.external_root("Acme", "..")

    def test_external_root_rejects_bad_company(self):
        with self.assertRaises(ValueError):
            external.external_root("..", "lskun-kit")


if __name__ == "__main__":
    unittest.main()
