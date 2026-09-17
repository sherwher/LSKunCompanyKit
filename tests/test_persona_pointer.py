"""ADR-0029 (P134) — persona 포인터 배포 회귀 가드.

본문은 회사 SSOT 에 한 부, 프로젝트에는 ``CLAUDE.local.md`` 의 import 1줄만.
추적되는 ``CLAUDE.md`` 에는 plugin 이 아무것도 쓰지 않는다.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import persona_injection as pi  # noqa: E402

BODY = "# cpo — Chief Product Officer\n\n본문\n"


def _inline(project: Path, company: str = "LSKun") -> None:
    pi.inject(project, company, "자비스", BODY)


class PointerBlockTests(unittest.TestCase):
    def test_block_has_header_and_single_import(self) -> None:
        block = pi.render_pointer_block("LSKun", "자비스")
        self.assertIn("# CPO Persona — 자비스 of LSKun (auto-injected by LSKunCompanyKit)", block)
        imports = [ln for ln in block.splitlines() if ln.startswith("@")]
        self.assertEqual(imports, ["@~/.lskun-companies/LSKun/hired/cpo.md"])

    def test_block_does_not_carry_persona_body(self) -> None:
        self.assertLess(len(pi.render_pointer_block("LSKun", "자비스")), 900)


class InjectPointerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_fresh_project_writes_only_local_file(self) -> None:
        res = pi.inject_pointer(self.proj, "LSKun", "자비스")
        self.assertEqual(res.action, "created")
        self.assertTrue((self.proj / "CLAUDE.local.md").exists())
        self.assertFalse((self.proj / "CLAUDE.md").exists())
        self.assertEqual(pi.detect_mode(self.proj), "pointer")
        self.assertEqual(pi.extract_company_name(self.proj), "LSKun")

    def test_idempotent(self) -> None:
        pi.inject_pointer(self.proj, "LSKun", "자비스")
        res = pi.inject_pointer(self.proj, "LSKun", "자비스")
        self.assertEqual(res.action, "unchanged")

    def test_preserves_user_content_in_local_file(self) -> None:
        (self.proj / "CLAUDE.local.md").write_text("# 내 개인 메모\n- sandbox URL\n", encoding="utf-8")
        pi.inject_pointer(self.proj, "LSKun", "자비스")
        text = (self.proj / "CLAUDE.local.md").read_text(encoding="utf-8")
        self.assertIn("# 내 개인 메모", text)
        self.assertIn("@~/.lskun-companies/LSKun/hired/cpo.md", text)

    def test_converts_inline_and_keeps_user_content(self) -> None:
        (self.proj / "CLAUDE.md").write_text("# 프로젝트 지침\n\n- 규칙 A\n", encoding="utf-8")
        _inline(self.proj)
        self.assertEqual(pi.detect_mode(self.proj), "inline")

        res = pi.inject_pointer(self.proj, "LSKun", "자비스")

        tracked = (self.proj / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("- 규칙 A", tracked)
        self.assertNotIn("LSKUN-CPO", tracked)
        self.assertTrue(res.removed_inline)
        self.assertIsNotNone(res.backup_path)
        self.assertIn("LSKUN-CPO", res.backup_path.read_text(encoding="utf-8"))
        self.assertEqual(pi.detect_mode(self.proj), "pointer")

    def test_claude_md_that_was_only_persona_is_deleted(self) -> None:
        _inline(self.proj)  # plugin 이 만든 CLAUDE.md — persona 뿐
        res = pi.inject_pointer(self.proj, "LSKun", "자비스")
        self.assertFalse((self.proj / "CLAUDE.md").exists())
        self.assertTrue(res.claude_md_deleted)
        self.assertTrue(res.backup_path.exists())

    def test_company_switch_rewrites_pointer(self) -> None:
        pi.inject_pointer(self.proj, "LSKun", "자비스")
        pi.inject_pointer(self.proj, "OtherCo", "다나")
        self.assertEqual(pi.extract_company_name(self.proj), "OtherCo")
        text = (self.proj / "CLAUDE.local.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("LSKUN-CPO:START"), 1)

    def test_local_file_takes_precedence_for_detection(self) -> None:
        _inline(self.proj, company="OldCo")
        (self.proj / "CLAUDE.local.md").write_text(
            pi.render_pointer_block("NewCo", "다나").lstrip(), encoding="utf-8"
        )
        self.assertEqual(pi.extract_company_name(self.proj), "NewCo")
        self.assertEqual(pi.detect_mode(self.proj), "pointer")

    def test_hand_written_marker_variants_are_recognized_and_removed(self) -> None:
        """실사용에서 발견된 손글씨 변형 — 인식 못 하면 persona 가 추적 파일에 그대로 남는다."""
        for start in ("<!-- LSKUN-CPO:START -->", "<!-- LSKUN-CPO:START company=LSKun -->"):
            with self.subTest(start=start), tempfile.TemporaryDirectory() as td:
                proj = Path(td)
                (proj / "CLAUDE.md").write_text(
                    f"# 앱 지침\n\n- 규칙\n\n{start}\n# cpo — Chief Product Officer\n본문\n"
                    "<!-- LSKUN-CPO:END -->\n\n## 뒤쪽 절\n",
                    encoding="utf-8",
                )
                self.assertEqual(pi.detect_mode(proj), "inline")
                pi.inject_pointer(proj, "LSKun", "자비스")
                tracked = (proj / "CLAUDE.md").read_text(encoding="utf-8")
                self.assertNotIn("LSKUN-CPO", tracked)
                self.assertNotIn("Chief Product Officer", tracked)
                self.assertIn("- 규칙", tracked)
                self.assertIn("## 뒤쪽 절", tracked)
                local = (proj / "CLAUDE.local.md").read_text(encoding="utf-8")
                self.assertIn(pi.PERSONA_MARKER_START, local)  # 쓰는 marker 는 표준형

    def test_existing_backup_is_never_overwritten(self) -> None:
        """기존 ``.lskun.bak`` 은 사용자 원본의 유일한 사본일 수 있다."""
        (self.proj / "CLAUDE.md").write_text("# 지침\n", encoding="utf-8")
        _inline(self.proj)
        precious = self.proj / "CLAUDE.md.lskun.bak"
        precious.write_text("PRECIOUS USER BACKUP", encoding="utf-8")

        res = pi.inject_pointer(self.proj, "LSKun", "자비스")

        self.assertEqual(precious.read_text(encoding="utf-8"), "PRECIOUS USER BACKUP")
        self.assertEqual(res.backup_path.name, "CLAUDE.md.lskun.bak.1")
        self.assertIn("LSKUN-CPO", res.backup_path.read_text(encoding="utf-8"))

    def test_invalid_company_name_rejected(self) -> None:
        """import 경로에 들어가는 값 — 경로 조작 문자 차단."""
        for bad in ("../evil", "a/b", "", "x\ny"):
            with self.assertRaises(ValueError):
                pi.inject_pointer(self.proj, bad, "자비스")


class GitExcludeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.proj)], check=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _status(self) -> str:
        return subprocess.run(
            ["git", "-C", str(self.proj), "status", "--porcelain"],
            capture_output=True, text=True, check=True,
        ).stdout

    def test_local_file_and_backup_hidden_without_touching_gitignore(self) -> None:
        (self.proj / "CLAUDE.md").write_text("# 지침\n", encoding="utf-8")
        _inline(self.proj)
        subprocess.run(["git", "-C", str(self.proj), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.proj), "-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-qm", "init"], check=True,
        )
        res = pi.inject_pointer(self.proj, "LSKun", "자비스")
        self.assertTrue(res.git_excluded)
        self.assertFalse((self.proj / ".gitignore").exists())
        # 추적 파일의 구간 제거만 diff 로 보이고, local 파일·백업은 보이지 않는다.
        self.assertEqual(self._status().split(), ["M", "CLAUDE.md"])

    def test_exclude_written_once(self) -> None:
        pi.inject_pointer(self.proj, "LSKun", "자비스")
        pi.inject_pointer(self.proj, "LSKun", "자비스")
        exclude = (self.proj / ".git" / "info" / "exclude").read_text(encoding="utf-8")
        self.assertEqual(exclude.count("CLAUDE.local.md"), 1)

    def test_parent_repo_exclude_is_never_touched(self) -> None:
        """프로젝트가 상위 저장소의 하위 디렉토리 — 상위 (dotfiles·남의 monorepo) 설정 비접촉."""
        sub = self.proj / "apps" / "mine"
        sub.mkdir(parents=True)
        exclude = self.proj / ".git" / "info" / "exclude"
        before = exclude.read_text(encoding="utf-8") if exclude.exists() else None

        res = pi.inject_pointer(sub, "LSKun", "자비스")

        self.assertFalse(res.git_excluded)
        self.assertTrue(any("상위 저장소" in n for n in res.notes))
        after = exclude.read_text(encoding="utf-8") if exclude.exists() else None
        self.assertEqual(before, after)
        self.assertTrue((sub / "CLAUDE.local.md").exists())

    def test_numbered_backups_are_excluded_too(self) -> None:
        (self.proj / "CLAUDE.md").write_text("# 지침\n", encoding="utf-8")
        _inline(self.proj)
        (self.proj / "CLAUDE.md.lskun.bak").write_text("old", encoding="utf-8")
        pi.inject_pointer(self.proj, "LSKun", "자비스")
        self.assertNotIn(".lskun.bak", self._status())

    def test_non_repo_skips_exclude(self) -> None:
        with tempfile.TemporaryDirectory() as plain:
            res = pi.inject_pointer(Path(plain), "LSKun", "자비스")
            self.assertFalse(res.git_excluded)

    def test_gitfile_worktree_skips_exclude(self) -> None:
        with tempfile.TemporaryDirectory() as wt:
            (Path(wt) / ".git").write_text("gitdir: /somewhere/else\n", encoding="utf-8")
            res = pi.inject_pointer(Path(wt), "LSKun", "자비스")
            self.assertFalse(res.git_excluded)
            self.assertTrue((Path(wt) / "CLAUDE.local.md").exists())


if __name__ == "__main__":
    unittest.main()
