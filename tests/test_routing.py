"""lskun_kit.routing 단위 테스트.

ADR-0002 §1 의 CPO 라우팅 분기 (Q1=ii) 를 검증한다:
    - direct: 워커 이름 명시 → CPO 경유 안 함
    - cpo: 이름 생략 + CPO hired → CPO 라우팅
    - missing-cpo: 이름 생략 + CPO 없음 → init 안내
    - build_cpo_routing_context 가 CPO/HR 를 라우팅 후보에서 제외
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import LocalAdapter, WorkerNotFoundError  # noqa: E402
from lskun_kit.init import LOCAL_COMPANY_DIRNAME, run  # noqa: E402
from lskun_kit.routing import (  # noqa: E402
    CPO_WORKER_NAME,
    HR_LEAD_WORKER_NAME,
    build_cpo_routing_context,
    decide_target,
)
from lskun_kit.templates import render_default_worker  # noqa: E402


def _init_local(tmp: Path) -> LocalAdapter:
    run(tmp, cpo_name="이세근", hr_name="김지혜", env={})
    return LocalAdapter(tmp / LOCAL_COMPANY_DIRNAME)


def _hire_extra(adapter: LocalAdapter, name: str, role: str) -> None:
    rendered = render_default_worker(
        name=name,
        role=role,
        template_filename="cpo.md",
        storage_backend="local",
        display_name=name.title(),
    )
    # 위에서 cpo.md 본문을 빌리지만 frontmatter 의 name/role 은 새 워커 것.
    # 본문 내용은 테스트 목적상 무관.
    (adapter.root / "hired" / f"{name}.md").write_text(rendered, encoding="utf-8")


class DecideTargetTests(unittest.TestCase):
    def test_direct_when_worker_specified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = _init_local(Path(tmp))
            d = decide_target(adapter, requested_worker="backend-engineer")
            self.assertEqual(d.mode, "direct")
            self.assertEqual(d.target_worker, "backend-engineer")

    def test_cpo_when_name_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = _init_local(Path(tmp))
            d = decide_target(adapter, requested_worker=None)
            self.assertEqual(d.mode, "cpo")
            self.assertEqual(d.target_worker, CPO_WORKER_NAME)

    def test_missing_cpo_returns_init_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hired = Path(tmp, ".company", "hired")
            hired.mkdir(parents=True)
            adapter = LocalAdapter(Path(tmp, ".company"))
            d = decide_target(adapter, requested_worker=None)
            self.assertEqual(d.mode, "missing-cpo")
            self.assertIn("/lskun-kit:init", d.reason)

    def test_whitespace_only_name_is_treated_as_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = _init_local(Path(tmp))
            d = decide_target(adapter, requested_worker="   ")
            self.assertEqual(d.mode, "cpo")


class BuildCpoRoutingContextTests(unittest.TestCase):
    def test_excludes_cpo_and_hr_from_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = _init_local(Path(tmp))
            _hire_extra(adapter, "backend-engineer", "backend-engineer")

            ctx = build_cpo_routing_context(
                adapter, user_request="API 한 개 짜줘"
            )
            self.assertIn("backend-engineer", ctx)
            self.assertIn("Hired Workers", ctx)
            # CPO/HR 는 후보 섹션에 등장하면 안 됨
            # (frontmatter 영역에 "cpo (chief-product-officer)" 가 있을 수는 있으므로
            # 후보 섹션만 잘라서 검사)
            candidates_section = ctx.split("## Hired Workers")[1].split("## User Request")[0]
            self.assertNotIn(CPO_WORKER_NAME, candidates_section)
            self.assertNotIn(HR_LEAD_WORKER_NAME, candidates_section)

    def test_empty_candidates_directs_to_auto_hire(self) -> None:
        """P35 — ADR-0004 §3: 적합 워커 부재 시 CPO 가 HR Lead Task dispatch 로 자동 채용."""
        with tempfile.TemporaryDirectory() as tmp:
            adapter = _init_local(Path(tmp))
            ctx = build_cpo_routing_context(adapter, user_request="아무거나")
            # 후보 부재 메시지는 자동 채용 흐름을 가리켜야 한다.
            self.assertIn("자동 채용", ctx)
            self.assertIn("HR Lead", ctx)
            # ADR-0002 시대 "사용자가 hr-lead 를 명시 호출" 안내가 살아있으면 안 됨.
            self.assertNotIn("권장 조치", ctx)

    def test_response_format_documented(self) -> None:
        """P35 — 응답 양식이 ADR-0004 §3 자동 채용 흐름을 명시한다."""
        with tempfile.TemporaryDirectory() as tmp:
            adapter = _init_local(Path(tmp))
            ctx = build_cpo_routing_context(adapter, user_request="x")
            self.assertIn("추천 워커:", ctx)
            # 자동 채용 행동 양식 (Task tool 호출)
            self.assertIn("자동 채용", ctx)
            self.assertIn("Task tool", ctx)
            self.assertIn("[채용 알림]", ctx)
            # 워커 → 워커 chain 금지 명시 (ADR-0004 §8)
            self.assertIn("chain", ctx.lower())

    def test_raises_when_cpo_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, ".company", "hired").mkdir(parents=True)
            adapter = LocalAdapter(Path(tmp, ".company"))
            with self.assertRaises(WorkerNotFoundError):
                build_cpo_routing_context(adapter, user_request="x")


class Adr0004ConsistencyTests(unittest.TestCase):
    """P35 회귀 가드 — routing.py 가 ADR-0002 의 폐기 조항을 재유입하지 않도록 검증."""

    def test_module_docstring_does_not_reaffirm_no_chain_to_hr(self) -> None:
        import lskun_kit.routing as routing_mod
        doc = (routing_mod.__doc__ or "")
        # ADR-0002 폐기 조항: "CPO 가 인사팀장을 chain 호출하지 않는다 (ADR-0002 §1 금지)"
        # ADR-0004 §3 이 폐기. docstring 에 그대로 재등장 금지.
        self.assertNotIn(
            "인사팀장을 chain 호출하지 않는다", doc,
            "ADR-0002 의 폐기 조항이 docstring 에 재유입됨 (ADR-0004 §3 이 자동 채용 허용)",
        )

    def test_response_format_does_not_offload_hire_to_user(self) -> None:
        """과거 양식 '사용자가 hr-lead 를 명시 호출' 안내가 살아있으면 회귀."""
        with tempfile.TemporaryDirectory() as tmp:
            adapter = _init_local(Path(tmp))
            ctx = build_cpo_routing_context(adapter, user_request="x")
            self.assertNotIn(
                "CPO 는 인사팀장을 직접 호출하지 않는다", ctx,
                "ADR-0002 폐기 조항 재유입",
            )
            self.assertNotIn(
                "신규 채용 요청 — role=", ctx,
                "ADR-0002 시대의 사용자 명시 호출 안내가 재유입됨",
            )


class TemplateRenderingTests(unittest.TestCase):
    def test_default_workers_are_cpo_and_hr_lead(self) -> None:
        from lskun_kit.templates import list_default_worker_names

        self.assertEqual(
            sorted(list_default_worker_names()), ["cpo", "hr-lead"]
        )

    def test_render_includes_required_frontmatter(self) -> None:
        rendered = render_default_worker(
            name="cpo",
            role="chief-product-officer",
            template_filename="cpo.md",
            storage_backend="vault",
            display_name="이세근",
        )
        for field in (
            "name:",
            "role:",
            "domain:",
            "hired_at:",
            "storage_backend:",
            "display_name:",
        ):
            self.assertIn(field, rendered)
        self.assertIn("storage_backend: vault", rendered)
        # default domain = "meta" (ADR-0003 §1)
        self.assertIn("domain: meta", rendered)
        # display_name 그대로 박제 (ADR-0004 §5)
        self.assertIn("display_name: 이세근", rendered)
        # model 미지정 시 frontmatter 에 emit 안 함 (ADR-0004 §6)
        self.assertNotIn("model:", rendered)

    def test_render_emits_model_when_specified(self) -> None:
        rendered = render_default_worker(
            name="hr-lead",
            role="hr-lead",
            template_filename="hr-lead.md",
            storage_backend="local",
            display_name="김지혜",
            model="sonnet",
        )
        self.assertIn("model: sonnet", rendered)

    def test_render_rejects_empty_display_name(self) -> None:
        with self.assertRaises(ValueError):
            render_default_worker(
                name="x",
                role="x",
                template_filename="cpo.md",
                storage_backend="local",
                display_name="",
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
