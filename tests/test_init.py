"""lskun_kit.init 단위 테스트.

ADR-0002 §3 의 init 동작을 검증한다:
    - backend 결정 (LSKUN_VAULT 우선)
    - 회사 루트 디렉토리 생성
    - company.md 보존 정책 (이미 있으면 덮어쓰지 않음)
    - CPO / HR 자동 hire + 멱등성 (재실행 시 skip)
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import LocalAdapter, VaultAdapter  # noqa: E402
from lskun_kit.adapters import frontmatter  # noqa: E402
from lskun_kit.init import (  # noqa: E402
    ENV_COMPANY,
    ENV_VAULT,
    LOCAL_COMPANY_DIRNAME,
    detect_backend,
    detect_dual_backend,
    resolve_company_root,
    run,
)
from lskun_kit.persona_injection import (  # noqa: E402
    CLAUDE_MD_FILENAME,
    PERSONA_MARKER_START,
    detect as detect_persona,
)


class DetectDualBackendTests(unittest.TestCase):
    """P33 — Local + Vault 양쪽에 company.md 가 있을 때 감지."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.proj = Path(self.tmp.name) / "proj"
        self.proj.mkdir()
        self.vault = Path(self.tmp.name) / "vault"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _make_company(self, root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "company.md").write_text("---\nname: x\n---\n# x\n", encoding="utf-8")

    def test_local_only_returns_none(self) -> None:
        self._make_company(self.proj / LOCAL_COMPANY_DIRNAME)
        self.assertIsNone(detect_dual_backend(self.proj, env={}))

    def test_vault_only_returns_none(self) -> None:
        self._make_company(self.vault / "03_Companies" / "Acme")
        env = {ENV_VAULT: str(self.vault), ENV_COMPANY: "Acme"}
        self.assertIsNone(detect_dual_backend(self.proj, env=env))

    def test_both_present_returns_paths(self) -> None:
        self._make_company(self.proj / LOCAL_COMPANY_DIRNAME)
        self._make_company(self.vault / "03_Companies" / "Acme")
        env = {ENV_VAULT: str(self.vault), ENV_COMPANY: "Acme"}
        result = detect_dual_backend(self.proj, env=env)
        self.assertIsNotNone(result)
        assert result is not None
        local_co, vault_co = result
        self.assertTrue(local_co.exists())
        self.assertTrue(vault_co.exists())

    def test_vault_env_without_company_returns_none(self) -> None:
        """LSKUN_COMPANY 누락 시 vault 경로 결정 불가 → 안전하게 None."""
        self._make_company(self.proj / LOCAL_COMPANY_DIRNAME)
        env = {ENV_VAULT: str(self.vault)}
        self.assertIsNone(detect_dual_backend(self.proj, env=env))

    def test_run_emits_dual_backend_note(self) -> None:
        """init.run 이 dual-backend 감지 시 InitResult.notes 에 경고 1줄."""
        self._make_company(self.proj / LOCAL_COMPANY_DIRNAME)
        self._make_company(self.vault / "03_Companies" / "Acme")
        env = {ENV_VAULT: str(self.vault), ENV_COMPANY: "Acme"}
        result = run(
            self.proj, company_name="Acme",
            cpo_name="L", hr_name="H",
            inject_persona=False, env=env,
        )
        self.assertTrue(
            any("dual-backend" in n for n in result.notes),
            f"expected dual-backend note, got: {result.notes}",
        )

    def test_dual_backend_with_hand_edited_marker(self) -> None:
        """P43 (#13) — dual-backend + CLAUDE.md marker 손편집 통합 시나리오.

        두 가드 (dual-backend 경고 + marker 백업) 가 동시 발생해도 상호 간섭
        없이 모두 동작해야 한다.
        """
        from lskun_kit.persona_injection import (
            BACKUP_SUFFIX, CLAUDE_MD_FILENAME, inject,
        )
        proj_root = self.proj
        # 1차 박제 후 사용자 손편집
        inject(proj_root, "Acme", "이세근", "# cpo\n\nbody.\n")
        claude_md = proj_root / CLAUDE_MD_FILENAME
        text = claude_md.read_text(encoding="utf-8")
        claude_md.write_text(text.replace("body.", "edited."), encoding="utf-8")

        # dual-backend 환경 셋업 (양쪽 다 company.md)
        self._make_company(proj_root / LOCAL_COMPANY_DIRNAME)
        self._make_company(self.vault / "03_Companies" / "Acme")
        env = {ENV_VAULT: str(self.vault), ENV_COMPANY: "Acme"}

        result = run(
            proj_root, company_name="Acme",
            cpo_name="L", hr_name="H",
            inject_persona=True, env=env,
        )

        # (a) dual-backend 경고 emit
        self.assertTrue(
            any("dual-backend" in n for n in result.notes),
            f"dual-backend note missing: {result.notes}",
        )
        # (b) marker 손편집 백업 생성
        backup = claude_md.with_suffix(claude_md.suffix + BACKUP_SUFFIX)
        self.assertTrue(
            backup.exists(),
            f"marker 손편집 백업이 생성되지 않음: {backup}",
        )
        self.assertIn("edited.", backup.read_text(encoding="utf-8"))


class DetectBackendTests(unittest.TestCase):
    def test_no_env_returns_local(self) -> None:
        backend, root = detect_backend("/tmp/proj", env={})
        self.assertEqual(backend, "local")
        self.assertEqual(root, Path("/tmp/proj"))

    def test_vault_env_returns_vault(self) -> None:
        backend, root = detect_backend(
            "/tmp/proj", env={ENV_VAULT: "/tmp/vault"}
        )
        self.assertEqual(backend, "vault")
        self.assertEqual(root, Path("/tmp/vault"))

    def test_blank_vault_env_falls_back_to_local(self) -> None:
        backend, _ = detect_backend("/tmp/proj", env={ENV_VAULT: "   "})
        self.assertEqual(backend, "local")


class ResolveCompanyRootTests(unittest.TestCase):
    def test_local_uses_dotcompany_subdir(self) -> None:
        backend, name, root = resolve_company_root("/tmp/myproj", env={})
        self.assertEqual(backend, "local")
        self.assertEqual(root, Path("/tmp/myproj") / LOCAL_COMPANY_DIRNAME)
        self.assertEqual(name, "myproj")  # directory name fallback

    def test_vault_requires_company_name(self) -> None:
        with self.assertRaises(ValueError):
            resolve_company_root("/tmp/proj", env={ENV_VAULT: "/tmp/vault"})

    def test_vault_uses_env_company_name(self) -> None:
        backend, name, root = resolve_company_root(
            "/tmp/proj",
            env={ENV_VAULT: "/tmp/vault", ENV_COMPANY: "Acme"},
        )
        self.assertEqual(backend, "vault")
        self.assertEqual(name, "Acme")
        self.assertEqual(root, Path("/tmp/vault/03_Companies/Acme"))

    def test_vault_explicit_arg_overrides_env(self) -> None:
        _, name, _ = resolve_company_root(
            "/tmp/proj",
            company_name="Beta",
            env={ENV_VAULT: "/tmp/vault", ENV_COMPANY: "Acme"},
        )
        self.assertEqual(name, "Beta")

    def test_invalid_company_name_rejected(self) -> None:
        for bad in ("a/b", ".", ".."):
            with self.assertRaises(ValueError):
                resolve_company_root(
                    "/tmp/proj",
                    company_name=bad,
                    env={ENV_VAULT: "/tmp/vault"},
                )


class RunLocalBackendTests(unittest.TestCase):
    def test_creates_company_and_workers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run(Path(tmp), cpo_name="이세근", hr_name="김지혜", env={})

            self.assertEqual(result.backend, "local")
            self.assertTrue(result.company_md_created)
            self.assertEqual(sorted(result.workers_created), ["cpo", "hr-lead"])
            self.assertEqual(result.workers_skipped, [])

            company_md = Path(tmp, LOCAL_COMPANY_DIRNAME, "company.md")
            self.assertTrue(company_md.exists())

            parsed = frontmatter.parse(company_md.read_text(encoding="utf-8"))
            self.assertIn("name", parsed.frontmatter)
            self.assertIn("founded", parsed.frontmatter)

            adapter = LocalAdapter(Path(tmp, LOCAL_COMPANY_DIRNAME))
            workers = adapter.list_workers()
            self.assertEqual(sorted(workers), ["cpo", "hr-lead"])

            cpo = adapter.read_worker("cpo")
            self.assertEqual(cpo.role, "chief-product-officer")
            self.assertEqual(cpo.storage_backend, "local")
            # ADR-0003 §1 — CPO 는 항상 domain="meta"
            self.assertEqual(cpo.domain, "meta")
            # ADR-0004 §5 — display_name 은 사용자 입력 그대로 박제
            self.assertEqual(cpo.display_name, "이세근")
            # ADR-0004 §4 — CPO 는 model 미설정 (메인 세션의 사용자 /model 사용)
            self.assertIsNone(cpo.model)

            hr = adapter.read_worker("hr-lead")
            self.assertEqual(hr.display_name, "김지혜")
            # ADR-0004 §4 — HR Lead 는 default model="sonnet"
            self.assertEqual(hr.model, "sonnet")

    def test_preserves_existing_company_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            company_dir = Path(tmp, LOCAL_COMPANY_DIRNAME)
            company_dir.mkdir()
            original = "---\nname: PreExisting\n---\n\n# original content\n"
            (company_dir / "company.md").write_text(original, encoding="utf-8")

            result = run(Path(tmp), cpo_name="이세근", hr_name="김지혜", env={})
            self.assertFalse(result.company_md_created)
            self.assertEqual(
                (company_dir / "company.md").read_text(encoding="utf-8"),
                original,
            )

    def test_idempotent_rerun_skips_existing_workers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run(Path(tmp), cpo_name="이세근", hr_name="김지혜", env={})
            second = run(Path(tmp), cpo_name="이세근", hr_name="김지혜", env={})
            self.assertEqual(second.workers_created, [])
            self.assertEqual(sorted(second.workers_skipped), ["cpo", "hr-lead"])

    def test_init_rejects_missing_cpo_name(self) -> None:
        # ADR-0004 §5 — CPO 이름은 사용자 명시 입력 필수 (자동 생성 금지)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as ctx:
                run(Path(tmp), hr_name="김지혜", env={})
            self.assertIn("cpo", str(ctx.exception).lower())

    def test_init_rejects_missing_hr_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as ctx:
                run(Path(tmp), cpo_name="이세근", env={})
            self.assertIn("hr-lead", str(ctx.exception).lower())

    def test_injects_cpo_persona_into_claude_md(self) -> None:
        # ADR-0004 §1 — init 가 project_root 의 CLAUDE.md 에 CPO persona 박제
        with tempfile.TemporaryDirectory() as tmp:
            result = run(Path(tmp), cpo_name="이세근", hr_name="김지혜", env={})
            self.assertEqual(result.persona_action, "created")
            self.assertTrue(detect_persona(Path(tmp)))
            content = (Path(tmp) / CLAUDE_MD_FILENAME).read_text(encoding="utf-8")
            self.assertIn(PERSONA_MARKER_START, content)
            self.assertIn("이세근", content)

    def test_inject_persona_can_be_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run(
                Path(tmp),
                cpo_name="이세근",
                hr_name="김지혜",
                inject_persona=False,
                env={},
            )
            self.assertEqual(result.persona_action, "skipped")
            self.assertFalse(detect_persona(Path(tmp)))

    def test_persona_reinject_preserves_user_claude_md_outside_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # 사용자가 먼저 CLAUDE.md 작성
            user_text = "# Project\n\n사용자 정의 가이드.\n"
            (Path(tmp) / CLAUDE_MD_FILENAME).write_text(user_text, encoding="utf-8")
            run(Path(tmp), cpo_name="이세근", hr_name="김지혜", env={})
            content = (Path(tmp) / CLAUDE_MD_FILENAME).read_text(encoding="utf-8")
            # 사용자 본문 보존 + persona 추가
            self.assertIn("사용자 정의 가이드.", content)
            self.assertIn(PERSONA_MARKER_START, content)

    def test_company_md_records_domain(self) -> None:
        # ADR-0003 — company.md frontmatter 에 domain 박제
        with tempfile.TemporaryDirectory() as tmp:
            run(
                Path(tmp),
                domain="의료 SaaS",
                cpo_name="이세근",
                hr_name="김지혜",
                env={},
            )
            company_md = Path(tmp, LOCAL_COMPANY_DIRNAME, "company.md")
            parsed = frontmatter.parse(company_md.read_text(encoding="utf-8"))
            self.assertEqual(parsed.frontmatter.get("domain"), "의료 SaaS")

    def test_company_md_empty_domain_when_not_specified(self) -> None:
        # ADR-0003 — domain 누락은 doctor 가 경고할 영역. init 는 강제하지 않음.
        with tempfile.TemporaryDirectory() as tmp:
            run(Path(tmp), cpo_name="이세근", hr_name="김지혜", env={})
            company_md = Path(tmp, LOCAL_COMPANY_DIRNAME, "company.md")
            parsed = frontmatter.parse(company_md.read_text(encoding="utf-8"))
            self.assertIn("domain", parsed.frontmatter)
            self.assertEqual(parsed.frontmatter["domain"], "")


class RunVaultBackendTests(unittest.TestCase):
    def test_creates_vault_company_dir_and_workers(self) -> None:
        with tempfile.TemporaryDirectory() as vault:
            result = run(
                Path("/nonexistent-project-root"),
                company_name="Acme",
                one_liner="Test compliance agents",
                cpo_name="이세근",
                hr_name="김지혜",
                env={ENV_VAULT: vault},
            )
            self.assertEqual(result.backend, "vault")
            self.assertEqual(result.company_name, "Acme")
            company_root = Path(vault, "03_Companies", "Acme")
            self.assertTrue(company_root.is_dir())
            self.assertTrue((company_root / "company.md").exists())

            adapter = VaultAdapter(vault, "Acme")
            cpo = adapter.read_worker("cpo")
            self.assertEqual(cpo.storage_backend, "vault")
            self.assertEqual(adapter.read_company().name, "Acme")

    def test_one_liner_lands_in_company_body(self) -> None:
        with tempfile.TemporaryDirectory() as vault:
            run(
                Path("/p"),
                company_name="Beta",
                one_liner="hello world",
                cpo_name="이세근",
                hr_name="김지혜",
                env={ENV_VAULT: vault},
            )
            body = Path(vault, "03_Companies", "Beta", "company.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("hello world", body)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
