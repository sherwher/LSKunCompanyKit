"""lskun_kit.hooks.session_start 단위 테스트 — ADR-0004 §1 layer B."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit.hooks import session_start  # noqa: E402
from lskun_kit.init import run as init_run  # noqa: E402


def _capture(func, env: dict[str, str], cwd: Path) -> tuple[int, str, str]:
    old_env = os.environ.copy()
    old_cwd = Path.cwd()
    os.environ.clear()
    os.environ.update(env)
    os.chdir(cwd)
    out_buf, err_buf = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out_buf), redirect_stderr(err_buf):
            rc = func()
    finally:
        os.environ.clear()
        os.environ.update(old_env)
        os.chdir(old_cwd)
    return rc, out_buf.getvalue(), err_buf.getvalue()


class SessionStartHookTests(unittest.TestCase):
    def test_silent_when_no_active_company(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rc, out, _ = _capture(session_start.main, env={}, cwd=Path(tmp))
            self.assertEqual(rc, 0)
            self.assertEqual(out, "")  # silent

    def test_emits_context_for_local_company(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # init 으로 회사 셋업
            init_run(Path(tmp), cpo_name="이세근", hr_name="김지혜", env={})
            rc, out, _ = _capture(session_start.main, env={}, cwd=Path(tmp))
            self.assertEqual(rc, 0)
            self.assertTrue(out)
            payload = json.loads(out)
            ctx = payload["hookSpecificOutput"]["additionalContext"]
            self.assertIn("LSKunCompanyKit", ctx)
            self.assertIn("이세근", ctx)
            self.assertIn("김지혜", ctx)
            self.assertIn("cpo", ctx)
            self.assertIn("hr-lead", ctx)

    def test_emits_context_for_vault_company(self) -> None:
        with tempfile.TemporaryDirectory() as vault:
            with tempfile.TemporaryDirectory() as proj:
                init_run(
                    Path(proj),
                    company_name="Acme",
                    cpo_name="이세근",
                    hr_name="김지혜",
                    env={"LSKUN_VAULT": vault, "LSKUN_COMPANY": "Acme"},
                )
                rc, out, _ = _capture(
                    session_start.main,
                    env={"LSKUN_VAULT": vault, "LSKUN_COMPANY": "Acme"},
                    cwd=Path(proj),
                )
                self.assertEqual(rc, 0)
                payload = json.loads(out)
                ctx = payload["hookSpecificOutput"]["additionalContext"]
                self.assertIn("Acme", ctx)
                self.assertIn("03_Companies", ctx)

    def test_finds_company_in_parent_directory(self) -> None:
        # 워크플로: 사용자가 회사 root 의 하위 디렉토리에서 작업
        with tempfile.TemporaryDirectory() as tmp:
            init_run(Path(tmp), cpo_name="이세근", hr_name="김지혜", env={})
            subdir = Path(tmp) / "src" / "deep"
            subdir.mkdir(parents=True)
            rc, out, _ = _capture(session_start.main, env={}, cwd=subdir)
            self.assertEqual(rc, 0)
            self.assertTrue(out)
            ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("이세근", ctx)

    def test_includes_cpo_history_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            init_run(Path(tmp), cpo_name="이세근", hr_name="김지혜", env={})
            # CPO 에 history 한 줄 박제
            from lskun_kit.adapters.local import LocalAdapter
            from lskun_kit.models import HistoryEntry
            from datetime import date

            LocalAdapter(Path(tmp) / ".company").append_history(
                "cpo",
                HistoryEntry(
                    date=date(2026, 5, 18),
                    project="onboarding",
                    topic="routing",
                    pattern="domain-first",
                    first_pass_score=88,
                ),
            )
            rc, out, _ = _capture(session_start.main, env={}, cwd=Path(tmp))
            ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("CPO 최근 history", ctx)
            self.assertIn("domain-first", ctx)

    def test_does_not_crash_on_broken_company_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            company_dir = Path(tmp) / ".company"
            company_dir.mkdir()
            (company_dir / "company.md").write_text("not valid frontmatter at all")
            rc, out, _ = _capture(session_start.main, env={}, cwd=Path(tmp))
            # broken company.md 도 silent 한 처리 — rc=0
            self.assertEqual(rc, 0)
            # 회사가 감지는 되지만 meta 가 비어있을 수 있음
            # (additionalContext 가 empty 일 수도, 헤더만 있을 수도 — 둘 다 허용)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
