"""ADR-0022 — 외주 setup 자동 시퀀스 marker 파일 schema + lifecycle 테스트."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import external_setup_state as ess  # noqa: E402


class StepEnumTest(unittest.TestCase):
    """STEP_ENUM 은 ADR-0022 의 7개 step allowlist 를 정확히 박제."""

    def test_step_enum_has_seven_values(self):
        self.assertEqual(len(ess.STEP_ENUM), 7)

    def test_step_enum_contents(self):
        expected = {
            "init",
            "domain_assessment",
            "hire_domain_worker",
            "fetch_advice",
            "synthesize_brief",
            "dispatch_hr_lead",
            "finalize",
        }
        self.assertEqual(set(ess.STEP_ENUM), expected)


class FromDictValidationTest(unittest.TestCase):
    """from_dict 는 enum / 이름 / tzinfo / 타입 검증을 모두 한다."""

    def _base(self, **overrides):
        data = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "company": "acme",
            "project": "redteam-q2",
            "current_step": "init",
            "next_action": "domain_assessment",
            "step_count_so_far": 1,
            "max_step_count": 10,
        }
        data.update(overrides)
        return data

    def test_valid_dict_parses(self):
        state = ess.ExternalSetupState.from_dict(self._base())
        self.assertEqual(state.company, "acme")
        self.assertEqual(state.project, "redteam-q2")
        self.assertEqual(state.current_step, "init")

    def test_invalid_step_rejected(self):
        with self.assertRaises(ValueError):
            ess.ExternalSetupState.from_dict(self._base(current_step="nonsense"))

    def test_invalid_company_rejected(self):
        with self.assertRaises(ValueError):
            ess.ExternalSetupState.from_dict(self._base(company="../etc"))

    def test_invalid_project_rejected(self):
        with self.assertRaises(ValueError):
            ess.ExternalSetupState.from_dict(self._base(project="a..b"))

    def test_naive_datetime_rejected(self):
        naive = datetime.now().isoformat()
        with self.assertRaises(ValueError):
            ess.ExternalSetupState.from_dict(self._base(started_at=naive))

    def test_step_count_type_check(self):
        with self.assertRaises(ValueError):
            ess.ExternalSetupState.from_dict(self._base(step_count_so_far="1"))

    def test_missing_field_rejected(self):
        data = self._base()
        del data["next_action"]
        with self.assertRaises(ValueError):
            ess.ExternalSetupState.from_dict(data)


class StartFinalizeTest(unittest.TestCase):
    """start → marker 생성, finalize → marker 삭제 (idempotent)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.patcher = mock.patch.object(Path, "home", return_value=self.home)
        self.patcher.start()
        (self.home / ".lskun-companies" / "acme").mkdir(parents=True)

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def test_start_creates_marker(self):
        state = ess.start("acme", "redteam-q2")
        path = ess.marker_path("acme")
        self.assertTrue(path.exists())
        self.assertEqual(state.current_step, "init")
        self.assertEqual(state.step_count_so_far, 1)
        self.assertEqual(state.company, "acme")
        self.assertEqual(state.project, "redteam-q2")

    def test_start_when_live_marker_raises(self):
        ess.start("acme", "redteam-q2")
        with self.assertRaises(ValueError):
            ess.start("acme", "redteam-q2")

    def test_start_clears_stale_marker(self):
        ess.start("acme", "redteam-q2")
        path = ess.marker_path("acme")
        data = json.loads(path.read_text(encoding="utf-8"))
        past = datetime.now(timezone.utc) - timedelta(seconds=ess.STALE_SECONDS + 60)
        data["started_at"] = past.isoformat()
        path.write_text(json.dumps(data), encoding="utf-8")
        # stale 은 자동 정리 후 새로 start 가능
        state = ess.start("acme", "redteam-q2")
        self.assertEqual(state.current_step, "init")

    def test_finalize_removes_marker(self):
        ess.start("acme", "redteam-q2")
        ess.finalize("acme")
        self.assertFalse(ess.marker_path("acme").exists())

    def test_finalize_idempotent(self):
        ess.finalize("acme")  # 부재해도 raise 안 함
        ess.finalize("acme")


class AdvanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.patcher = mock.patch.object(Path, "home", return_value=self.home)
        self.patcher.start()
        (self.home / ".lskun-companies" / "acme").mkdir(parents=True)

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def test_advance_increments_step(self):
        ess.start("acme", "redteam-q2")
        state = ess.advance("acme", "domain_assessment", "hire_domain_worker")
        self.assertEqual(state.current_step, "domain_assessment")
        self.assertEqual(state.step_count_so_far, 2)
        self.assertEqual(state.next_action, "hire_domain_worker")

    def test_advance_invalid_step_rejected(self):
        ess.start("acme", "redteam-q2")
        with self.assertRaises(ValueError):
            ess.advance("acme", "nonsense_step", "x")

    def test_advance_without_marker_raises(self):
        with self.assertRaises(ValueError):
            ess.advance("acme", "domain_assessment", "x")


class ReadStaleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.patcher = mock.patch.object(Path, "home", return_value=self.home)
        self.patcher.start()
        (self.home / ".lskun-companies" / "acme").mkdir(parents=True)

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def test_read_missing_returns_none(self):
        self.assertIsNone(ess.read("acme"))

    def test_read_malformed_returns_none_and_unlinks(self):
        path = ess.marker_path("acme")
        path.write_text("not-json", encoding="utf-8")
        self.assertIsNone(ess.read("acme"))
        self.assertFalse(path.exists())

    def test_read_stale_returns_none_and_unlinks(self):
        ess.start("acme", "redteam-q2")
        path = ess.marker_path("acme")
        data = json.loads(path.read_text(encoding="utf-8"))
        past = datetime.now(timezone.utc) - timedelta(seconds=ess.STALE_SECONDS + 60)
        data["started_at"] = past.isoformat()
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertIsNone(ess.read("acme"))
        self.assertFalse(path.exists())

    def test_read_exhausted_returns_none_and_unlinks(self):
        ess.start("acme", "redteam-q2")
        path = ess.marker_path("acme")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["step_count_so_far"] = data["max_step_count"] + 1
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertIsNone(ess.read("acme"))
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
