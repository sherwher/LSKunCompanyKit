"""P54 — ADR-0007 ``.claude/lskun-kit.json`` link 검증.

원칙:
- schema 검증 (company 필수, backend enum, backend_root abs)
- idempotent write (동일 내용 noop)
- 다른 내용 write 시 overwrite 강제
- JSON parse 실패 → ProjectLinkError
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import project_link as pl  # noqa: E402


class ProjectLinkSchemaTests(unittest.TestCase):
    def test_minimal_valid(self) -> None:
        link = pl.ProjectLink(company="Acme")
        self.assertEqual(link.company, "Acme")
        self.assertIsNone(link.backend)
        self.assertIsNone(link.backend_root)

    def test_company_required(self) -> None:
        with self.assertRaises(pl.ProjectLinkError):
            pl.ProjectLink(company="")
        with self.assertRaises(pl.ProjectLinkError):
            pl.ProjectLink(company="   ")

    def test_company_no_slash(self) -> None:
        with self.assertRaises(pl.ProjectLinkError):
            pl.ProjectLink(company="03_Companies/Acme")

    def test_company_no_dotdot(self) -> None:
        for bad in (".", ".."):
            with self.assertRaises(pl.ProjectLinkError):
                pl.ProjectLink(company=bad)

    def test_backend_enum(self) -> None:
        pl.ProjectLink(company="Acme", backend="vault")
        pl.ProjectLink(company="Acme", backend="local")
        pl.ProjectLink(company="Acme", backend=None)
        with self.assertRaises(pl.ProjectLinkError):
            pl.ProjectLink(company="Acme", backend="notion")

    def test_backend_root_must_be_absolute(self) -> None:
        with self.assertRaises(pl.ProjectLinkError):
            pl.ProjectLink(company="Acme", backend_root="relative/path")
        with self.assertRaises(pl.ProjectLinkError):
            pl.ProjectLink(company="Acme", backend_root="")
        pl.ProjectLink(company="Acme", backend_root="/abs/path")

    def test_to_dict_omits_none(self) -> None:
        d = pl.ProjectLink(company="Acme").to_dict()
        self.assertEqual(d, {"company": "Acme"})
        d2 = pl.ProjectLink(company="Acme", backend="vault").to_dict()
        self.assertEqual(d2, {"company": "Acme", "backend": "vault"})


class ReadWriteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_read_absent_returns_none(self) -> None:
        self.assertIsNone(pl.read(self.root))

    def test_write_creates_claude_dir(self) -> None:
        link = pl.ProjectLink(company="Acme")
        p = pl.write(self.root, link)
        self.assertEqual(p, self.root / ".claude" / "lskun-kit.json")
        self.assertTrue(p.exists())
        self.assertEqual(p.parent.name, ".claude")

    def test_roundtrip(self) -> None:
        link = pl.ProjectLink(company="Acme", backend="vault")
        pl.write(self.root, link)
        got = pl.read(self.root)
        self.assertEqual(got, link)

    def test_write_idempotent_same_content_is_noop(self) -> None:
        link = pl.ProjectLink(company="Acme")
        pl.write(self.root, link)
        # 다시 써도 raise 안 함
        pl.write(self.root, link)

    def test_write_rejects_different_content_without_overwrite(self) -> None:
        pl.write(self.root, pl.ProjectLink(company="Acme"))
        with self.assertRaises(pl.ProjectLinkError):
            pl.write(self.root, pl.ProjectLink(company="Beta"))

    def test_write_overwrite_force(self) -> None:
        pl.write(self.root, pl.ProjectLink(company="Acme"))
        pl.write(self.root, pl.ProjectLink(company="Beta"), overwrite=True)
        self.assertEqual(pl.read(self.root).company, "Beta")

    def test_read_malformed_json_raises(self) -> None:
        p = pl.link_path(self.root)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("not json{", encoding="utf-8")
        with self.assertRaises(pl.ProjectLinkError):
            pl.read(self.root)

    def test_read_non_object_raises(self) -> None:
        p = pl.link_path(self.root)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("[]", encoding="utf-8")
        with self.assertRaises(pl.ProjectLinkError):
            pl.read(self.root)

    def test_read_missing_company_raises(self) -> None:
        p = pl.link_path(self.root)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"backend": "vault"}), encoding="utf-8")
        with self.assertRaises(pl.ProjectLinkError):
            pl.read(self.root)

    def test_read_invalid_company_type_raises(self) -> None:
        p = pl.link_path(self.root)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"company": 42}), encoding="utf-8")
        with self.assertRaises(pl.ProjectLinkError):
            pl.read(self.root)

    def test_link_path_resolves_dotclaude(self) -> None:
        self.assertEqual(
            pl.link_path("/some/where"),
            Path("/some/where/.claude/lskun-kit.json"),
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
