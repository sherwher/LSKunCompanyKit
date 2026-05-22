"""Plugin manifest (hooks/hooks.json) 의 hook 등록 검증.

ADR-0014 (2026-05-22) 로 Reflection 메커니즘 폐기. Stop/PostToolUse hook
은 더 이상 박제되지 않는다. SessionStart + PreToolUse(Task) 만 유지.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS_JSON = ROOT / "hooks" / "hooks.json"


class HooksManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))

    def test_session_start_registered(self) -> None:
        entries = self.manifest["hooks"]["SessionStart"]
        commands = [h["command"] for e in entries for h in e["hooks"]]
        self.assertTrue(
            any("session_start.py" in c for c in commands),
            f"SessionStart command 에 session_start.py 가 없음: {commands}",
        )
        self.assertTrue(
            any("$CLAUDE_PLUGIN_ROOT" in c or "${CLAUDE_PLUGIN_ROOT}" in c for c in commands)
        )

    def test_reflection_hooks_removed(self) -> None:
        """ADR-0014 — Stop / PostToolUse hook 은 reflection 메커니즘 폐기로 제거됨."""
        self.assertNotIn("Stop", self.manifest["hooks"])
        self.assertNotIn("PostToolUse", self.manifest["hooks"])

    def test_hook_matchers_are_expected(self) -> None:
        """SessionStart 는 '*'. PreToolUse 는 'Task' 로 좁힘."""
        expected = {
            "SessionStart": "*",
            "PreToolUse": "Task",
        }
        for event, entries in self.manifest["hooks"].items():
            for e in entries:
                self.assertEqual(
                    e.get("matcher"), expected.get(event, "*"),
                    f"{event} hook matcher 불일치 (현재: {e.get('matcher')!r})",
                )

    def test_pre_tool_use_registered(self) -> None:
        """P31 — 워커 → 워커 chain 차단 hook 이 박제돼있어야 한다."""
        self.assertIn("PreToolUse", self.manifest["hooks"])
        commands = [
            h["command"]
            for e in self.manifest["hooks"]["PreToolUse"]
            for h in e["hooks"]
        ]
        self.assertTrue(any("pre_tool_use.py" in c for c in commands), commands)

    def test_all_hook_commands_use_plugin_root_placeholder(self) -> None:
        """P48 — 모든 hook 명령은 $CLAUDE_PLUGIN_ROOT 직접 경로를 사용해야 한다."""
        for event, entries in self.manifest["hooks"].items():
            for e in entries:
                for h in e["hooks"]:
                    cmd = h["command"]
                    self.assertIn(
                        "CLAUDE_PLUGIN_ROOT", cmd,
                        f"{event} hook 이 CLAUDE_PLUGIN_ROOT placeholder 미사용: {cmd!r}",
                    )
                    self.assertNotIn(
                        "python3 -m lskun_kit", cmd,
                        f"{event} hook 이 -m 모드 사용 (sys.path 깨짐): {cmd!r}",
                    )


if __name__ == "__main__":
    unittest.main()
