"""P109-B — audit_rotate 단위 테스트.

원칙:
- 사용자 명시 명령만, 자동 호출 없음
- atomic-ish (gzip write → 원본 truncate)
- idempotent (기존 회전 파일에 append, 옛 데이터 손실 0)
- best-effort (malformed 라인은 현재 월에 잔존)
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

from lskun_kit.audit_rotate import (  # noqa: E402
    AuditRotateError,
    plan_rotation,
    execute_rotation,
)


def _entry(worker: str, ts: str) -> str:
    return json.dumps({"worker": worker, "ts": ts}, ensure_ascii=False, separators=(",", ":"))


class RotationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.audit_dir = Path(self._td.name) / ".audit"
        self.audit_dir.mkdir()
        self.current = self.audit_dir / "decisions.jsonl"

    def tearDown(self) -> None:
        self._td.cleanup()

    def _write(self, lines: list[str]) -> None:
        self.current.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")

    # 1
    def test_single_month_is_no_op(self) -> None:
        self._write([
            _entry("alice", "2026-05-01T10:00:00+00:00"),
            _entry("bob", "2026-05-15T10:00:00+00:00"),
        ])
        plan = plan_rotation(self.audit_dir, now_month="2026-05")
        self.assertTrue(plan.is_no_op)
        execute_rotation(plan)
        # 원본 변경 없음 — 2줄 그대로
        self.assertEqual(
            len([ln for ln in self.current.read_text(encoding="utf-8").splitlines() if ln.strip()]),
            2,
        )

    # 2
    def test_multi_month_splits_into_gz_buckets(self) -> None:
        self._write([
            _entry("alice", "2026-03-15T10:00:00+00:00"),  # 옛 월
            _entry("bob", "2026-04-10T10:00:00+00:00"),    # 옛 월
            _entry("carol", "2026-04-22T10:00:00+00:00"),  # 옛 월
            _entry("dave", "2026-05-27T10:00:00+00:00"),   # 현재 월
        ])
        plan = plan_rotation(self.audit_dir, now_month="2026-05")
        self.assertEqual(len(plan.rotate_buckets), 2)  # 2026-03 + 2026-04
        self.assertEqual(len(plan.current_lines), 1)
        execute_rotation(plan)
        # gzip 2개 생성
        gz_march = self.audit_dir / "decisions.2026-03.jsonl.gz"
        gz_april = self.audit_dir / "decisions.2026-04.jsonl.gz"
        self.assertTrue(gz_march.exists())
        self.assertTrue(gz_april.exists())
        # gz 내용 검증
        with gzip.open(gz_april, "rt", encoding="utf-8") as f:
            april_lines = [ln for ln in f if ln.strip()]
        self.assertEqual(len(april_lines), 2)

    # 3
    def test_current_month_preserved_in_jsonl(self) -> None:
        self._write([
            _entry("alice", "2026-03-15T10:00:00+00:00"),
            _entry("bob", "2026-05-27T10:00:00+00:00"),
        ])
        execute_rotation(plan_rotation(self.audit_dir, now_month="2026-05"))
        remaining = [ln for ln in self.current.read_text(encoding="utf-8").splitlines() if ln.strip()]
        self.assertEqual(len(remaining), 1)
        self.assertIn("bob", remaining[0])
        self.assertNotIn("alice", remaining[0])

    # 4
    def test_idempotent_replay(self) -> None:
        """이미 회전된 .gz 가 있을 때 같은 월 entry 가 더 와도 append (덮어쓰기 X)."""
        self._write([_entry("alice", "2026-03-15T10:00:00+00:00")])
        execute_rotation(plan_rotation(self.audit_dir, now_month="2026-05"))
        # 두 번째 실행: 또 다른 2026-03 entry 가 추가됐다고 가정
        self._write([_entry("bob", "2026-03-20T10:00:00+00:00")])
        execute_rotation(plan_rotation(self.audit_dir, now_month="2026-05"))
        gz = self.audit_dir / "decisions.2026-03.jsonl.gz"
        with gzip.open(gz, "rt", encoding="utf-8") as f:
            lines = [ln for ln in f if ln.strip()]
        # 두 entry 모두 보존 — idempotent merge
        self.assertEqual(len(lines), 2)

    # 5
    def test_audit_file_missing_returns_noop(self) -> None:
        plan = plan_rotation(self.audit_dir, now_month="2026-05")
        self.assertTrue(plan.is_no_op)
        self.assertEqual(plan.current_lines, [])

    # 6
    def test_malformed_lines_stay_in_current(self) -> None:
        """parse 실패 라인은 회전하지 않고 현재 월에 잔존 (사용자 수동 정리)."""
        self._write([
            _entry("alice", "2026-03-15T10:00:00+00:00"),
            "{not json",
            "{}",  # ts 부재
            _entry("bob", "2026-05-27T10:00:00+00:00"),
        ])
        plan = plan_rotation(self.audit_dir, now_month="2026-05")
        self.assertEqual(plan.malformed_count, 2)
        execute_rotation(plan)
        remaining = [ln for ln in self.current.read_text(encoding="utf-8").splitlines() if ln.strip()]
        # bob (현재 월) + malformed 2건 = 3건
        self.assertEqual(len(remaining), 3)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
