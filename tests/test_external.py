"""ADR-0021 — 외주 경로 코어 테스트."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class PersonaPathTest(unittest.TestCase):
    def test_redteam_persona_path(self):
        p = external.persona_path("Acme", "proj", "redteam", "competitor-analyst")
        root = external.external_root("Acme", "proj")
        self.assertEqual(p, root / "redteam" / "competitor-analyst.md")

    def test_customer_persona_path(self):
        p = external.persona_path("Acme", "proj", "customers", "power-user")
        root = external.external_root("Acme", "proj")
        self.assertEqual(p, root / "customers" / "power-user.md")

    def test_invalid_kind_rejected(self):
        with self.assertRaises(ValueError):
            external.persona_path("Acme", "proj", "redteam-evil", "x")

    def test_invalid_persona_name_rejected(self):
        for bad in ("..", "a/b", ".hidden", ""):
            with self.assertRaises(ValueError):
                external.persona_path("Acme", "proj", "redteam", bad)

    def test_persona_path_is_relative_to_root(self):
        root = external.external_root("Acme", "proj").resolve()
        p = external.persona_path("Acme", "proj", "redteam", "x").resolve()
        self.assertTrue(p.is_relative_to(root))

    def test_brief_path(self):
        p = external.brief_path("Acme", "proj")
        self.assertEqual(p, external.external_root("Acme", "proj") / "brief.md")


class ListPersonasTest(unittest.TestCase):
    def test_list_empty_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(paths.Path, "home", return_value=Path(tmp)):
                self.assertEqual(
                    external.list_external_personas("Acme", "proj", "redteam"), []
                )

    def test_list_returns_sorted_stems(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(paths.Path, "home", return_value=Path(tmp)):
                d = external.external_root("Acme", "proj") / "redteam"
                d.mkdir(parents=True)
                (d / "b-critic.md").write_text("x")
                (d / "a-critic.md").write_text("x")
                (d / "note.txt").write_text("x")  # 비-md 무시
                self.assertEqual(
                    external.list_external_personas("Acme", "proj", "redteam"),
                    ["a-critic", "b-critic"],
                )


class ExternalTemplatePathTest(unittest.TestCase):
    """Task 8 — 외주 template path resolver (ADR-0021)."""

    def test_external_templates_dir_points_to_repo_root(self):
        d = external.external_templates_dir()
        repo_root = Path(__file__).resolve().parents[1]
        self.assertEqual(d, repo_root / "templates")

    def test_external_template_path_redteam(self):
        p = external.external_template_path("redteam")
        self.assertEqual(p.name, "redteam.md")
        self.assertTrue(p.exists(), f"{p} not found (Task 7 에서 생성됨)")

    def test_external_template_path_customer(self):
        p = external.external_template_path("customer")
        self.assertEqual(p.name, "customer.md")
        self.assertTrue(p.exists())

    def test_external_template_path_customers_alias(self):
        # "customers" alias 도 customer.md 로 매핑.
        p = external.external_template_path("customers")
        self.assertEqual(p.name, "customer.md")

    def test_external_template_path_invalid_kind(self):
        with self.assertRaises(ValueError):
            external.external_template_path("bogus")

    def test_templates_dir_sibling_to_src(self):
        """repo root 가 정말 src/ 형제 디렉토리를 갖는지 sanity 검증."""
        d = external.external_templates_dir()
        # repo root 에는 반드시 src/ 가 형제로 존재해야 함.
        self.assertTrue((d.parent / "src").is_dir(),
                        f"external_templates_dir miscalculated: {d}")

    def test_templates_dir_raises_if_relocated(self):
        """external.py 가 이동되어 parents[2] 가 잘못된 곳을 가리키면 명시 raise."""
        # __file__ 을 src/ 가 없는 임시 경로로 가장해 parents[2] miscalculation 시뮬레이션
        with mock.patch.object(external, "__file__",
                                "/tmp/nonexistent/foo/bar/external.py"):
            with self.assertRaises(RuntimeError) as ctx:
                external.external_templates_dir()
            self.assertIn("miscalculated", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
