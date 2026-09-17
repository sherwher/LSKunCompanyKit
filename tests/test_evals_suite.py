"""ADR-0028 (P133) — eval suite 구조 회귀 가드.

eval 실행 자체는 모델 호출 비용이 들어 unittest 에서 돌리지 않는다. 여기서는
케이스가 실행 가능한 형태인지만 본다 (fixture 실행 권한, grader 존재, persona 비복제).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
CASES = sorted(p.parent for p in EVALS.glob("*/case.yaml"))


class EvalSuiteStructureTests(unittest.TestCase):
    def test_cases_exist(self) -> None:
        self.assertGreaterEqual(len(CASES), 5)

    def test_each_case_is_runnable(self) -> None:
        for case in CASES:
            with self.subTest(case=case.name):
                self.assertTrue((case / "prompt.md").exists())
                self.assertTrue(list((case / "graders").glob("*.md")), "grader 없음")
                fixture = case / "fixture.sh"
                self.assertTrue(fixture.exists())
                self.assertTrue(os.access(fixture, os.X_OK), "fixture.sh 실행 권한 없음")
                self.assertIn(f"name: {case.name}", (case / "case.yaml").read_text(encoding="utf-8"))

    def test_bash_dependent_cases_are_outside_core_tag(self) -> None:
        """Bash 샌드박스를 못 쓰는 머신에서 `--tag core` 가 통째로 실패하지 않도록."""
        for case in CASES:
            prompt = (case / "prompt.md").read_text(encoding="utf-8")
            tags = (case / "case.yaml").read_text(encoding="utf-8")
            if "Bash" in prompt.split("---")[1]:
                self.assertNotIn("core", tags.split("tags:")[1].splitlines()[0], case.name)

    def test_persona_not_duplicated_into_cases(self) -> None:
        """persona SSOT 는 templates/cpo.md — 케이스에 본문을 복제하지 않는다."""
        for case in CASES:
            prompt = (case / "prompt.md").read_text(encoding="utf-8")
            self.assertNotIn("append_system_prompt", prompt, case.name)
            self.assertLess(len(prompt), 1500, case.name)

    def test_results_ignored(self) -> None:
        self.assertIn("results/", (EVALS / ".gitignore").read_text(encoding="utf-8"))

    def test_shared_fixture_builds_company(self) -> None:
        """공용 fixture 가 임시 HOME 에 회사와 CLAUDE.md marker 를 실제로 만든다."""
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as work:
            proc = subprocess.run(
                ["bash", str(CASES[0] / "fixture.sh")],
                cwd=work, capture_output=True, text=True,
                env={"HOME": home, "PATH": os.environ.get("PATH", "")},
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            co = Path(home) / ".lskun-companies" / "EvalCo"
            self.assertTrue((co / "hired" / "backend-engineer.md").exists())
            self.assertTrue((co / "hired" / "cpo.md").exists())
            self.assertIn("LSKUN-CPO", (Path(work) / "CLAUDE.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
