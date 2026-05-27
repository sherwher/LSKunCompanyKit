"""P109-A — audit_view 단위 테스트.

원칙:
- read-only (audit 파일 수정 X)
- best-effort (불량 라인 1개로 전체 fail X)
- JSONL + gzip 동시 지원
"""

from __future__ import annotations

import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit.audit_view import WorkerUsage, read_usage  # noqa: E402


def _make_entry(worker: str, ts: str, **kwargs) -> str:
    """audit JSONL 1줄 (schema 검증 우회, view 는 read-only 라 schema 강제 안 함)."""
    data = {"worker": worker, "ts": ts}
    data.update(kwargs)
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


class ReadUsageTests(unittest.TestCase):
    """audit_view.read_usage 의 핵심 8 케이스."""

    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.audit_dir = Path(self._td.name) / ".audit"
        self.audit_dir.mkdir()

    def tearDown(self) -> None:
        self._td.cleanup()

    def _write_current(self, lines: list[str]) -> None:
        (self.audit_dir / "decisions.jsonl").write_text(
            "\n".join(lines) + "\n" if lines else "", encoding="utf-8"
        )

    def _write_rotated(self, month: str, lines: list[str]) -> None:
        path = self.audit_dir / f"decisions.{month}.jsonl.gz"
        body = ("\n".join(lines) + "\n").encode("utf-8") if lines else b""
        with gzip.open(path, "wb") as f:
            f.write(body)

    # 1
    def test_single_entry_single_worker(self) -> None:
        self._write_current([_make_entry("alice", "2026-05-27T10:00:00+00:00")])
        usage = read_usage(self.audit_dir)
        self.assertEqual(usage["alice"], WorkerUsage("alice", 1, "2026-05-27T10:00:00+00:00"))

    # 2
    def test_same_worker_aggregates_count_and_max_ts(self) -> None:
        self._write_current([
            _make_entry("alice", "2026-05-01T10:00:00+00:00"),
            _make_entry("alice", "2026-05-15T10:00:00+00:00"),
            _make_entry("alice", "2026-05-03T10:00:00+00:00"),
        ])
        usage = read_usage(self.audit_dir)
        self.assertEqual(usage["alice"].dispatches, 3)
        self.assertEqual(usage["alice"].last_seen, "2026-05-15T10:00:00+00:00")

    # 3
    def test_best_effort_skips_malformed_lines(self) -> None:
        self._write_current([
            _make_entry("alice", "2026-05-27T10:00:00+00:00"),
            "{not json",
            "",
            _make_entry("bob", "2026-05-27T11:00:00+00:00"),
        ])
        usage = read_usage(self.audit_dir)
        self.assertIn("alice", usage)
        self.assertIn("bob", usage)
        self.assertEqual(usage["alice"].dispatches, 1)
        self.assertEqual(usage["bob"].dispatches, 1)

    # 4
    def test_audit_dir_missing_returns_empty(self) -> None:
        usage = read_usage(self.audit_dir.parent / "nonexistent")
        self.assertEqual(usage, {})

    # 5
    def test_reads_both_current_and_rotated_gz(self) -> None:
        self._write_current([_make_entry("alice", "2026-05-27T10:00:00+00:00")])
        self._write_rotated("2026-04", [
            _make_entry("alice", "2026-04-15T10:00:00+00:00"),
            _make_entry("bob", "2026-04-20T10:00:00+00:00"),
        ])
        usage = read_usage(self.audit_dir)
        self.assertEqual(usage["alice"].dispatches, 2)
        self.assertEqual(usage["alice"].last_seen, "2026-05-27T10:00:00+00:00")
        self.assertEqual(usage["bob"].dispatches, 1)
        self.assertEqual(usage["bob"].last_seen, "2026-04-20T10:00:00+00:00")

    # 6
    def test_missing_worker_field_is_skipped(self) -> None:
        self._write_current([
            json.dumps({"ts": "2026-05-27T10:00:00+00:00"}),
            _make_entry("alice", "2026-05-27T10:00:00+00:00"),
        ])
        usage = read_usage(self.audit_dir)
        self.assertEqual(list(usage.keys()), ["alice"])

    # 7
    def test_missing_ts_counts_but_does_not_update_last_seen(self) -> None:
        self._write_current([
            json.dumps({"worker": "alice"}),  # ts 부재
            _make_entry("alice", "2026-05-27T10:00:00+00:00"),
        ])
        usage = read_usage(self.audit_dir)
        self.assertEqual(usage["alice"].dispatches, 2)
        self.assertEqual(usage["alice"].last_seen, "2026-05-27T10:00:00+00:00")

    # 8
    def test_non_dict_json_lines_are_skipped(self) -> None:
        """audit 가 list / scalar JSON 인 라인은 무시."""
        self._write_current([
            "[1, 2, 3]",
            '"just a string"',
            _make_entry("alice", "2026-05-27T10:00:00+00:00"),
        ])
        usage = read_usage(self.audit_dir)
        self.assertEqual(list(usage.keys()), ["alice"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
