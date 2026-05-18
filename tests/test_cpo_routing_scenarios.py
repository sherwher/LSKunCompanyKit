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
from lskun_kit.init import LOCAL_COMPANY_DIRNAME, run as init_run  # noqa: E402
from lskun_kit.routing import build_cpo_routing_context  # noqa: E402
from lskun_kit.templates import render_default_worker  # noqa: E402


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
    """init + 추가 워커 hire."""
    init_run(tmp, cpo_name="이세근", hr_name="김지혜", env={})
    adapter = LocalAdapter(tmp / LOCAL_COMPANY_DIRNAME)
    for w in workers:
        rendered = render_default_worker(
            name=w["name"],
            role=w["role"],
            template_filename="cpo.md",
            storage_backend="local",
            display_name=w["name"].title(),
        )
        # frontmatter 의 domain 만 교체 (단순 텍스트 replace)
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
