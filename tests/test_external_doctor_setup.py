"""ADR-0022 — doctor [33] stale marker + [34] env export 진단 테스트 (P121).

mocking 패턴은 실증된 test_hooks_post_tool_use_external.py 와 일치
(``mock.patch.object(Path, "home")`` — pathlib 직접 patch 로 company_root /
env 파일 home 참조 모두 커버).
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import external_diagnostics  # noqa: E402
from lskun_kit import external_setup_state as state  # noqa: E402
from lskun_kit import paths  # noqa: E402


def _patch_home(tmp: str):
    return mock.patch.object(Path, "home", return_value=Path(tmp))


class StaleMarkerDetectionTest(unittest.TestCase):
    def test_no_marker_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, _patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            findings = external_diagnostics.diagnose_external_setup("Acme")
            self.assertEqual(findings.issues, [])

    def test_fresh_marker_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, _patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            state.start("Acme", "proj")
            findings = external_diagnostics.diagnose_external_setup("Acme")
            self.assertEqual(findings.issues, [])  # 살아있는 marker = OK

    def test_stale_marker_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, _patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            marker = state.marker_path("Acme")
            old = datetime.now(timezone.utc) - timedelta(hours=30)
            marker.write_text(json.dumps({
                "started_at": old.isoformat(),
                "company": "Acme", "project": "p",
                "current_step": "init", "next_action": "domain_assessment",
                "step_count_so_far": 1, "max_step_count": 10,
            }), encoding="utf-8")
            findings = external_diagnostics.diagnose_external_setup("Acme")
            self.assertTrue(any("stale" in i.lower() or "오래" in i
                                for i in findings.issues))

    def test_malformed_marker_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, _patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            state.marker_path("Acme").write_text("not json {", encoding="utf-8")
            findings = external_diagnostics.diagnose_external_setup("Acme")
            self.assertTrue(findings.issues)  # 손상 → 1개 이상 issue


class EnvGrepTest(unittest.TestCase):
    def test_no_env_files_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, _patch_home(tmp):
            findings = external_diagnostics.diagnose_external_env_export()
            self.assertEqual(findings.issues, [])

    def test_zshrc_with_halt_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, _patch_home(tmp):
            (Path(tmp) / ".zshrc").write_text(
                "export LSKUN_ALLOW_EXTERNAL_HALT=1\n", encoding="utf-8"
            )
            findings = external_diagnostics.diagnose_external_env_export()
            self.assertTrue(any("LSKUN_ALLOW_EXTERNAL_HALT" in i
                                for i in findings.issues))

    def test_unrelated_zshrc_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, _patch_home(tmp):
            (Path(tmp) / ".zshrc").write_text(
                "export PATH=/usr/local/bin:$PATH\n", encoding="utf-8"
            )
            findings = external_diagnostics.diagnose_external_env_export()
            self.assertEqual(findings.issues, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
