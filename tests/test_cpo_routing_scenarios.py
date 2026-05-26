"""P47 (#23) — CPO 라우팅 컨텍스트 시나리오 회귀 가드.

LLM 영역 (CPO 의 최종 워커 선택 / 결재 판단 / 자동 채용 결정) 은 코드로 단위
테스트가 불가능하다. 대신 ``build_cpo_routing_context`` 가 결정론적으로 만드는
컨텍스트 구조 (후보 목록 / 응답 양식 / 자동 채용 안내 / 워커 chain 금지 명시)
가 회귀하지 않는지 검증한다.

시나리오는 ``tests/fixtures/cpo_routing_scenarios.jsonl`` 에 박제. 각 줄은 한 케이스.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import LocalAdapter  # noqa: E402
from lskun_kit.routing import build_cpo_routing_context  # noqa: E402
from lskun_kit.templates import (  # noqa: E402
    iter_default_workers,
    render_default_worker,
)


FIXTURE_PATH = ROOT / "tests" / "fixtures" / "cpo_routing_scenarios.jsonl"


def _load_scenarios() -> list[dict]:
    out: list[dict] = []
    for line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(json.loads(line))
    return out


def _setup_company(tmp: Path, workers: list[dict]) -> LocalAdapter:
    """ADR-0015 — 임시 회사 root 에 CPO/HR + 추가 워커 hire.

    test_routing 과 동일 패턴 — init.run() 풀체인 없이 직접 디렉토리 박제하여
    Path.home() mock 의존도 0.
    """
    from datetime import date as _date
    co_root = tmp / "company-root"
    hired = co_root / "hired"
    hired.mkdir(parents=True)
    (co_root / "company.md").write_text(
        "---\nname: Test\nfounded: 2026-05-22\ndomain: meta\n---\n# Test\n",
        encoding="utf-8",
    )
    for worker_name, role, template_filename, default_model in iter_default_workers():
        text = render_default_worker(
            name=worker_name,
            role=role,
            template_filename=template_filename,
            storage_backend="local",
            display_name="이세근" if worker_name == "cpo" else "김지혜",
            hired_at=_date(2026, 5, 22),
            model=default_model,
            synced_from="lskun-kit@test",
        )
        (hired / f"{worker_name}.md").write_text(text, encoding="utf-8")
    adapter = LocalAdapter(co_root)
    for w in workers:
        rendered = render_default_worker(
            name=w["name"],
            role=w["role"],
            template_filename="cpo.md",
            storage_backend="local",
            display_name=w["name"].title(),
        )
        rendered = rendered.replace(
            "domain: meta", f"domain: {w['domain']}"
        ).replace(
            "role: chief-product-officer", f"role: {w['role']}"
        ).replace(
            "name: cpo", f"name: {w['name']}"
        )
        (adapter.root / "hired" / f"{w['name']}.md").write_text(
            rendered, encoding="utf-8"
        )
    return adapter


class CpoRoutingScenarioTests(unittest.TestCase):
    """fixture 로 박제된 시나리오를 모두 통과해야 한다."""

    def test_fixture_file_exists_and_has_scenarios(self) -> None:
        self.assertTrue(FIXTURE_PATH.exists())
        scenarios = _load_scenarios()
        self.assertGreaterEqual(len(scenarios), 3)

    def test_all_scenarios_produce_expected_context(self) -> None:
        scenarios = _load_scenarios()
        for s in scenarios:
            with self.subTest(scenario=s["id"]):
                with tempfile.TemporaryDirectory() as tmp:
                    adapter = _setup_company(Path(tmp), s["workers"])
                    ctx = build_cpo_routing_context(
                        adapter, user_request=s["user_request"]
                    )
                    for needle in s.get("expected_in_context", []):
                        self.assertIn(
                            needle, ctx,
                            f"scenario {s['id']!r}: {needle!r} not in ctx",
                        )
                    for forbidden in s.get("expected_not_in_context", []):
                        self.assertNotIn(
                            forbidden, ctx,
                            f"scenario {s['id']!r}: {forbidden!r} should not appear",
                        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
