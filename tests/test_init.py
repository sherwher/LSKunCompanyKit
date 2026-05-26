"""lskun_kit.init 단위 테스트.

ADR-0015 (2026-05-22) — Local SSOT 단일화 + 멱등성 4행 명세.

본 모듈은 init 동작을 검증한다:
    - resolve_company_root: ``~/.lskun-companies/<name>/`` 단일 backend
    - 회사 자원 박제 (company.md + hired/cpo|hr-lead.md)
    - CPO / HR 자동 hire + 멱등성 (재실행 시 skip)
    - CLAUDE.md inline persona 박제
    - 결정 2-B 멱등성 4행 분기 (founded / joined / silent / marker_replaced)
    - ConfirmRequired 패턴 (옵션 B — caller 가 confirm 후 재호출)

테스트 격리: ``Path.home()`` 를 tempdir 로 mock 하여 사용자 홈 디렉토리 오염 0.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import LocalAdapter  # noqa: E402
from lskun_kit.adapters import frontmatter  # noqa: E402
from lskun_kit.errors import ConfirmRequired  # noqa: E402
from lskun_kit.init import (  # noqa: E402
    resolve_company_root,
    run,
)
from lskun_kit.paths import lskun_companies_root  # noqa: E402
from lskun_kit.persona_injection import (  # noqa: E402
    CLAUDE_MD_FILENAME,
    PERSONA_MARKER_START,
    detect as detect_persona,
    extract_company_name as extract_marker_company,
)


def _patched_home(fake_home: str):
    """Path.home() 을 fake_home 로 patch 하는 context manager."""
    return mock.patch("lskun_kit.paths.Path.home",
                      return_value=Path(fake_home))


class ResolveCompanyRootTests(unittest.TestCase):
    """ADR-0015 — resolve_company_root 는 항상 ``~/.lskun-companies/<name>/``."""

    def test_returns_home_based_root(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home:
            with _patched_home(fake_home):
                backend, name, root = resolve_company_root("LSKun")
                self.assertEqual(backend, "local")
                self.assertEqual(name, "LSKun")
                self.assertEqual(root, Path(fake_home) / ".lskun-companies" / "LSKun")

    def test_invalid_company_name_rejected(self) -> None:
        for bad in ("..", ".backups", "a/b", "한글이름"):
            with self.assertRaises(ValueError, msg=f"{bad!r}"):
                resolve_company_root(bad)


class RunIdempotencyRow1FoundedTests(unittest.TestCase):
    """ADR-0015 결정 2-B row 1 — 신규 회사 + 신규 프로젝트."""

    def test_founded_creates_everything(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as proj:
            with _patched_home(fake_home):
                result = run(
                    Path(proj), company_name="LSKun",
                    cpo_name="이세근", hr_name="김지혜",
                )
                self.assertEqual(result.backend, "local")
                self.assertEqual(result.idempotency_row, "founded")
                self.assertTrue(result.company_md_created)
                self.assertEqual(sorted(result.workers_created), ["cpo", "hr-lead"])

                # 회사 root 가 ~/.lskun-companies/<name>/ 하위
                expected = Path(fake_home) / ".lskun-companies" / "LSKun"
                self.assertEqual(result.company_root, expected)
                self.assertTrue((expected / "company.md").exists())
                self.assertTrue((expected / "hired" / "cpo.md").exists())

                # marker 가 프로젝트 root 에 박제됨
                self.assertTrue(detect_persona(Path(proj)))
                self.assertEqual(extract_marker_company(Path(proj)), "LSKun")

    def test_founded_records_domain(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as proj:
            with _patched_home(fake_home):
                run(Path(proj), company_name="Acme",
                    domain="의료 SaaS",
                    cpo_name="이세근", hr_name="김지혜")
                company_md = (Path(fake_home) / ".lskun-companies" / "Acme"
                              / "company.md")
                parsed = frontmatter.parse(company_md.read_text(encoding="utf-8"))
                self.assertEqual(parsed.frontmatter.get("domain"), "의료 SaaS")

    def test_founded_default_company_name_from_project_dir(self) -> None:
        """회사명 생략 시 project 디렉토리명 fallback."""
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as proj:
            proj_subdir = Path(proj) / "MyCompany"
            proj_subdir.mkdir()
            with _patched_home(fake_home):
                result = run(proj_subdir, cpo_name="이세근", hr_name="김지혜")
                self.assertEqual(result.company_name, "MyCompany")

    def test_founded_rejects_missing_cpo_name(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as proj:
            with _patched_home(fake_home):
                with self.assertRaises(ValueError) as ctx:
                    run(Path(proj), company_name="LSKun", hr_name="김지혜")
                self.assertIn("cpo", str(ctx.exception).lower())


class RunIdempotencyRow2JoinedTests(unittest.TestCase):
    """ADR-0015 결정 2-B row 2 — 기존 회사 + 신규 프로젝트 (joining)."""

    def test_joining_preserves_company_resources(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as proj_a, \
             tempfile.TemporaryDirectory() as proj_b:
            with _patched_home(fake_home):
                # proj_a 에서 회사 창설
                run(Path(proj_a), company_name="LSKun",
                    cpo_name="이세근", hr_name="김지혜")
                co_md = (Path(fake_home) / ".lskun-companies" / "LSKun"
                         / "company.md")
                original = co_md.read_text(encoding="utf-8")

                # proj_b 에서 joining
                result = run(Path(proj_b), company_name="LSKun",
                             cpo_name="이세근", hr_name="김지혜")
                self.assertEqual(result.idempotency_row, "joined")
                self.assertFalse(result.company_md_created)
                # 회사 자원 그대로
                self.assertEqual(co_md.read_text(encoding="utf-8"), original)
                # 워커 도 skip (이미 hired)
                self.assertEqual(result.workers_created, [])
                self.assertEqual(sorted(result.workers_skipped), ["cpo", "hr-lead"])
                # 그러나 proj_b 의 CLAUDE.md marker 는 박제됨
                self.assertTrue(detect_persona(Path(proj_b)))
                self.assertEqual(extract_marker_company(Path(proj_b)), "LSKun")


class RunIdempotencyRow3SilentTests(unittest.TestCase):
    """ADR-0015 결정 2-B row 3 — 같은 회사 marker 재진입 silent skip."""

    def test_silent_skip_when_same_company_marker_present(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as proj:
            with _patched_home(fake_home):
                # 1차 init
                run(Path(proj), company_name="LSKun",
                    cpo_name="이세근", hr_name="김지혜")
                claude_md = Path(proj) / "CLAUDE.md"
                first = claude_md.read_text(encoding="utf-8")

                # 2차 init (같은 회사)
                result = run(Path(proj), company_name="LSKun",
                             cpo_name="이세근", hr_name="김지혜")
                self.assertEqual(result.idempotency_row, "silent")
                self.assertEqual(result.workers_created, [])
                self.assertEqual(result.persona_action, "unchanged")
                # CLAUDE.md 한 글자도 안 변함
                self.assertEqual(claude_md.read_text(encoding="utf-8"), first)


class RunIdempotencyRow4MarkerReplaceTests(unittest.TestCase):
    """ADR-0015 결정 2-B row 4 — 다른 회사 marker 재진입 confirm 강제."""

    def test_raises_confirm_required_when_marker_different(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as proj:
            with _patched_home(fake_home):
                # 1차: LSKun 박제
                run(Path(proj), company_name="LSKun",
                    cpo_name="이세근", hr_name="김지혜")
                # 2차: Acme 시도 — confirm 없이는 ConfirmRequired
                with self.assertRaises(ConfirmRequired) as ctx:
                    run(Path(proj), company_name="Acme",
                        cpo_name="박지원", hr_name="이수민")
                err = ctx.exception
                self.assertEqual(err.kind, "marker_replace")
                self.assertIn("LSKun", err.prompt)
                self.assertIn("Acme", err.prompt)
                self.assertEqual(
                    err.context.get("current_marker_company"), "LSKun"
                )
                self.assertEqual(err.context.get("new_company"), "Acme")

    def test_replaces_marker_when_confirmed(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as proj:
            with _patched_home(fake_home):
                run(Path(proj), company_name="LSKun",
                    cpo_name="이세근", hr_name="김지혜")
                result = run(
                    Path(proj), company_name="Acme",
                    cpo_name="박지원", hr_name="이수민",
                    confirmed_replace_marker=True,
                )
                self.assertEqual(result.idempotency_row, "marker_replaced")
                # marker 의 회사가 Acme 로 교체됨
                self.assertEqual(extract_marker_company(Path(proj)), "Acme")

    def test_no_confirm_required_when_inject_persona_false(self) -> None:
        """marker 박제 자체를 skip 하면 cross-check 도 skip — 자유로운 재호출."""
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as proj:
            with _patched_home(fake_home):
                run(Path(proj), company_name="LSKun",
                    cpo_name="이세근", hr_name="김지혜")
                # inject_persona=False 면 marker 무관
                result = run(
                    Path(proj), company_name="Acme",
                    cpo_name="박지원", hr_name="이수민",
                    inject_persona=False,
                )
                # marker 는 LSKun 그대로
                self.assertEqual(extract_marker_company(Path(proj)), "LSKun")
                # Acme 는 신규 회사로 founded
                self.assertEqual(result.idempotency_row, "founded")


class RunPersonaInjectionTests(unittest.TestCase):
    def test_persona_marker_contains_company_and_display_name(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as proj:
            with _patched_home(fake_home):
                run(Path(proj), company_name="LSKun",
                    cpo_name="이세근", hr_name="김지혜")
                content = (Path(proj) / CLAUDE_MD_FILENAME).read_text(
                    encoding="utf-8"
                )
                self.assertIn(PERSONA_MARKER_START, content)
                self.assertIn("이세근", content)
                self.assertIn("LSKun", content)

    def test_persona_reinject_preserves_user_claude_md_outside_markers(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as proj:
            with _patched_home(fake_home):
                # 사용자가 먼저 CLAUDE.md 작성
                user_text = "# Project\n\n사용자 정의 가이드.\n"
                (Path(proj) / CLAUDE_MD_FILENAME).write_text(
                    user_text, encoding="utf-8"
                )
                run(Path(proj), company_name="LSKun",
                    cpo_name="이세근", hr_name="김지혜")
                content = (Path(proj) / CLAUDE_MD_FILENAME).read_text(
                    encoding="utf-8"
                )
                # 사용자 본문 보존 + persona 추가
                self.assertIn("사용자 정의 가이드.", content)
                self.assertIn(PERSONA_MARKER_START, content)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
