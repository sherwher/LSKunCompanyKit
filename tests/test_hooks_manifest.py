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
        self.assertIn("python3 -m lskun_kit.hooks.session_start", commands)

    def test_stop_hook_registered(self) -> None:
        """ADR-0001 §3 — Stop hook 미등록 시 reflection 이 default-off 되어
        핵심 메커니즘 #1 이 동작하지 않는다."""
        self.assertIn(
            "Stop",
            self.manifest["hooks"],
            "Stop hook 이 plugin manifest 에 등록되어 있어야 reflection 이 default-on",
        )
        entries = self.manifest["hooks"]["Stop"]
        commands = [h["command"] for e in entries for h in e["hooks"]]
        self.assertIn("python3 -m lskun_kit.hooks.stop_reflect", commands)

    def test_hook_matchers_are_expected(self) -> None:
        """SessionStart / Stop 은 '*'. PreToolUse 는 'Task' 로 좁힘 (P31)."""
        expected = {
            "SessionStart": "*",
            "Stop": "*",
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
        self.assertIn("python3 -m lskun_kit.hooks.pre_tool_use", commands)


if __name__ == "__main__":
    unittest.main()
