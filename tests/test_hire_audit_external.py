"""ADR-0021 — 외주 박제 audit (rate-limit 우회) 테스트."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import hire_audit  # noqa: E402


class RecordExternalOnboardTest(unittest.TestCase):
    def _audit_path(self, tmp):
        d = Path(tmp) / ".audit"
        d.mkdir(parents=True)
        return d / "decisions.jsonl"

    def test_records_event_type_onboard_external(self):
        with tempfile.TemporaryDirectory() as tmp:
            ap = self._audit_path(tmp)
            hire_audit.record_external_onboard(
                ap, actor="hr-lead", name="competitor-analyst",
                kind="redteam", project="proj",
                at=datetime(2026, 5, 28, tzinfo=timezone.utc),
            )
            content = ap.read_text()
            self.assertIn("onboard_external", content)
            self.assertIn("competitor-analyst", content)
            self.assertIn("redteam", content)

    def test_multiple_customers_same_role_no_ratelimit(self):
        with tempfile.TemporaryDirectory() as tmp:
            ap = self._audit_path(tmp)
            for n in ("power-user", "price-sensitive", "newbie", "poweruser2", "casual"):
                hire_audit.record_external_onboard(
                    ap, actor="hr-lead", name=n,
                    kind="customer", project="proj",
                    at=datetime(2026, 5, 28, tzinfo=timezone.utc),
                )
            lines = [l for l in ap.read_text().splitlines() if l.strip()]
            self.assertEqual(len(lines), 5)


if __name__ == "__main__":
    unittest.main()
