"""HR Lead 자동 채용 rate-limit + audit log 검증 (ADR-0004 §3, P32)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import hire_audit  # noqa: E402


class HireAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        (self.root / "hired").mkdir(parents=True)
        self.t0 = datetime(2026, 5, 18, 12, 0, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_hire_rate_limited_is_lskunkit_error(self) -> None:
        """P41 — HireRateLimited 가 LSKunKitError 를 상속한다."""
        from lskun_kit.errors import LSKunKitError
        self.assertTrue(issubclass(hire_audit.HireRateLimited, LSKunKitError))

    def test_first_hire_succeeds_and_writes_jsonl(self) -> None:
        ev = hire_audit.record_hire(
            self.root, actor="hr-lead", name="alice",
            role="backend-engineer", domain="payments", model="sonnet",
            reason="auto-hire by CPO", now=self.t0,
        )
        self.assertEqual(ev.actor, "hr-lead")
        path = hire_audit.audit_path(self.root)
        self.assertTrue(path.exists())
        line = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(line["name"], "alice")
        self.assertEqual(line["role"], "backend-engineer")

    def test_rate_limit_blocks_same_role_domain_within_cooldown(self) -> None:
        hire_audit.record_hire(
            self.root, actor="hr-lead", name="alice",
            role="backend-engineer", domain="payments", now=self.t0,
        )
        with self.assertRaises(hire_audit.HireRateLimited) as cm:
            hire_audit.record_hire(
                self.root, actor="hr-lead", name="alice-2",
                role="backend-engineer", domain="payments",
                now=self.t0 + timedelta(minutes=5),
            )
        self.assertEqual(cm.exception.role, "backend-engineer")
        self.assertEqual(cm.exception.domain, "payments")

    def test_rate_limit_does_not_block_different_role(self) -> None:
        hire_audit.record_hire(
            self.root, actor="hr-lead", name="alice",
            role="backend-engineer", domain="payments", now=self.t0,
        )
        hire_audit.record_hire(
            self.root, actor="hr-lead", name="bob",
            role="frontend-engineer", domain="payments",
            now=self.t0 + timedelta(minutes=1),
        )

    def test_rate_limit_does_not_block_different_domain(self) -> None:
        hire_audit.record_hire(
            self.root, actor="hr-lead", name="alice",
            role="backend-engineer", domain="payments", now=self.t0,
        )
        hire_audit.record_hire(
            self.root, actor="hr-lead", name="charlie",
            role="backend-engineer", domain="medical-saas",
            now=self.t0 + timedelta(minutes=1),
        )

    def test_rate_limit_expires_after_cooldown(self) -> None:
        hire_audit.record_hire(
            self.root, actor="hr-lead", name="alice",
            role="backend-engineer", domain="payments", now=self.t0,
        )
        # 31분 후 → cooldown 통과
        hire_audit.record_hire(
            self.root, actor="hr-lead", name="alice-2",
            role="backend-engineer", domain="payments",
            now=self.t0 + timedelta(minutes=31),
        )

    def test_user_actor_bypasses_rate_limit(self) -> None:
        """사용자 명시 /lskun-kit:hire 는 rate-limit 통과."""
        hire_audit.record_hire(
            self.root, actor="hr-lead", name="alice",
            role="backend-engineer", domain="payments", now=self.t0,
        )
        # 사용자가 1분 후 같은 role/domain 으로 직접 채용 → 통과
        hire_audit.record_hire(
            self.root, actor="user", name="alice-manual",
            role="backend-engineer", domain="payments",
            now=self.t0 + timedelta(minutes=1),
        )

    def test_user_event_does_not_start_cooldown_for_hr(self) -> None:
        """user 이벤트는 cooldown 산정에서 제외 — HR 의 다음 자동 채용 막지 않는다."""
        hire_audit.record_hire(
            self.root, actor="user", name="alice-manual",
            role="backend-engineer", domain="payments", now=self.t0,
        )
        # HR 가 1분 후 자동 채용 시도 → 통과 (user 이벤트는 무시)
        hire_audit.record_hire(
            self.root, actor="hr-lead", name="alice-auto",
            role="backend-engineer", domain="payments",
            now=self.t0 + timedelta(minutes=1),
        )

    def test_rate_limit_blocks_at_exact_cooldown_boundary(self) -> None:
        """P39 (#20) — `ev.at >= cutoff` 경계 검증."""
        hire_audit.record_hire(
            self.root, actor="hr-lead", name="alice",
            role="backend-engineer", domain="payments", now=self.t0,
        )
        with self.assertRaises(hire_audit.HireRateLimited):
            hire_audit.record_hire(
                self.root, actor="hr-lead", name="alice-2",
                role="backend-engineer", domain="payments",
                now=self.t0 + timedelta(seconds=hire_audit.DEFAULT_COOLDOWN_SECONDS),
            )

    def test_rate_limit_passes_one_second_after_cooldown(self) -> None:
        """경계 + 1초 → 통과."""
        hire_audit.record_hire(
            self.root, actor="hr-lead", name="alice",
            role="backend-engineer", domain="payments", now=self.t0,
        )
        hire_audit.record_hire(
            self.root, actor="hr-lead", name="alice-2",
            role="backend-engineer", domain="payments",
            now=self.t0 + timedelta(seconds=hire_audit.DEFAULT_COOLDOWN_SECONDS + 1),
        )

    def test_timestamp_regression_emits_stderr_warning(self) -> None:
        """P39 (#11) — 새 이벤트 시각이 마지막보다 과거 → stderr WARNING."""
        import io
        from unittest.mock import patch

        hire_audit.record_hire(
            self.root, actor="hr-lead", name="alice",
            role="r1", domain="d1", now=self.t0,
        )
        err = io.StringIO()
        with patch("sys.stderr", err):
            hire_audit.record_hire(
                self.root, actor="hr-lead", name="bob",
                role="r2", domain="d2",
                now=self.t0 - timedelta(hours=1),  # 과거 timestamp
            )
        self.assertIn("WARNING", err.getvalue())
        self.assertIn("timestamp regression", err.getvalue())

    def test_audit_event_generalization_round_trip(self) -> None:
        """P45 (#16) — AuditEvent 일반 스키마 와 평탄 스키마 모두 읽힌다."""
        # 평탄 스키마 (P32) 1줄 + 신규 일반화 1줄 + 손상 1줄 혼합
        path = hire_audit.audit_path(self.root)
        path.write_text(
            json.dumps({
                "at": self.t0.isoformat(), "actor": "hr-lead", "name": "old-form",
                "role": "r", "domain": "d", "model": None,
            }) + "\n"
            + json.dumps({
                "at": self.t0.isoformat(), "actor": "hr-lead",
                "event_type": "hire",
                "payload": {
                    "name": "new-form", "role": "r2", "domain": "d2",
                    "model": "sonnet", "reason": "auto",
                },
            }) + "\n"
            + json.dumps({
                "at": self.t0.isoformat(), "actor": "hr-lead",
                "event_type": "evaluate",
                "payload": {"target": "alice", "score": 88},
            }) + "\n",
            encoding="utf-8",
        )
        # read_events 는 hire 만 추려 반환 — 평탄/일반 모두 인식
        hires = hire_audit.read_events(self.root)
        names = [e.name for e in hires]
        self.assertEqual(sorted(names), ["new-form", "old-form"])
        # read_audit_events 는 모든 이벤트 (evaluate 포함)
        all_events = hire_audit.read_audit_events(self.root)
        self.assertEqual(len(all_events), 3)
        types = sorted(e.event_type for e in all_events)
        self.assertEqual(types, ["evaluate", "hire", "hire"])

    def test_hire_event_to_audit_event(self) -> None:
        ev = hire_audit.HireEvent(
            at=self.t0, actor="hr-lead", name="alice", role="r", domain="d",
            model="sonnet", reason="x",
        )
        audit = ev.to_audit_event()
        self.assertEqual(audit.event_type, "hire")
        self.assertEqual(audit.payload["name"], "alice")
        self.assertEqual(audit.payload["reason"], "x")

    def test_read_events_skips_corrupt_lines(self) -> None:
        path = hire_audit.audit_path(self.root)
        path.write_text(
            "not-json\n"
            + json.dumps({
                "at": self.t0.isoformat(), "actor": "hr-lead", "name": "ok",
                "role": "r", "domain": "d", "model": None,
            })
            + "\n",
            encoding="utf-8",
        )
        events = hire_audit.read_events(self.root)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].name, "ok")


if __name__ == "__main__":
    unittest.main()
