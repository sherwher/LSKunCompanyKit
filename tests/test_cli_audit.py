"""ADR-0027 (P130) — 결재 기록 진입점 ``lskun-audit record`` 회귀 가드.

기록 절차의 마찰 (12필드 inline Python) 이 빙의 건 기록 누락과 JSONL 손기록을
낳았다. 진입점은 입력을 3개로 줄이되 기존 ``AuditEntry`` 검증을 그대로 통과시킨다.
"""

from __future__ import annotations

import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import date as _date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import cli_audit  # noqa: E402
from lskun_kit.templates import (  # noqa: E402
    iter_default_workers,
    render_default_worker,
)

BIN = ROOT / "bin" / "lskun-audit"


def _init_company(tmp: Path) -> Path:
    co_root = tmp / "AcmeCo"
    hired = co_root / "hired"
    hired.mkdir(parents=True)
    (co_root / "company.md").write_text(
        "---\nname: AcmeCo\nfounded: 2026-09-17\ndomain: medical-saas\n---\n# AcmeCo\n",
        encoding="utf-8",
    )
    for worker_name, role, template_filename, default_model in iter_default_workers():
        text = render_default_worker(
            name=worker_name,
            role=role,
            template_filename=template_filename,
            storage_backend="local",
            display_name="이세근" if worker_name == "cpo" else "김지혜",
            hired_at=_date(2026, 9, 17),
            model=default_model,
            synced_from="lskun-kit@test",
        )
        (hired / f"{worker_name}.md").write_text(text, encoding="utf-8")
    (hired / "backend-engineer.md").write_text(
        "---\nname: backend-engineer\nrole: backend-engineer\ndomain: medical-saas\n"
        "display_name: 박서버\nhired_at: 2026-09-17\nstorage_backend: local\n---\n# JD\n",
        encoding="utf-8",
    )
    return co_root


def _run(argv: list[str], co_root: Path | None) -> tuple[int, str, str]:
    env = {"LSKUN_SSOT_ROOT": str(co_root)} if co_root else {}
    with patch.dict(os.environ, env, clear=True), \
         patch("sys.stdout", io.StringIO()) as out, \
         patch("sys.stderr", io.StringIO()) as err:
        try:
            rc = cli_audit.main(argv)
        except SystemExit as e:  # argparse 오류
            rc = int(e.code or 0)
    return rc, out.getvalue(), err.getvalue()


def _entries(co_root: Path) -> list[dict]:
    path = co_root / ".audit" / "decisions.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class RecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.co = _init_company(Path(self.tmp.name))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_minimal_record(self) -> None:
        rc, out, _ = _run(
            ["record", "--worker", "backend-engineer", "--verdict", "approved",
             "--reason", "요구 3건 대응 확인, 테스트 통과 출력 확인"],
            self.co,
        )
        self.assertEqual(rc, 0)
        (entry,) = _entries(self.co)
        self.assertEqual(entry["company"], "AcmeCo")
        self.assertEqual(entry["worker"], "backend-engineer")
        self.assertEqual(entry["domain"], "medical-saas")  # 워커 frontmatter 에서 자동 해소
        self.assertEqual(entry["verdict"], "approved")
        self.assertEqual(entry["rounds"], 1)
        self.assertEqual(entry["model"], "inherit")
        self.assertFalse(entry["auto_hired"])
        self.assertEqual(len(entry["request_id"]), 32)
        self.assertTrue(entry["ts"])
        self.assertIn(entry["request_id"], out)

    def test_legacy_score_fields_filled_without_schema_change(self) -> None:
        """ADR-0027 D2 — reflection 시절 잔재 필드는 기본값, schema 불변."""
        _run(["record", "--worker", "cpo", "--verdict", "approved", "--reason", "r"], self.co)
        (entry,) = _entries(self.co)
        self.assertEqual(entry["first_pass_score"], 0)
        self.assertIsNone(entry["final_score"])

    def test_embody_flag_prefixes_reason(self) -> None:
        _run(["record", "--worker", "backend-engineer", "--verdict", "approved",
              "--reason", "API 스키마 직접 수정", "--embody"], self.co)
        (entry,) = _entries(self.co)
        self.assertEqual(entry["reason"], "embody: API 스키마 직접 수정")

    def test_embody_flag_does_not_double_prefix(self) -> None:
        _run(["record", "--worker", "backend-engineer", "--verdict", "approved",
              "--reason", "embody: 이미 접두 있음", "--embody"], self.co)
        (entry,) = _entries(self.co)
        self.assertEqual(entry["reason"], "embody: 이미 접두 있음")

    def test_request_id_reuse_for_rework_rounds(self) -> None:
        _run(["record", "--worker", "backend-engineer", "--verdict", "rework",
              "--reason", "R1 누락", "--request-id", "a" * 32], self.co)
        _run(["record", "--worker", "backend-engineer", "--verdict", "approved",
              "--reason", "보완 확인", "--request-id", "a" * 32, "--rounds", "2"], self.co)
        first, second = _entries(self.co)
        self.assertEqual(first["request_id"], second["request_id"])
        self.assertEqual(second["rounds"], 2)

    def test_optional_flags(self) -> None:
        _run(["record", "--worker", "backend-engineer", "--verdict", "approved",
              "--reason", "r", "--model", "opus", "--auto-hired"], self.co)
        (entry,) = _entries(self.co)
        self.assertEqual(entry["model"], "opus")
        self.assertTrue(entry["auto_hired"])

    def test_append_only(self) -> None:
        for i in range(3):
            _run(["record", "--worker", "cpo", "--verdict", "approved", "--reason", f"r{i}"], self.co)
        self.assertEqual([e["reason"] for e in _entries(self.co)], ["r0", "r1", "r2"])


class RejectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.co = _init_company(Path(self.tmp.name))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_invalid_verdict_rejected_without_write(self) -> None:
        rc, _, _ = _run(["record", "--worker", "cpo", "--verdict", "great", "--reason", "r"], self.co)
        self.assertNotEqual(rc, 0)
        self.assertEqual(_entries(self.co), [])

    def test_unknown_worker_rejected_without_write(self) -> None:
        """ADR-0023 — 파일 없는 워커에 대한 audit (유령참조) 금지."""
        rc, _, err = _run(["record", "--worker", "ghost", "--verdict", "approved", "--reason", "r"], self.co)
        self.assertNotEqual(rc, 0)
        self.assertIn("ghost", err)
        self.assertEqual(_entries(self.co), [])

    def test_blank_reason_rejected(self) -> None:
        rc, _, _ = _run(["record", "--worker", "cpo", "--verdict", "approved", "--reason", "  "], self.co)
        self.assertNotEqual(rc, 0)
        self.assertEqual(_entries(self.co), [])

    def test_multiline_reason_flattened(self) -> None:
        """JSONL 1줄 원칙 — 개행은 직렬화로 이스케이프되어 1줄을 유지한다."""
        rc, _, _ = _run(["record", "--worker", "cpo", "--verdict", "approved",
                         "--reason", "첫 줄\n둘째 줄"], self.co)
        self.assertEqual(rc, 0)
        raw = (self.co / ".audit" / "decisions.jsonl").read_text(encoding="utf-8")
        self.assertEqual(len(raw.splitlines()), 1)

    def test_no_active_company(self) -> None:
        with tempfile.TemporaryDirectory() as empty:
            cwd = os.getcwd()
            os.chdir(empty)
            try:
                rc, _, err = _run(["record", "--worker", "cpo", "--verdict", "approved", "--reason", "r"], None)
            finally:
                os.chdir(cwd)
        self.assertNotEqual(rc, 0)
        self.assertIn("회사", err)


class SurfaceTests(unittest.TestCase):
    def test_only_record_subcommand(self) -> None:
        """ADR-0027 D5 — 조회·집계 하위 명령 금지 (ADR-0006 KPI 금지)."""
        self.assertEqual(cli_audit.SUBCOMMANDS, ("record",))

    def test_bin_is_executable_and_runs(self) -> None:
        self.assertTrue(BIN.exists())
        self.assertTrue(BIN.stat().st_mode & stat.S_IXUSR, "bin/lskun-audit 실행 권한 없음")
        with tempfile.TemporaryDirectory() as td:
            co = _init_company(Path(td))
            proc = subprocess.run(
                [str(BIN), "record", "--worker", "cpo", "--verdict", "approved",
                 "--reason", "bin 경유 실행", "--embody"],
                env={"LSKUN_SSOT_ROOT": str(co), "PATH": os.environ.get("PATH", "")},
                capture_output=True, text=True, cwd=td,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            (entry,) = _entries(co)
            self.assertEqual(entry["reason"], "embody: bin 경유 실행")


if __name__ == "__main__":
    unittest.main()
