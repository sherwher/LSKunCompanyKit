"""P52 — ADR-0006 CPO 결재 audit log 검증.

원칙:
- append-only
- schema 검증 (verdict enum / score range / required fields)
- ``.audit/`` 자동 생성
- ``request_id`` 필수
- single-line JSON only
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import LocalAdapter  # noqa: E402
from lskun_kit import audit  # noqa: E402


def _make_entry(**overrides):
    base = dict(
        request_id=audit.new_request_id(),
        company="Acme",
        worker="alice",
        domain="payments",
        model="sonnet",
        first_pass_score=82,
        rounds=1,
        verdict=audit.VERDICT_APPROVED,
        reason="요구사항 부합, 테스트 포함.",
        auto_hired=False,
    )
    base.update(overrides)
    return audit.AuditEntry(**base)


class AuditEntrySchemaTests(unittest.TestCase):
    def test_minimal_valid_entry(self) -> None:
        e = _make_entry()
        self.assertEqual(e.verdict, "approved")
        self.assertEqual(e.router, "cpo")
        self.assertIsNone(e.final_score)
        self.assertTrue(e.ts.endswith("+00:00") or "T" in e.ts)

    def test_verdict_enum_rejects_unknown(self) -> None:
        with self.assertRaises(audit.AuditError):
            _make_entry(verdict="passed")

    def test_request_id_required(self) -> None:
        with self.assertRaises(audit.AuditError):
            _make_entry(request_id="")

    def test_first_pass_score_range(self) -> None:
        for bad in (-1, 101, 200):
            with self.assertRaises(audit.AuditError):
                _make_entry(first_pass_score=bad)

    def test_final_score_range(self) -> None:
        with self.assertRaises(audit.AuditError):
            _make_entry(final_score=150)
        # None 허용
        e = _make_entry(final_score=None)
        self.assertIsNone(e.final_score)

    def test_rounds_must_be_positive(self) -> None:
        with self.assertRaises(audit.AuditError):
            _make_entry(rounds=0)

    def test_reason_must_be_non_empty(self) -> None:
        for bad in ("", "   "):
            with self.assertRaises(audit.AuditError):
                _make_entry(reason=bad)

    def test_required_strings_non_empty(self) -> None:
        for field in ("company", "worker", "domain", "model"):
            with self.assertRaises(audit.AuditError):
                _make_entry(**{field: ""})

    def test_to_json_line_is_single_line(self) -> None:
        e = _make_entry(reason="여러\n줄 사유")  # newline 이 reason 에 있어도
        line = e.to_json_line()
        self.assertNotIn("\n", line)
        # JSON 안에서는 \\n 으로 escape 됐어야
        decoded = json.loads(line)
        self.assertEqual(decoded["reason"], "여러\n줄 사유")


class AppendAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        (self.root / "hired").mkdir(parents=True)
        self.adapter = LocalAdapter(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_first_append_creates_audit_dir_and_file(self) -> None:
        self.assertFalse(self.adapter.audit_path.exists())
        e = _make_entry()
        p = audit.record(self.adapter, e)
        self.assertEqual(p, self.adapter.audit_path)
        self.assertTrue(p.exists())
        self.assertEqual(p.parent.name, ".audit")

    def test_multiple_appends_are_jsonl(self) -> None:
        e1 = _make_entry(reason="첫 번째")
        e2 = _make_entry(reason="두 번째", verdict=audit.VERDICT_REWORK, rounds=1)
        audit.record(self.adapter, e1)
        audit.record(self.adapter, e2)
        lines = self.adapter.audit_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        d1 = json.loads(lines[0])
        d2 = json.loads(lines[1])
        self.assertEqual(d1["reason"], "첫 번째")
        self.assertEqual(d2["verdict"], "rework")

    def test_append_only_preserves_existing_lines(self) -> None:
        # 직접 file 에 손으로 1줄 박아두고 record 가 append 하는지
        self.adapter.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self.adapter.audit_path.write_text(
            '{"manual": "preexisting"}\n', encoding="utf-8",
        )
        audit.record(self.adapter, _make_entry(reason="새로운 결재"))
        lines = self.adapter.audit_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("preexisting", lines[0])
        self.assertIn("새로운 결재", lines[1])

    def test_appendaudit_rejects_multiline(self) -> None:
        # adapter 단에서 직접 호출하더라도 newline 거부
        with self.assertRaises(ValueError):
            self.adapter.append_audit('{"a":1}\n{"b":2}')

    def test_verdict_rework_and_rerouted_accepted(self) -> None:
        for verdict in (audit.VERDICT_REWORK, audit.VERDICT_REROUTED,
                        audit.VERDICT_REJECTED):
            audit.record(self.adapter, _make_entry(verdict=verdict))
        lines = self.adapter.audit_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 3)


class RequestIdLinkTests(unittest.TestCase):
    def test_new_request_id_is_unique(self) -> None:
        ids = {audit.new_request_id() for _ in range(50)}
        self.assertEqual(len(ids), 50)

    # test_reflection_accepts_request_id_kwarg — ADR-0014 (2026-05-22) 폐기로 삭제


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
