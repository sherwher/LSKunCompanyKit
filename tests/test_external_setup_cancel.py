"""ADR-0022 — external setup cancel 테스트 (P121 Task 8).

cancel 은 사용자 명시 중단. marker unlink 만 담당 (audit entry 박제는
commands/external.md 가 호출). finalize 와 의미 구분: finalize = 정상 완료,
cancel = 사용자 중단.

mocking 패턴은 실증된 test_external_setup_state.py 와 일치.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import external_setup_state as state  # noqa: E402
from lskun_kit import paths  # noqa: E402


def _patch_home(tmp: str):
    return mock.patch.object(Path, "home", return_value=Path(tmp))


class CancelTest(unittest.TestCase):
    def test_cancel_unlinks_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, _patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            state.start("Acme", "proj")
            self.assertTrue(state.marker_path("Acme").exists())
            state.cancel("Acme")
            self.assertFalse(state.marker_path("Acme").exists())

    def test_cancel_no_marker_no_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, _patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            state.cancel("Acme")  # no-op, no exception

    def test_cancel_validates_company_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, _patch_home(tmp):
            with self.assertRaises(ValueError):
                state.cancel("..")  # path traversal 차단

    def test_cancel_then_start_again(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, _patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            state.start("Acme", "proj")
            state.cancel("Acme")
            # cancel 후 새 setup 즉시 가능 (marker 정리됨).
            s = state.start("Acme", "proj2")
            self.assertEqual(s.project, "proj2")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
