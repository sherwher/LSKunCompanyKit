"""P127 — 실행 품질 규격화 회귀 가드 (ADR-0025 / ADR-0024 보강, v0.33.0).

브리프·보고·검증 세 접점 규격화:
    - Handoff Brief 에 기대 출력 형식 / 도구·소스 가이드 필드 추가
    - 빙의(embody) 경로 증거 게이트 — 새 검증 증거 없이 완료 주장 금지
    - 워커 보고 상태코드 enum + CPO 상태코드별 분기
    - Delegation Gate 통과 후 규모 스케일링 규칙 (병렬 상한 4)
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit.routing import build_cpo_routing_context  # noqa: E402

from test_delegation_gate import _init_local  # noqa: E402

CPO_TEMPLATE = ROOT / "src" / "lskun_kit" / "templates" / "cpo.md"
HR_TEMPLATE = ROOT / "src" / "lskun_kit" / "templates" / "hr-lead.md"
WORK_CMD = ROOT / "commands" / "work.md"

STATUS_CODES = ("DONE", "DONE_WITH_CONCERNS", "NEEDS_CONTEXT", "BLOCKED")


class TestHandoffBriefFields(unittest.TestCase):
    def setUp(self) -> None:
        self.body = CPO_TEMPLATE.read_text(encoding="utf-8")

    def test_new_fields_present(self) -> None:
        for item in ("기대 출력 형식:", "도구·소스 가이드:"):
            self.assertIn(item, self.body)

    def test_existing_fields_kept(self) -> None:
        for item in ("목표:", "제약:", "관련 파일:", "지금까지의 결정:", "완료 기준:"):
            self.assertIn(item, self.body)


class TestEmbodyEvidenceGate(unittest.TestCase):
    def setUp(self) -> None:
        self.body = CPO_TEMPLATE.read_text(encoding="utf-8")

    def test_evidence_gate_section(self) -> None:
        self.assertIn("### 증거 게이트", self.body)
        self.assertIn("새 검증 증거", self.body)
        self.assertIn("미검증", self.body)

    def test_approval_loop_covers_embody(self) -> None:
        self.assertIn("dispatch 또는 빙의 1건당", self.body)
        self.assertNotIn("본 절차는 dispatch 1건당", self.body)


class TestReportStatusCodes(unittest.TestCase):
    def setUp(self) -> None:
        self.body = CPO_TEMPLATE.read_text(encoding="utf-8")

    def test_status_line_in_report_format(self) -> None:
        self.assertIn("상태: " + " | ".join(STATUS_CODES), self.body)

    def test_status_line_injected_via_deep_work_protocol(self) -> None:
        """보고 양식은 워커 prompt 에 자동 주입되지 않는다 — 모든 dispatch 에
        붙는 Deep Work Protocol 블록에도 상태 줄이 있어야 워커가 안다."""
        start = self.body.index("## 작업 프로토콜 (Deep Work Protocol)")
        block = self.body[start : self.body.index("```", start)]
        self.assertIn("상태: " + " | ".join(STATUS_CODES), block)

    def test_branch_per_status(self) -> None:
        self.assertIn("### 상태코드별 분기", self.body)
        for code in STATUS_CODES:
            self.assertIn(f"`{code}`", self.body)

    def test_old_self_eval_vocabulary_removed(self) -> None:
        self.assertNotIn("<통과 / 부분 통과 / 불확실>", self.body)

    def test_report_keeps_two_sections(self) -> None:
        """ADR-0014 — 보고는 작업 결과 + 자가 평가 2섹션 유지."""
        self.assertIn("## 작업 결과", self.body)
        self.assertIn("## 자가 평가", self.body)

    def test_hr_lead_report_uses_status_code(self) -> None:
        hr = HR_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("상태: DONE", hr)


class TestScalingRule(unittest.TestCase):
    def setUp(self) -> None:
        self.body = CPO_TEMPLATE.read_text(encoding="utf-8")

    def test_scaling_section(self) -> None:
        self.assertIn("### 규모 스케일링", self.body)
        self.assertIn("상한 4", self.body)

    def test_parallel_requires_disjoint_boundaries(self) -> None:
        self.assertIn("작업 경계", self.body)


class TestWorkCommandAndRoutingContext(unittest.TestCase):
    def test_work_command_mentions_p127(self) -> None:
        body = WORK_CMD.read_text(encoding="utf-8")
        self.assertIn("상태코드", body)
        self.assertIn("규모 스케일링", body)
        self.assertIn("증거 게이트", body)

    def test_routing_context_mentions_p127(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            adapter = _init_local(Path(td))
            ctx = build_cpo_routing_context(adapter, user_request="테스트 요청")
        self.assertIn("규모 스케일링", ctx)
        self.assertIn("상태코드", ctx)
        self.assertIn("증거 게이트", ctx)


if __name__ == "__main__":
    unittest.main()
