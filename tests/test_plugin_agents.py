"""ADR-0026 (P129) — plugin 제공 agent 정의 회귀 가드.

dispatch 워커의 쓰기 단일화 (ADR-0025 D3) 와 chain 금지 (ADR-0004 §8) 를
프롬프트가 아닌 도구 권한으로 강제한다.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit.hooks import pre_tool_use  # noqa: E402

AGENTS_DIR = ROOT / "agents"
MANIFEST = ROOT / ".claude-plugin" / "plugin.json"


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path.name}: frontmatter 없음"
    block = text.split("---\n", 2)[1]
    out: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out


def _tools(value: str) -> set[str]:
    return {t.strip() for t in value.split(",") if t.strip()}


class WorkerAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fm = _frontmatter(AGENTS_DIR / "worker.md")

    def test_name_matches_filename(self) -> None:
        self.assertEqual(self.fm["name"], "worker")

    def test_write_tools_and_agent_removed(self) -> None:
        denied = _tools(self.fm["disallowedTools"])
        self.assertLessEqual({"Write", "Edit", "NotebookEdit", "Agent"}, denied)

    def test_bash_kept(self) -> None:
        """테스트 실행·탐색을 위해 Bash 는 유지 (ADR-0026 알려진 한계)."""
        self.assertNotIn("Bash", _tools(self.fm["disallowedTools"]))

    def test_model_inherits(self) -> None:
        """ADR-0025 D4 — 자동 강등 금지."""
        self.assertEqual(self.fm["model"], "inherit")

    def test_no_tools_allowlist(self) -> None:
        """MCP·WebFetch·Skill 등 정당한 도구를 막지 않도록 denylist 만 쓴다."""
        self.assertNotIn("tools", self.fm)

    def test_no_memory_field(self) -> None:
        """ADR-0014 — 세션 간 학습 금지."""
        self.assertNotIn("memory", self.fm)


class HrLeadAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fm = _frontmatter(AGENTS_DIR / "hr-lead.md")

    def test_name_matches_filename(self) -> None:
        self.assertEqual(self.fm["name"], "hr-lead")

    def test_only_agent_tool_removed(self) -> None:
        """HR Lead 는 skill 파일 Write·채용 파일 생성이 정상 업무 (ADR-0020/0023)."""
        self.assertEqual(_tools(self.fm["disallowedTools"]), {"Agent"})

    def test_model_inherits(self) -> None:
        self.assertEqual(self.fm["model"], "inherit")

    def test_no_memory_field(self) -> None:
        self.assertNotIn("memory", self.fm)


class AllowlistMatchesAgentsTests(unittest.TestCase):
    def test_allowlist_equals_plugin_agents(self) -> None:
        """hook allowlist 와 실제 agent 파일이 어긋나면 dispatch 가 전부 막힌다."""
        plugin = json.loads(MANIFEST.read_text(encoding="utf-8"))["name"]
        expected = {
            f"{plugin}:{p.stem}" for p in AGENTS_DIR.glob("*.md")
        }
        self.assertEqual(set(pre_tool_use._ALLOWED_SUBAGENT), expected)

    def test_agent_bodies_do_not_embed_persona(self) -> None:
        """ADR-0014 — JD 는 dispatch prompt 로 전달. agent 본문은 최소 (이중 SSOT 방지)."""
        for p in AGENTS_DIR.glob("*.md"):
            body = p.read_text(encoding="utf-8").split("---\n", 2)[2]
            self.assertLess(len(body), 1500, f"{p.name} 본문이 너무 김")


if __name__ == "__main__":
    unittest.main()
