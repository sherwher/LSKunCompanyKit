"""lskun_kit.permissions 단위 테스트 — ADR-0015 결정 4.

테스트 격리: ``settings_path`` 인자로 tempdir 사용. ``Path.home()`` mock 도
일부 시나리오에서 사용. 사용자 실제 ``~/.claude/settings.json`` 오염 0.
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

from lskun_kit import permissions  # noqa: E402
from lskun_kit.errors import ConfirmRequired  # noqa: E402


class PatternsForPathTests(unittest.TestCase):
    """ADR-0015 결정 4-A — 5개 패턴 + 절대경로 변환."""

    def test_returns_five_patterns(self) -> None:
        ps = permissions.patterns_for_path("/abs/root/LSKun")
        self.assertEqual(len(ps), 5)

    def test_patterns_contain_read_edit_write_bash(self) -> None:
        ps = permissions.patterns_for_path("/abs/root/LSKun")
        kinds = [p.split("(", 1)[0] for p in ps]
        self.assertEqual(kinds, ["Read", "Edit", "Write", "Bash", "Bash"])

    def test_tilde_expanded_to_absolute(self) -> None:
        """ADR-0015 결정 4-A — settings.json 에 절대경로 박제."""
        ps = permissions.patterns_for_path("~/.lskun-companies/LSKun")
        for p in ps:
            self.assertNotIn("~", p)
            # Path.home() 의 절대경로가 포함되어야 함
            self.assertIn(str(Path.home()), p)

    def test_bash_ls_pattern_uses_glob_star(self) -> None:
        """ADR-0015 결정 4-A 의 정확한 ``Bash(ls <root>*)`` 형식."""
        ps = permissions.patterns_for_path("/abs/LSKun")
        bash_ls = [p for p in ps if p.startswith("Bash(ls ")]
        self.assertEqual(len(bash_ls), 1)
        self.assertEqual(bash_ls[0], "Bash(ls /abs/LSKun*)")


class EnsureForPathRequiresConfirmTests(unittest.TestCase):
    def test_raises_confirm_required_when_missing_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / "settings.json"
            with self.assertRaises(ConfirmRequired) as ctx:
                permissions.ensure_for_path(
                    Path(tmp) / "LSKun", settings_path=settings,
                )
            err = ctx.exception
            self.assertEqual(err.kind, "permissions")
            self.assertIn("settings.json", err.prompt)
            self.assertIn("[y/N]", err.prompt)
            self.assertEqual(err.context.get("settings_path"), str(settings))
            self.assertEqual(len(err.context.get("patterns", [])), 5)


class EnsureForPathCreatesNewSettingsTests(unittest.TestCase):
    def test_creates_settings_json_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / "missing-subdir" / "settings.json"
            result = permissions.ensure_for_path(
                "/abs/LSKun", confirmed=True, settings_path=settings,
            )
            self.assertEqual(result.action, "created")
            self.assertTrue(settings.exists())
            data = json.loads(settings.read_text(encoding="utf-8"))
            self.assertIn("permissions", data)
            allow = data["permissions"]["allow"]
            self.assertEqual(len(allow), 5)
            self.assertIn("Read(/abs/LSKun/**)", allow)


class EnsureForPathAddsToExistingTests(unittest.TestCase):
    def test_preserves_existing_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / "settings.json"
            existing = {
                "env": {"FOO": "bar"},
                "permissions": {
                    "allow": ["Bash(npm run *)", "Bash(yarn *)"],
                    "deny": ["Bash(rm -rf /)"],
                },
            }
            settings.write_text(
                json.dumps(existing, indent=2), encoding="utf-8"
            )

            result = permissions.ensure_for_path(
                "/abs/LSKun", confirmed=True, settings_path=settings,
            )
            self.assertEqual(result.action, "added")
            self.assertEqual(len(result.added_patterns), 5)

            data = json.loads(settings.read_text(encoding="utf-8"))
            # 기존 보존
            self.assertEqual(data["env"]["FOO"], "bar")
            self.assertEqual(data["permissions"]["deny"], ["Bash(rm -rf /)"])
            # 기존 + 신규 = 2 + 5 = 7
            allow = data["permissions"]["allow"]
            self.assertEqual(len(allow), 7)
            self.assertIn("Bash(npm run *)", allow)
            self.assertIn("Read(/abs/LSKun/**)", allow)


class EnsureForPathIdempotentTests(unittest.TestCase):
    def test_unchanged_when_all_patterns_already_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / "settings.json"
            # 1차 박제
            permissions.ensure_for_path(
                "/abs/LSKun", confirmed=True, settings_path=settings,
            )
            # 2차 (멱등) — confirmed=False 여도 ConfirmRequired 안 남
            result = permissions.ensure_for_path(
                "/abs/LSKun", settings_path=settings,
            )
            self.assertEqual(result.action, "unchanged")
            self.assertEqual(result.added_patterns, [])
            self.assertEqual(len(result.already_present), 5)

    def test_partial_present_only_adds_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / "settings.json"
            existing = {
                "permissions": {
                    "allow": ["Read(/abs/LSKun/**)", "Edit(/abs/LSKun/**)"],
                },
            }
            settings.write_text(json.dumps(existing), encoding="utf-8")
            result = permissions.ensure_for_path(
                "/abs/LSKun", confirmed=True, settings_path=settings,
            )
            self.assertEqual(result.action, "added")
            self.assertEqual(len(result.added_patterns), 3)  # Write/Bash/Bash
            self.assertEqual(len(result.already_present), 2)


class EnsureForPathRejectsCorruptedTests(unittest.TestCase):
    def test_rejects_broken_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / "settings.json"
            settings.write_text("not json at all {", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                permissions.ensure_for_path(
                    "/abs/LSKun", confirmed=True, settings_path=settings,
                )
            self.assertIn("parse failed", str(ctx.exception))

    def test_rejects_non_object_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / "settings.json"
            settings.write_text("[1,2,3]", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                permissions.ensure_for_path(
                    "/abs/LSKun", confirmed=True, settings_path=settings,
                )
            self.assertIn("not a JSON object", str(ctx.exception))

    def test_rejects_non_list_allow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = Path(tmp) / "settings.json"
            settings.write_text(
                json.dumps({"permissions": {"allow": "not-a-list"}}),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError) as ctx:
                permissions.ensure_for_path(
                    "/abs/LSKun", confirmed=True, settings_path=settings,
                )
            self.assertIn("permissions.allow", str(ctx.exception))
            self.assertIn("list", str(ctx.exception))


class GlobalSettingsPathTests(unittest.TestCase):
    def test_under_home_dot_claude(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home:
            with mock.patch("lskun_kit.permissions.Path.home",
                            return_value=Path(fake_home)):
                p = permissions.global_settings_path()
                self.assertEqual(
                    p, Path(fake_home) / ".claude" / "settings.json"
                )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
