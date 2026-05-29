"""ADR-0022 — sync 시 ``.external-setup.json`` 가드 (security C1).

외부 mirror 의 marker 가 sync-in 으로 회사 SSOT 에 복사되면 hook 이 읽는다.
marker schema 의 enum allowlist (external_setup_state.read) 가 raw 인젝션을
1차 차단하지만, 사용자가 marker 의 존재 자체를 인지하도록 sync 결과 notes 에
경고를 박는다 (인지 = C1 완화의 마지막 갈래).

mocking 패턴은 실증된 test_sync.py 와 일치
(``mock.patch("lskun_kit.paths.Path.home")`` + ``today_stamp`` 주입).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import sync  # noqa: E402
from lskun_kit.paths import company_root  # noqa: E402


def _patched_home(fake_home: str):
    return mock.patch("lskun_kit.paths.Path.home", return_value=Path(fake_home))


def _company_files(root: Path, with_marker: bool = False) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "company.md").write_text("---\nname: Acme\n---\n# Acme\n", encoding="utf-8")
    if with_marker:
        (root / sync.EXTERNAL_MARKER_NAME).write_text(json.dumps({
            "started_at": "2026-05-28T14:00:00+00:00",
            "company": "Acme", "project": "evil",
            "current_step": "init", "next_action": "domain_assessment",
            "step_count_so_far": 1, "max_step_count": 10,
        }), encoding="utf-8")


class SyncScanHelperTest(unittest.TestCase):
    """``_scan_external_markers`` 는 root 의 marker 상대경로를 노트로 반환."""

    def test_no_marker_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "src"
            _company_files(root, with_marker=False)
            self.assertEqual(sync._scan_external_markers(root), [])

    def test_marker_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "src"
            _company_files(root, with_marker=True)
            notes = sync._scan_external_markers(root)
            self.assertEqual(len(notes), 1)
            self.assertIn(sync.EXTERNAL_MARKER_NAME, notes[0])


class SyncInMarkerGuardTest(unittest.TestCase):
    """sync-in 결과 notes 에 marker 경고가 포함된다 (security C1)."""

    def test_sync_in_warns_on_external_marker(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as vault, _patched_home(fake_home):
            src = Path(vault) / "Acme"
            _company_files(src, with_marker=True)
            result = sync.sync_in(
                "Acme", src, confirmed=True, today_stamp="20260528-140000",
            )
            joined = "\n".join(result.notes)
            self.assertIn(sync.EXTERNAL_MARKER_NAME, joined)
            self.assertIn("ADR-0022", joined)

    def test_sync_in_clean_no_marker_note(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as vault, _patched_home(fake_home):
            src = Path(vault) / "Acme"
            _company_files(src, with_marker=False)
            result = sync.sync_in(
                "Acme", src, confirmed=True, today_stamp="20260528-140000",
            )
            joined = "\n".join(result.notes)
            self.assertNotIn(sync.EXTERNAL_MARKER_NAME, joined)


class SyncOutMarkerGuardTest(unittest.TestCase):
    """sync-out 도 로컬 SSOT 의 marker 를 외부로 내보낼 때 경고."""

    def test_sync_out_warns_on_external_marker(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, \
             tempfile.TemporaryDirectory() as vault, _patched_home(fake_home):
            _company_files(company_root("Acme"), with_marker=True)
            tgt = Path(vault) / "Acme-mirror"
            result = sync.sync_out(
                "Acme", tgt, confirmed=True, today_stamp="20260528-140000",
            )
            joined = "\n".join(result.notes)
            self.assertIn(sync.EXTERNAL_MARKER_NAME, joined)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
