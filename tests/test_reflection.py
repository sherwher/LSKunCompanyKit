"""Reflection 자동화 — session / context / reflection.record 테스트."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import HistoryEntry, LocalAdapter  # noqa: E402
from lskun_kit import context, reflection, session  # noqa: E402


WORKER_MD = dedent(
    """\
    ---
    name: alice
    role: backend-engineer
    domain: payments
    hired_at: 2026-05-15
    storage_backend: local
    display_name: Alice Park
    ---

    # alice

    ## Project History

    - 2026-05-10 / payment-svc / idempotency / stripe-key-as-idem / first-pass 92%
    - 2026-05-12 / music-pay / webhook / signature-verify / first-pass 85%
    """
)


def _setup_local(tmp: Path) -> tuple[Path, LocalAdapter]:
    root = tmp / ".company"
    (root / "hired").mkdir(parents=True)
    (root / "hired" / "alice.md").write_text(WORKER_MD, encoding="utf-8")
    return root, LocalAdapter(root)


class SessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        self.root.mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_start_creates_session_file(self) -> None:
        sess = session.start(self.root, "alice")
        self.assertEqual(sess.active_worker, "alice")
        self.assertTrue(session.session_path(self.root).exists())

    def test_read_roundtrip(self) -> None:
        session.start(self.root, "alice")
        again = session.read(self.root)
        self.assertIsNotNone(again)
        assert again is not None
        self.assertEqual(again.active_worker, "alice")

    def test_read_missing_returns_none(self) -> None:
        self.assertIsNone(session.read(self.root))

    def test_read_malformed_returns_none(self) -> None:
        session.session_path(self.root).write_text("{not json", encoding="utf-8")
        self.assertIsNone(session.read(self.root))

    def test_clear_removes_file(self) -> None:
        session.start(self.root, "alice")
        session.clear(self.root)
        self.assertFalse(session.session_path(self.root).exists())

    def test_clear_missing_is_safe(self) -> None:
        session.clear(self.root)  # 예외 없어야 함

    def test_lock_file_created_alongside_session(self) -> None:
        """P44 (#6) — file lock 파일이 세션과 같은 디렉토리에 생성된다."""
        session.start(self.root, "alice")
        from lskun_kit.session import lock_path
        # POSIX 환경에서만 lock 파일이 생성된다.
        from lskun_kit.session import _HAS_FLOCK
        if _HAS_FLOCK:
            self.assertTrue(lock_path(self.root).exists())

    def test_read_returns_none_and_clears_stale_session(self) -> None:
        """P38 — TTL 초과 세션은 stale 로 보고 None 반환 + 파일 삭제."""
        from datetime import datetime, timedelta, timezone
        session.start(self.root, "alice")
        future = datetime.now(timezone.utc) + timedelta(hours=25)
        result = session.read(self.root, now=future)
        self.assertIsNone(result)
        self.assertFalse(session.session_path(self.root).exists())

    def test_fresh_session_within_ttl_returned(self) -> None:
        """TTL 안의 세션은 정상 반환."""
        from datetime import datetime, timedelta, timezone
        session.start(self.root, "alice")
        future = datetime.now(timezone.utc) + timedelta(hours=23)
        result = session.read(self.root, now=future)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.active_worker, "alice")


class ContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root, self.adapter = _setup_local(Path(self.tmp.name))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_includes_header_and_recent_history(self) -> None:
        ctx = context.build_worker_context(self.adapter, "alice")
        self.assertIn("Worker: alice (backend-engineer)", ctx)
        self.assertIn("Backend: local", ctx)
        self.assertIn("stripe-key-as-idem", ctx)
        self.assertIn("signature-verify", ctx)

    def test_limits_to_recent_n(self) -> None:
        # 10줄 추가
        for i in range(12):
            self.adapter.append_history(
                "alice",
                HistoryEntry(date(2026, 5, 15), f"proj{i}", "topic", "pattern", 50),
            )
        ctx = context.build_worker_context(self.adapter, "alice", recent=5)
        self.assertEqual(ctx.count("- 2026-"), 5)

    def test_empty_history_message(self) -> None:
        blank = dedent(
            """\
            ---
            name: bob
            role: pm
            domain: meta
            hired_at: 2026-05-15
            storage_backend: local
            display_name: Bob Lee
            ---

            # bob
            """
        )
        (self.root / "hired" / "bob.md").write_text(blank, encoding="utf-8")
        ctx = context.build_worker_context(self.adapter, "bob")
        self.assertIn("no history yet", ctx)


class ReflectionRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root, self.adapter = _setup_local(Path(self.tmp.name))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_record_appends_line(self) -> None:
        entry = reflection.record(
            self.adapter, "alice", "music-pay", "refund-flow", "saga", 88,
            when=date(2026, 5, 15),
        )
        text = (self.root / "hired" / "alice.md").read_text(encoding="utf-8")
        self.assertIn(entry.render(), text)

    def test_record_rejects_slash_in_field(self) -> None:
        with self.assertRaises(ValueError):
            reflection.record(self.adapter, "alice", "a/b", "x", "y", 50)
        with self.assertRaises(ValueError):
            reflection.record(self.adapter, "alice", "p", "t", "pat/tern", 50)

    def test_record_rejects_empty_field(self) -> None:
        with self.assertRaises(ValueError):
            reflection.record(self.adapter, "alice", "", "t", "p", 50)

    def test_record_rejects_score_out_of_range(self) -> None:
        for bad in (-1, 101, 200):
            with self.assertRaises(ValueError):
                reflection.record(self.adapter, "alice", "p", "t", "x", bad)

    def test_reflection_skipped_is_lskunkit_error(self) -> None:
        """P41 — ReflectionSkipped 가 LSKunKitError 를 상속해 일괄 catch 가능."""
        from lskun_kit.errors import LSKunKitError
        self.assertTrue(issubclass(reflection.ReflectionSkipped, LSKunKitError))
        with self.assertRaises(LSKunKitError):
            reflection.record(
                self.adapter, "alice", "p", "t", "x", 100,
                outcome=reflection.OUTCOME_ABORTED,
            )

    def test_outcome_aborted_skips_history(self) -> None:
        """P30 — outcome=aborted 면 history 박제 skip + ReflectionSkipped raise."""
        before = (self.root / "hired" / "alice.md").read_text(encoding="utf-8")
        with self.assertRaises(reflection.ReflectionSkipped):
            reflection.record(
                self.adapter, "alice", "p", "t", "x", 100,
                outcome=reflection.OUTCOME_ABORTED,
            )
        after = (self.root / "hired" / "alice.md").read_text(encoding="utf-8")
        self.assertEqual(before, after, "aborted outcome 은 파일을 변경하지 않아야 한다")

    def test_outcome_invalid_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            reflection.record(
                self.adapter, "alice", "p", "t", "x", 50, outcome="maybe",
            )

    def test_outcome_success_default_appends(self) -> None:
        """default outcome 은 'success' — 기존 동작 보존."""
        reflection.record(
            self.adapter, "alice", "proj-x", "topic-x", "pattern-x", 70,
            when=date(2026, 5, 18),
        )
        text = (self.root / "hired" / "alice.md").read_text(encoding="utf-8")
        self.assertIn("proj-x", text)


if __name__ == "__main__":
    unittest.main()
