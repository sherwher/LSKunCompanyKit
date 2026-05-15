"""Stop hook — 환경변수 + 세션 상태에 따른 동작 검증."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import session  # noqa: E402
from lskun_kit.hooks import stop_reflect  # noqa: E402


WORKER_MD = dedent(
    """\
    ---
    name: alice
    role: backend-engineer
    hired_at: 2026-05-15
    storage_backend: local
    ---

    # alice

    ## Project History
    """
)


def _setup(tmp: Path) -> Path:
    root = tmp / ".company"
    (root / "hired").mkdir(parents=True)
    (root / "hired" / "alice.md").write_text(WORKER_MD, encoding="utf-8")
    return root


class StopReflectHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = _setup(Path(self.tmp.name))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _run_with_env(self, env: dict[str, str]) -> int:
        with patch.dict(os.environ, env, clear=True):
            return stop_reflect.main([])

    def test_no_root_returns_zero(self) -> None:
        self.assertEqual(self._run_with_env({}), 0)

    def test_no_active_session_returns_zero(self) -> None:
        self.assertEqual(
            self._run_with_env({"LSKUN_SSOT_ROOT": str(self.root)}), 0
        )

    def test_missing_reflection_fields_is_silent_noop(self) -> None:
        session.start(self.root, "alice")
        rc = self._run_with_env(
            {"LSKUN_SSOT_ROOT": str(self.root)}
        )
        self.assertEqual(rc, 0)
        # 세션은 그대로 살아있어야 함
        self.assertIsNotNone(session.read(self.root))

    def test_full_reflection_appends_and_clears_session(self) -> None:
        session.start(self.root, "alice")
        rc = self._run_with_env(
            {
                "LSKUN_SSOT_ROOT": str(self.root),
                "LSKUN_PROJECT": "music-pay",
                "LSKUN_TOPIC": "refund-flow",
                "LSKUN_PATTERN": "saga",
                "LSKUN_FIRST_PASS": "88",
            }
        )
        self.assertEqual(rc, 0)
        text = (self.root / "hired" / "alice.md").read_text(encoding="utf-8")
        self.assertIn("music-pay", text)
        self.assertIn("saga", text)
        # 세션은 정리되어야 함
        self.assertIsNone(session.read(self.root))

    def test_invalid_score_returns_2(self) -> None:
        session.start(self.root, "alice")
        rc = self._run_with_env(
            {
                "LSKUN_SSOT_ROOT": str(self.root),
                "LSKUN_PROJECT": "p",
                "LSKUN_TOPIC": "t",
                "LSKUN_PATTERN": "x",
                "LSKUN_FIRST_PASS": "not-a-number",
            }
        )
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
