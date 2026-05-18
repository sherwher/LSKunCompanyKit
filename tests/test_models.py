"""lskun_kit.models 단위 테스트 — ADR-0004 §4 모델 라우팅 helper."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit.models import (  # noqa: E402
    DEFAULT_WORKER_MODEL,
    MODEL_ALIASES,
    META_DOMAIN,
    OPTIONAL_WORKER_FIELDS,
    REQUIRED_WORKER_FIELDS,
    resolve_model,
)


class FrontmatterFieldConstantsTests(unittest.TestCase):
    def test_required_fields_are_six(self) -> None:
        # ADR-0004 §6
        self.assertEqual(len(REQUIRED_WORKER_FIELDS), 6)
        self.assertIn("display_name", REQUIRED_WORKER_FIELDS)

    def test_optional_fields_contain_model(self) -> None:
        self.assertIn("model", OPTIONAL_WORKER_FIELDS)

    def test_meta_domain_is_string(self) -> None:
        self.assertEqual(META_DOMAIN, "meta")


class ResolveModelTests(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(resolve_model(None))

    def test_aliases_resolve_to_ids(self) -> None:
        self.assertEqual(resolve_model("sonnet"), "claude-sonnet-4-6")
        self.assertEqual(resolve_model("opus"), "claude-opus-4-7")
        self.assertEqual(resolve_model("haiku"), "claude-haiku-4-5-20251001")

    def test_unknown_alias_returned_as_is(self) -> None:
        # 모델 ID 직접 입력 허용 — alias 사전에 없으면 그대로 반환
        self.assertEqual(resolve_model("claude-opus-4-7"), "claude-opus-4-7")
        self.assertEqual(resolve_model("custom-model-id"), "custom-model-id")

    def test_default_model_is_known_alias(self) -> None:
        self.assertIn(DEFAULT_WORKER_MODEL, MODEL_ALIASES)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
