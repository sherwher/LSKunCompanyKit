"""워커 skills 필드 테스트 (ADR-0020, P111).

stdlib unittest 만 사용. spec §7.3 의 테스트 항목 전부 커버:
    - models / read_worker: skills optional 파싱
    - context: build_skills_block 주입 / 누락 표시 / 빈 값 생략 / 경로 조합
    - C1 회귀: 양 dispatch 경로 (build_worker_context + worker.body 조립) 주입
    - M1 보안: skill 이름 traversal / 공백 / 빈 토큰 거부
    - doctor: dangling / orphan / invalid / meta 검출
    - 마이그레이션: skills 없는 기존 워커가 여전히 정상
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import LocalAdapter  # noqa: E402
from lskun_kit.context import (  # noqa: E402
    _split_skills,
    build_skills_block,
    build_worker_context,
)
from lskun_kit.skills_diagnostics import diagnose_skills  # noqa: E402


def _worker_md(name: str, *, domain: str = "medical", skills: str | None = None) -> str:
    fm = dedent(
        f"""\
        ---
        name: {name}
        role: {name}
        domain: {domain}
        hired_at: 2026-05-27
        storage_backend: local
        display_name: Test {name}
        """
    )
    if skills is not None:
        fm += f"skills: {skills}\n"
    fm += "---\nJD body 본문\n"
    return fm


def _skill_md(name: str) -> str:
    return f"---\nname: {name}\ndescription: 테스트 스킬\n---\n체크리스트 본문\n"


class SkillsTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self.root = Path(self._tmp)
        (self.root / "hired").mkdir()
        (self.root / "skills").mkdir()
        self.adapter = LocalAdapter(self.root)

    def _write_worker(self, name: str, **kw) -> None:
        (self.root / "hired" / f"{name}.md").write_text(
            _worker_md(name, **kw), encoding="utf-8"
        )

    def _write_skill(self, name: str) -> None:
        (self.root / "skills" / f"{name}.md").write_text(
            _skill_md(name), encoding="utf-8"
        )


class TestSplitSkills(unittest.TestCase):
    def test_none_and_empty(self) -> None:
        self.assertEqual(_split_skills(None), [])
        self.assertEqual(_split_skills(""), [])
        self.assertEqual(_split_skills("   "), [])

    def test_empty_tokens_dropped(self) -> None:
        self.assertEqual(_split_skills("a,,b"), ["a", "b"])
        self.assertEqual(_split_skills(" a , b ,"), ["a", "b"])

    def test_normal(self) -> None:
        self.assertEqual(
            _split_skills("hipaa-phi-masking, hl7-fhir-validator"),
            ["hipaa-phi-masking", "hl7-fhir-validator"],
        )


class TestReadWorkerSkills(SkillsTestBase):
    def test_skills_parsed(self) -> None:
        self._write_worker("backend", skills="hipaa-phi-masking")
        self.assertEqual(self.adapter.read_worker("backend").skills, "hipaa-phi-masking")

    def test_skills_absent_is_none(self) -> None:
        self._write_worker("backend")  # skills 미지정
        self.assertIsNone(self.adapter.read_worker("backend").skills)


class TestBuildSkillsBlock(SkillsTestBase):
    def test_block_contains_paths_and_directive(self) -> None:
        self._write_skill("hipaa-phi-masking")
        self._write_worker("backend", skills="hipaa-phi-masking")
        block = build_skills_block(self.adapter, "backend")
        self.assertIn("전문 도구", block)
        self.assertIn("hipaa-phi-masking", block)
        self.assertIn("Read", block)
        self.assertIn("읽은 전문 도구", block)  # M3 가시성 지시

    def test_missing_skill_flagged(self) -> None:
        self._write_worker("backend", skills="missing-one")
        block = build_skills_block(self.adapter, "backend")
        self.assertIn("⚠️ 파일 없음", block)

    def test_empty_skills_omits_block(self) -> None:
        self._write_worker("backend")  # skills 없음
        self.assertEqual(build_skills_block(self.adapter, "backend"), "")

    def test_invalid_name_flagged_not_pathed(self) -> None:
        # M1 — traversal 토큰은 경로 조합 없이 invalid 표시
        self._write_worker("backend", skills="../etc/passwd, ok-skill")
        block = build_skills_block(self.adapter, "backend")
        self.assertIn("invalid skill name", block)


class TestDispatchInjectionC1(SkillsTestBase):
    """C1 회귀 — 양 dispatch 경로에 skills 가 도달하는지."""

    def test_direct_path_build_worker_context(self) -> None:
        # 직통 경로: build_worker_context 가 내부에서 append
        self._write_skill("hipaa-phi-masking")
        self._write_worker("backend", skills="hipaa-phi-masking")
        ctx = build_worker_context(self.adapter, "backend")
        self.assertIn("# Worker: backend", ctx)
        self.assertIn("전문 도구", ctx)
        self.assertIn("hipaa-phi-masking", ctx)

    def test_cpo_path_body_plus_block(self) -> None:
        # CPO 경로: worker.body + build_skills_block + user_request 조립 시뮬레이션
        self._write_skill("hipaa-phi-masking")
        self._write_worker("backend", skills="hipaa-phi-masking")
        worker = self.adapter.read_worker("backend")
        context = worker.body + build_skills_block(self.adapter, "backend") + "요청"
        self.assertIn("JD body 본문", context)  # body 보존
        self.assertIn("전문 도구", context)  # skills 주입
        self.assertIn("요청", context)

    def test_both_paths_consistent_for_empty(self) -> None:
        # skills 없으면 양 경로 모두 블록 없음
        self._write_worker("backend")
        ctx = build_worker_context(self.adapter, "backend")
        self.assertNotIn("전문 도구", ctx)
        worker = self.adapter.read_worker("backend")
        context = worker.body + build_skills_block(self.adapter, "backend")
        self.assertNotIn("전문 도구", context)


class TestSkillPathSecurity(SkillsTestBase):
    """M1 — skill_path traversal 차단."""

    def test_traversal_rejected(self) -> None:
        for bad in ("../etc/passwd", "/abs/path", "foo bar", "a/b", ".."):
            with self.assertRaises(ValueError):
                self.adapter.skill_path(bad)

    def test_valid_names_accepted(self) -> None:
        for ok in ("hipaa-phi-masking", "skill_1", "a"):
            path = self.adapter.skill_path(ok)
            self.assertTrue(str(path).endswith(f"skills/{ok}.md"))

    def test_list_skills(self) -> None:
        self._write_skill("a")
        self._write_skill("b")
        self.assertEqual(self.adapter.list_skills(), ["a", "b"])


class TestSkillsDiagnostics(SkillsTestBase):
    def test_dangling(self) -> None:
        self._write_worker("backend", skills="missing-one")
        diag = diagnose_skills(self.adapter)
        self.assertIn(("backend", "missing-one"), diag.dangling)

    def test_orphan(self) -> None:
        self._write_skill("orphan-skill")
        self._write_worker("backend")  # 아무도 선언 안 함
        diag = diagnose_skills(self.adapter)
        self.assertIn("orphan-skill", diag.orphan)

    def test_declared_skill_not_orphan(self) -> None:
        self._write_skill("used-skill")
        self._write_worker("backend", skills="used-skill")
        diag = diagnose_skills(self.adapter)
        self.assertNotIn("used-skill", diag.orphan)
        self.assertTrue(diag.is_clean())

    def test_invalid_name(self) -> None:
        self._write_worker("backend", skills="../bad")
        diag = diagnose_skills(self.adapter)
        self.assertIn(("backend", "../bad"), diag.invalid)

    def test_meta_worker_skills_flagged(self) -> None:
        self._write_worker("cpo", domain="meta", skills="should-not-be-here")
        diag = diagnose_skills(self.adapter)
        self.assertIn(("cpo", "should-not-be-here"), diag.meta_declared)

    def test_clean_when_no_skills(self) -> None:
        self._write_worker("backend")
        self.assertTrue(diagnose_skills(self.adapter).is_clean())

    def test_skill_path_valueerror_does_not_crash(self) -> None:
        # C-1 — skill_path 가 ValueError 를 던지는 입력에서도 진단이 크래시 안 함.
        # symlink 로 skills/ 밖을 향하는 토큰: 정규식은 통과, resolve 가드는 거부.
        outside = self.root / "outside.md"
        outside.write_text(_skill_md("x"), encoding="utf-8")
        (self.root / "skills" / "escaper.md").symlink_to(outside)
        # escaper 자체는 skills/ 안의 심볼릭이라 resolve 시 밖을 가리킴 → skill_path 거부
        self._write_worker("backend", skills="escaper")
        # 크래시 없이 invalid 로 분류되거나 정상 처리되어야 함
        diag = diagnose_skills(self.adapter)  # raise 하면 테스트 실패
        self.assertIsNotNone(diag)


class TestBlockSeparator(SkillsTestBase):
    """C-2 — 앞 콘텐츠가 newline 없이 끝나도 heading 이 안 붙는지."""

    def test_block_has_leading_blank_line(self) -> None:
        self._write_skill("ok-skill")
        self._write_worker("backend", skills="ok-skill")
        block = build_skills_block(self.adapter, "backend")
        self.assertTrue(block.startswith("\n\n## 전문 도구"))

    def test_cpo_concat_no_newline_body_safe(self) -> None:
        # body 가 newline 없이 끝나는 경우 heading 이 깨지지 않음
        self._write_skill("ok-skill")
        self._write_worker("backend", skills="ok-skill")
        block = build_skills_block(self.adapter, "backend")
        body_no_nl = "JD 마지막 줄"  # trailing newline 없음
        context = body_no_nl + block
        self.assertNotIn("줄## 전문 도구", context)
        self.assertIn("줄\n\n## 전문 도구", context)


class TestMigrationSafety(SkillsTestBase):
    """skills 없는 기존 워커가 안 깨지는지 (P69 선례)."""

    def test_legacy_worker_reads_fine(self) -> None:
        self._write_worker("legacy")  # skills 키 자체 없음
        worker = self.adapter.read_worker("legacy")
        self.assertIsNone(worker.skills)
        self.assertEqual(worker.role, "legacy")


if __name__ == "__main__":
    unittest.main()
