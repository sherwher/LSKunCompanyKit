"""ADR-0025 (P126) — Delegation Gate 회귀 가드.

위임은 예외, 빙의(embody)가 기본:
    - cpo.md template 에 Delegation Gate 3조건 + 빙의 + 쓰기 단일화 + Handoff Brief 박제
    - dispatch default sonnet (ADR-0004 §4) 잔재 재등장 차단 (모델 상속, D4)
    - routing 컨텍스트가 게이트 판정 + 빙의 분기를 안내
    - sync-persona 가 CLAUDE.md marker 재박제 단계를 포함 (마이그레이션 공백 가드)
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date as _date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import LocalAdapter  # noqa: E402
from lskun_kit.routing import build_cpo_routing_context  # noqa: E402
from lskun_kit.templates import (  # noqa: E402
    iter_default_workers,
    render_default_worker,
)

CPO_TEMPLATE = ROOT / "src" / "lskun_kit" / "templates" / "cpo.md"
WORK_CMD = ROOT / "commands" / "work.md"
SYNC_PERSONA_CMD = ROOT / "commands" / "sync-persona.md"


def _init_local(tmp: Path) -> LocalAdapter:
    co_root = tmp / "company-root"
    hired = co_root / "hired"
    hired.mkdir(parents=True)
    (co_root / "company.md").write_text(
        "---\nname: Test\nfounded: 2026-08-07\ndomain: meta\n---\n# Test\n",
        encoding="utf-8",
    )
    for worker_name, role, template_filename, default_model in iter_default_workers():
        text = render_default_worker(
            name=worker_name,
            role=role,
            template_filename=template_filename,
            storage_backend="local",
            display_name="이세근" if worker_name == "cpo" else "김지혜",
            hired_at=_date(2026, 8, 7),
            model=default_model,
            synced_from="lskun-kit@test",
        )
        (hired / f"{worker_name}.md").write_text(text, encoding="utf-8")
    return LocalAdapter(co_root)


class TestCpoTemplateDelegationGate(unittest.TestCase):
    def setUp(self) -> None:
        self.body = CPO_TEMPLATE.read_text(encoding="utf-8")

    def test_gate_section_exists(self) -> None:
        self.assertIn("## Delegation Gate (ADR-0025)", self.body)

    def test_gate_three_conditions(self) -> None:
        for cond in ("컨텍스트 보호", "병렬 탐색", "독립 검증"):
            self.assertIn(cond, self.body)

    def test_embody_is_default(self) -> None:
        self.assertIn("빙의(embody)", self.body)
        self.assertIn("embody:", self.body)  # audit reason 접두 규약

    def test_single_threaded_writes(self) -> None:
        self.assertIn("쓰기 단일화 (ADR-0025 D3)", self.body)

    def test_handoff_brief_section(self) -> None:
        self.assertIn("## Handoff Brief", self.body)
        for item in ("목표:", "제약:", "관련 파일:", "완료 기준:"):
            self.assertIn(item, self.body)

    def test_no_default_sonnet_regression(self) -> None:
        """ADR-0025 D4 — dispatch default sonnet 잔재 재등장 차단."""
        self.assertNotIn('or "sonnet"', self.body)
        self.assertNotIn("sonnet** 권장 (default)", self.body)
        self.assertIn("메인 세션 모델 상속", self.body)


class TestWorkCommandDelegationGate(unittest.TestCase):
    def setUp(self) -> None:
        self.body = WORK_CMD.read_text(encoding="utf-8")

    def test_gate_in_routing_path(self) -> None:
        self.assertIn("Delegation Gate", self.body)
        self.assertIn("빙의", self.body)

    def test_no_default_sonnet_regression(self) -> None:
        self.assertNotIn("default(`sonnet`)", self.body)
        self.assertNotIn("default(sonnet)", self.body)
        self.assertIn("메인 세션 모델 상속", self.body)


class TestRoutingContextDelegationGate(unittest.TestCase):
    def test_context_includes_gate_and_embody(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            adapter = _init_local(Path(td))
            ctx = build_cpo_routing_context(adapter, user_request="테스트 요청")
        self.assertIn("Delegation Gate 판정 (ADR-0025)", ctx)
        self.assertIn("빙의(embody, 기본 경로)", ctx)
        self.assertIn("Handoff Brief", ctx)
        # 옛 안내 (게이트 없는 즉시 dispatch) 잔재 차단
        self.assertNotIn("적합 워커가 있을 때 — Task tool 로 dispatch:", ctx)


class TestSyncPersonaMigrationChain(unittest.TestCase):
    def test_project_propagation_step_documented(self) -> None:
        """sync 후 프로젝트 쪽이 stale 로 남지 않아야 한다.

        P126 은 "CLAUDE.md marker 재박제" 단계로 막았고, ADR-0029 (P134) 가 그것을
        포인터로 대체했다 — 포인터 프로젝트는 재박제가 필요 없고, 옛 inline
        프로젝트는 sync-persona 가 포인터로 전환한다.
        """
        body = SYNC_PERSONA_CMD.read_text(encoding="utf-8")
        self.assertIn("ADR-0029", body)
        self.assertIn("재박제가 필요 없다", body)
        self.assertIn("persona_injection.inject_pointer", body)


if __name__ == "__main__":
    unittest.main()
