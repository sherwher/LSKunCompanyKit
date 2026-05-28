"""ADR-0021 — Worker.kind OPTIONAL 필드 테스트."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import models  # noqa: E402,F401
from lskun_kit.models import (  # noqa: E402
    OPTIONAL_WORKER_FIELDS,
    REQUIRED_WORKER_FIELDS,
    Worker,
)


class WorkerKindTest(unittest.TestCase):
    def test_kind_not_in_required(self):
        # 기존 워커 호환 — kind 는 절대 필수가 아니다.
        self.assertNotIn("kind", REQUIRED_WORKER_FIELDS)

    def test_kind_in_optional(self):
        self.assertIn("kind", OPTIONAL_WORKER_FIELDS)

    def test_worker_default_kind_none(self):
        w = Worker(
            name="backend-engineer", role="backend-engineer", domain="medical",
            hired_at=date(2026, 5, 28), storage_backend="local",
            display_name="김백엔드",
        )
        self.assertIsNone(w.kind)

    def test_worker_with_kind(self):
        w = Worker(
            name="competitor-analyst", role="competitor-analyst", domain="medical",
            hired_at=date(2026, 5, 28), storage_backend="local",
            display_name="경쟁분석", kind="redteam",
        )
        self.assertEqual(w.kind, "redteam")


if __name__ == "__main__":
    unittest.main()
