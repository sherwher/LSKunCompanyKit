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
    run(tmp, env={})
    return LocalAdapter(tmp / LOCAL_COMPANY_DIRNAME)


def _hire_extra(adapter: LocalAdapter, name: str, role: str) -> None:
    rendered = render_default_worker(
        name=name, role=role, template_filename="cpo.md", storage_backend="local"
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

    def test_empty_candidates_shows_hire_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = _init_local(Path(tmp))
            ctx = build_cpo_routing_context(adapter, user_request="아무거나")
            self.assertIn("채용 권장", ctx)

    def test_response_format_documented(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            adapter = _init_local(Path(tmp))
            ctx = build_cpo_routing_context(adapter, user_request="x")
            self.assertIn("추천 워커:", ctx)
            self.assertIn("권장 조치:", ctx)
            self.assertIn("/lskun-kit:work hr-lead", ctx)

    def test_raises_when_cpo_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, ".company", "hired").mkdir(parents=True)
            adapter = LocalAdapter(Path(tmp, ".company"))
            with self.assertRaises(WorkerNotFoundError):
                build_cpo_routing_context(adapter, user_request="x")


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
        )
        for field in ("name:", "role:", "hired_at:", "storage_backend:"):
            self.assertIn(field, rendered)
        self.assertIn("storage_backend: vault", rendered)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
