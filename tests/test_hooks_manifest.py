"""Plugin manifest (hooks/hooks.json) 의 hook 등록 검증.

ADR-0014 (2026-05-22) 로 Reflection 메커니즘 폐기 — reflection 용 Stop/PostToolUse
hook 은 제거됐다. ADR-0022 (2026-05-28) 로 **외주 setup 한정** Stop /
PostToolUse:Task hook 이 재도입됐다 (reflection 과 무관, marker 파일 존재 시에만
동작). 따라서 허용 hook event 는 SessionStart / PreToolUse / PostToolUse / Stop
이며, PostToolUse/Stop 의 command 경로는 외주 setup 모듈만 가리켜야 한다.
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

    def test_only_external_setup_hooks_allowed_beyond_pre_tool_use(self) -> None:
        """ADR-0022: reflection 메커니즘 폐기는 유지, 외주 setup 한정 hook 만 허용.

        허용 event 는 SessionStart / PreToolUse / PostToolUse / Stop 뿐이고,
        PostToolUse / Stop 의 command 경로는 외주 setup 모듈만 가리켜야 한다
        (reflection hook 재도입 방지 — forbidden-history.md:45 부분 supersede).
        """
        hooks = self.manifest["hooks"]
        allowed_events = {"SessionStart", "PreToolUse", "PostToolUse", "Stop"}
        self.assertTrue(
            set(hooks.keys()) <= allowed_events,
            f"unexpected hook events: {set(hooks.keys()) - allowed_events}",
        )

        # PostToolUse 는 Task matcher + external 모듈 경로 강제.
        for e in hooks.get("PostToolUse", []):
            self.assertEqual(e["matcher"], "Task")
            for cmd in e["hooks"]:
                self.assertIn("post_tool_use_external", cmd["command"])

        # Stop 도 external 모듈만 허용.
        for e in hooks.get("Stop", []):
            for cmd in e["hooks"]:
                self.assertIn("stop_external", cmd["command"])

    def test_external_setup_hooks_registered(self) -> None:
        """ADR-0022: PostToolUse:Task + Stop 등록 검증."""
        hooks = self.manifest["hooks"]
        self.assertIn("PostToolUse", hooks)
        self.assertIn("Stop", hooks)

    def test_hook_matchers_are_expected(self) -> None:
        """SessionStart/Stop 은 '*'. PreToolUse/PostToolUse 는 'Task' 로 좁힘."""
        expected = {
            "SessionStart": "*",
            "PreToolUse": "Task",
            "PostToolUse": "Task",  # ADR-0022 외주 setup push
            "Stop": "*",            # ADR-0022 외주 setup turn 차단
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
