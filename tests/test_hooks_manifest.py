"""Plugin manifest (hooks/hooks.json) 의 hook 등록 검증.

ADR-0001 §3 — Reflection 은 default-on 이어야 한다. Stop hook 이 plugin 자체에
박제되어 있어야 사용자가 별도 settings.json 작업 없이 동작한다.
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
        # P48 — $CLAUDE_PLUGIN_ROOT 직접 경로 호출. module 이름 / 명령 형식 검증.
        self.assertTrue(
            any("session_start.py" in c for c in commands),
            f"SessionStart command 에 session_start.py 가 없음: {commands}",
        )
        # plugin root placeholder 사용 여부
        self.assertTrue(any("$CLAUDE_PLUGIN_ROOT" in c or "${CLAUDE_PLUGIN_ROOT}" in c for c in commands))

    def test_stop_hook_registered(self) -> None:
        """ADR-0001 §3 — Stop hook 미등록 시 reflection 이 default-off."""
        self.assertIn("Stop", self.manifest["hooks"])
        entries = self.manifest["hooks"]["Stop"]
        commands = [h["command"] for e in entries for h in e["hooks"]]
        self.assertTrue(any("stop_reflect.py" in c for c in commands), commands)

    def test_hook_matchers_are_expected(self) -> None:
        """SessionStart / Stop 은 '*'. PreToolUse / PostToolUse 는 'Task' 로 좁힘.

        P76 — PostToolUse:Task 추가 (reflection 박제 reminder hook).
        """
        expected = {
            "SessionStart": "*",
            "Stop": "*",
            "PreToolUse": "Task",
            "PostToolUse": "Task",
        }
        for event, entries in self.manifest["hooks"].items():
            for e in entries:
                self.assertEqual(
                    e.get("matcher"), expected.get(event, "*"),
                    f"{event} hook matcher 불일치 (현재: {e.get('matcher')!r})",
                )

    def test_post_tool_use_registered(self) -> None:
        """P76 — PostToolUse:Task reminder hook 박제 (reflection 박제 누락 surface)."""
        self.assertIn("PostToolUse", self.manifest["hooks"])
        commands = [
            h["command"]
            for e in self.manifest["hooks"]["PostToolUse"]
            for h in e["hooks"]
        ]
        self.assertTrue(any("post_tool_use.py" in c for c in commands), commands)

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
        """P48 — 모든 hook 명령은 $CLAUDE_PLUGIN_ROOT 직접 경로를 사용해야 한다.

        ``python3 -m lskun_kit.hooks.x`` 형식은 sys.path 에 src/ 가 없어 hook 실행이
        ModuleNotFoundError 로 깨진다 (실제 설치 환경에서 발현). 회귀 방지 가드.
        """
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
