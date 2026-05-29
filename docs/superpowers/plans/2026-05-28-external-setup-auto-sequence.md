# 외주 setup 자동 시퀀스 (ADR-0022) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/lskun-kit:external setup` multi-step 시퀀스의 중간 멈춤을 plugin 차원에서 결정론적으로 차단한다. PostToolUse + Stop hook 이중 강제 (push) + commands/external.md 본문 강화 (pull) 양 갈래.

**Architecture:** marker 파일(`.external-setup.json`) 존재 시에만 두 hook 동작. enum allowlist 로 prompt 인젝션 표면 차단, `stop_hook_active=true` + wall-clock 24h TTL 로 lockup 방지. hook 으로 못 푸는 `/clear` 강제 break 는 문서 안내로 보완.

**Tech Stack:** Python 3 stdlib only (json, pathlib, dataclasses, datetime, fcntl, unittest). 외부 의존성 0 (ADR-0009).

**Spec:** `docs/superpowers/specs/2026-05-28-external-setup-auto-sequence-design.md`

---

## File Structure

신규/수정 파일과 책임:

- **Create** `src/lskun_kit/external_setup_state.py` — marker 파일 schema (dataclass) + start/advance/finalize + stale TTL + atomic write. paths.py 와 동급 단일 진입점.
- **Create** `src/lskun_kit/hooks/post_tool_use_external.py` — PostToolUse:Task hook. marker 존재 시 다음 step 안내 stdout 주입. enum 검증 통과만.
- **Create** `src/lskun_kit/hooks/stop_external.py` — Stop hook. `stop_hook_active=true` 우선 통과, 그 외엔 marker 살아있으면 `decision="block"` + reason.
- **Modify** `hooks/hooks.json` — PostToolUse:Task / Stop 등록.
- **Modify** `commands/external.md` — setup 시퀀스에 "1턴 완수 + /clear 안내" 명시, cancel 서브명령 본문 추가.
- **Modify** `src/lskun_kit/sync.py` — `.external-setup.json` 발견 시 명시 confirm (security C1).
- **Modify** `src/lskun_kit/external_diagnostics.py` 또는 신규 — doctor [33] stale marker + [34] zshrc env grep.
- **Modify** ADR / 문서 — adr-index, forbidden-history, CLAUDE.md, plugin.json 0.28.0.
- **Test** 신규 5개 + manifest 갱신:
  - `tests/test_external_setup_state.py`
  - `tests/test_hooks_post_tool_use_external.py`
  - `tests/test_hooks_stop_external.py`
  - `tests/test_external_doctor_setup.py`
  - `tests/test_hooks_manifest.py` 확장 (`test_reflection_hooks_removed` → 외주 setup hook 허용으로 의도 명시)

순서: state 모듈 → hook 들 → manifest → command 본문 → sync 가드 → doctor → 문서.

**테스트 실행 규약:** `cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit && python3 -m unittest discover -s tests -p "<file>.py" -v`. 기존 P120 conventions 그대로.

---

## Task 1: `external_setup_state.py` — marker 파일 schema + start/finalize

**Files:**
- Create: `src/lskun_kit/external_setup_state.py`
- Test: `tests/test_external_setup_state.py`

dataclass + enum allowlist + atomic write + stale TTL. session.py 의 패턴(advisory flock, STALE_SECONDS) 재사용.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_external_setup_state.py` (기존 tests/test_external.py 의 sys.path bootstrap preamble 그대로):

```python
"""ADR-0022 — external_setup_state marker schema + lifecycle 테스트."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import external_setup_state as state  # noqa: E402
from lskun_kit import paths  # noqa: E402


class StepEnumTest(unittest.TestCase):
    def test_known_steps_allowed(self):
        for s in ("init", "domain_assessment", "hire_domain_worker",
                  "fetch_advice", "synthesize_brief", "dispatch_hr_lead",
                  "finalize"):
            self.assertIn(s, state.STEP_ENUM)

    def test_unknown_step_rejected(self):
        self.assertNotIn("evil_step", state.STEP_ENUM)


class FromDictValidationTest(unittest.TestCase):
    def _valid(self, **overrides):
        base = {
            "started_at": "2026-05-28T14:00:00+00:00",
            "company": "Acme",
            "project": "lskun-kit",
            "current_step": "fetch_advice",
            "next_action": "synthesize_brief",
            "step_count_so_far": 2,
            "max_step_count": 10,
        }
        base.update(overrides)
        return base

    def test_valid_dict_parses(self):
        s = state.ExternalSetupState.from_dict(self._valid())
        self.assertEqual(s.company, "Acme")
        self.assertEqual(s.current_step, "fetch_advice")

    def test_invalid_step_rejected(self):
        with self.assertRaises(ValueError):
            state.ExternalSetupState.from_dict(self._valid(current_step="evil"))

    def test_invalid_next_action_rejected(self):
        with self.assertRaises(ValueError):
            state.ExternalSetupState.from_dict(self._valid(next_action="rm -rf"))

    def test_invalid_company_rejected(self):
        with self.assertRaises(ValueError):
            state.ExternalSetupState.from_dict(self._valid(company=".."))

    def test_invalid_project_rejected(self):
        with self.assertRaises(ValueError):
            state.ExternalSetupState.from_dict(self._valid(project="a..b"))


class StartFinalizeTest(unittest.TestCase):
    def _patch_home(self, tmp):
        return mock.patch.object(paths.Path, "home", return_value=Path(tmp))

    def test_start_writes_marker(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            state.start("Acme", "proj")
            marker = state.marker_path("Acme")
            self.assertTrue(marker.exists())
            data = json.loads(marker.read_text())
            self.assertEqual(data["current_step"], "init")

    def test_start_rejects_fresh_marker_if_alive(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            state.start("Acme", "proj")
            # 다시 start — 살아있으면 ValueError
            with self.assertRaises(ValueError):
                state.start("Acme", "proj")

    def test_start_replaces_stale_marker(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            # 30시간 전 marker 수동 박제
            marker = state.marker_path("Acme")
            old = datetime.now(timezone.utc) - timedelta(hours=30)
            marker.write_text(json.dumps({
                "started_at": old.isoformat(),
                "company": "Acme", "project": "old-proj",
                "current_step": "init", "next_action": "domain_assessment",
                "step_count_so_far": 0, "max_step_count": 10,
            }))
            # stale 이면 자동 정리 후 새 박제 성공
            state.start("Acme", "proj")
            data = json.loads(marker.read_text())
            self.assertEqual(data["project"], "proj")

    def test_finalize_unlinks(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            state.start("Acme", "proj")
            state.finalize("Acme")
            self.assertFalse(state.marker_path("Acme").exists())

    def test_finalize_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            state.finalize("Acme")  # 부재 시도 → no-op
            state.start("Acme", "proj")
            state.finalize("Acme")
            state.finalize("Acme")  # 다시 호출도 안전


class AdvanceTest(unittest.TestCase):
    def _patch_home(self, tmp):
        return mock.patch.object(paths.Path, "home", return_value=Path(tmp))

    def test_advance_updates_step(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            state.start("Acme", "proj")
            state.advance("Acme", "fetch_advice", "synthesize_brief")
            data = json.loads(state.marker_path("Acme").read_text())
            self.assertEqual(data["current_step"], "fetch_advice")
            self.assertEqual(data["next_action"], "synthesize_brief")
            self.assertGreaterEqual(data["step_count_so_far"], 1)

    def test_advance_rejects_invalid_step(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            state.start("Acme", "proj")
            with self.assertRaises(ValueError):
                state.advance("Acme", "evil", "synthesize_brief")


class ReadStaleTest(unittest.TestCase):
    def _patch_home(self, tmp):
        return mock.patch.object(paths.Path, "home", return_value=Path(tmp))

    def test_read_returns_none_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            self.assertIsNone(state.read("Acme"))

    def test_read_returns_state(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            state.start("Acme", "proj")
            s = state.read("Acme")
            self.assertIsNotNone(s)
            self.assertEqual(s.project, "proj")

    def test_read_auto_unlinks_stale(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            marker = state.marker_path("Acme")
            old = datetime.now(timezone.utc) - timedelta(hours=30)
            marker.write_text(json.dumps({
                "started_at": old.isoformat(),
                "company": "Acme", "project": "p",
                "current_step": "init", "next_action": "domain_assessment",
                "step_count_so_far": 0, "max_step_count": 10,
            }))
            self.assertIsNone(state.read("Acme"))
            self.assertFalse(marker.exists())  # auto-unlink

    def test_read_auto_unlinks_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            marker = state.marker_path("Acme")
            marker.write_text("{ not valid json")
            self.assertIsNone(state.read("Acme"))
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit && python3 -m unittest discover -s tests -p "test_external_setup_state.py" -v`
Expected: `ModuleNotFoundError: lskun_kit.external_setup_state`.

- [ ] **Step 3: 구현**

`src/lskun_kit/external_setup_state.py`:

```python
"""외주 setup marker 파일 schema + lifecycle — ADR-0022.

`.external-setup.json` 의 단일 진입점. enum allowlist 로 prompt 인젝션 표면을 막고,
wall-clock 24h TTL 로 영구 stuck 을 방지한다. session.py 의 패턴(atomic write,
STALE_SECONDS) 을 재사용한다.

ADR-0009: stdlib only.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lskun_kit import external, paths

#: marker 파일 이름. 회사 SSOT 하위.
MARKER_FILENAME = ".external-setup.json"

#: 24h TTL — session.STALE_SESSION_SECONDS 와 동일 (재해석 가능).
STALE_SECONDS = 24 * 60 * 60

#: max step count 가드 (폭주 방지).
MAX_STEP_COUNT_DEFAULT = 10

#: step enum allowlist. raw string 박제 금지 — sync-in 인젝션 차단.
STEP_ENUM = frozenset({
    "init",
    "domain_assessment",
    "hire_domain_worker",
    "fetch_advice",
    "synthesize_brief",
    "dispatch_hr_lead",
    "finalize",
})


@dataclass(frozen=True)
class ExternalSetupState:
    started_at: datetime
    company: str
    project: str
    current_step: str
    next_action: str
    step_count_so_far: int
    max_step_count: int = MAX_STEP_COUNT_DEFAULT

    @classmethod
    def from_dict(cls, data: dict) -> "ExternalSetupState":
        """검증 통과 시 instance. invalid → ValueError."""
        if not isinstance(data, dict):
            raise ValueError("marker data must be dict")

        # 1. enum 검증 (인젝션 차단의 핵심)
        cs = data.get("current_step")
        na = data.get("next_action")
        if cs not in STEP_ENUM:
            raise ValueError(f"invalid current_step: {cs!r}")
        if na not in STEP_ENUM:
            raise ValueError(f"invalid next_action: {na!r}")

        # 2. 회사/프로젝트 이름 검증 (기존 검증 함수 재사용)
        company = data.get("company")
        project = data.get("project")
        paths.validate_company_name(company)
        external.validate_project_name(project)

        # 3. 타입 검증
        try:
            sa = datetime.fromisoformat(data["started_at"])
        except (TypeError, ValueError, KeyError) as e:
            raise ValueError(f"invalid started_at: {e}")
        if sa.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")

        sc = data.get("step_count_so_far")
        mc = data.get("max_step_count", MAX_STEP_COUNT_DEFAULT)
        if not isinstance(sc, int) or sc < 0:
            raise ValueError(f"invalid step_count_so_far: {sc!r}")
        if not isinstance(mc, int) or mc < 1:
            raise ValueError(f"invalid max_step_count: {mc!r}")

        return cls(
            started_at=sa, company=company, project=project,
            current_step=cs, next_action=na,
            step_count_so_far=sc, max_step_count=mc,
        )

    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at.isoformat(),
            "company": self.company,
            "project": self.project,
            "current_step": self.current_step,
            "next_action": self.next_action,
            "step_count_so_far": self.step_count_so_far,
            "max_step_count": self.max_step_count,
        }

    def is_stale(self, now: "datetime | None" = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return (now - self.started_at).total_seconds() > STALE_SECONDS

    def is_exhausted(self) -> bool:
        return self.step_count_so_far >= self.max_step_count


def marker_path(company: str) -> Path:
    """``~/.lskun-companies/<company>/.external-setup.json`` 절대경로."""
    return paths.company_root(company) / MARKER_FILENAME


def _atomic_write(path: Path, data: dict) -> None:
    """tmp + os.replace 로 atomic write. session.py 패턴."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def read(company: str) -> "ExternalSetupState | None":
    """marker 읽기. malformed/stale/exhausted 면 auto-unlink + None."""
    p = marker_path(company)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        s = ExternalSetupState.from_dict(raw)
    except (json.JSONDecodeError, ValueError, OSError):
        p.unlink(missing_ok=True)
        return None
    if s.is_stale() or s.is_exhausted():
        p.unlink(missing_ok=True)
        return None
    return s


def start(company: str, project: str) -> ExternalSetupState:
    """marker 시작. 살아있는 marker 가 있으면 ValueError (stale 은 자동 정리 후 박제)."""
    existing = read(company)  # stale 이면 자동 unlink
    if existing is not None:
        raise ValueError(
            f"external setup already in progress for {company} "
            f"(project={existing.project!r}). cancel 하거나 wait."
        )
    s = ExternalSetupState(
        started_at=datetime.now(timezone.utc),
        company=company, project=project,
        current_step="init",
        next_action="domain_assessment",
        step_count_so_far=0,
        max_step_count=MAX_STEP_COUNT_DEFAULT,
    )
    _atomic_write(marker_path(company), s.to_dict())
    return s


def advance(company: str, current_step: str, next_action: str) -> ExternalSetupState:
    """현재 marker 갱신. enum 위반/marker 부재 시 ValueError."""
    s = read(company)
    if s is None:
        raise ValueError(f"no active external setup for {company}")
    if current_step not in STEP_ENUM or next_action not in STEP_ENUM:
        raise ValueError(f"invalid step: {current_step!r}/{next_action!r}")
    new = ExternalSetupState(
        started_at=s.started_at,
        company=s.company, project=s.project,
        current_step=current_step,
        next_action=next_action,
        step_count_so_far=s.step_count_so_far + 1,
        max_step_count=s.max_step_count,
    )
    _atomic_write(marker_path(company), new.to_dict())
    return new


def finalize(company: str) -> None:
    """marker 정리. 부재 시 no-op."""
    marker_path(company).unlink(missing_ok=True)


__all__ = [
    "MARKER_FILENAME",
    "STALE_SECONDS",
    "MAX_STEP_COUNT_DEFAULT",
    "STEP_ENUM",
    "ExternalSetupState",
    "marker_path",
    "read",
    "start",
    "advance",
    "finalize",
]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit && python3 -m unittest discover -s tests -p "test_external_setup_state.py" -v`
Expected: 전부 PASS (대략 15 tests).

- [ ] **Step 5: 전체 회귀**

Run: `cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit && python3 -m unittest discover -s tests -v 2>&1 | tail -3`
Expected: 전체 OK (기존 363 + 신규).

- [ ] **Step 6: 커밋**

```bash
git add src/lskun_kit/external_setup_state.py tests/test_external_setup_state.py
git commit -m "feat(P121): external_setup_state — marker schema + start/advance/finalize + TTL (ADR-0022)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: PostToolUse hook — 다음 step push (soft hint)

**Files:**
- Create: `src/lskun_kit/hooks/post_tool_use_external.py`
- Test: `tests/test_hooks_post_tool_use_external.py`

평가 순서는 spec §5.1. enum allowlist 통과만 stdout 출력 — sync-in 인젝션 차단.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_hooks_post_tool_use_external.py`:

```python
"""ADR-0022 — PostToolUse:Task hook 테스트."""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import external_setup_state as state  # noqa: E402
from lskun_kit import paths  # noqa: E402
from lskun_kit.hooks import post_tool_use_external as hook  # noqa: E402


def _run(stdin_text: str, env: dict[str, str]) -> tuple[str, str, int]:
    with patch.dict(os.environ, env, clear=True), \
         patch("sys.stdin", io.StringIO(stdin_text)), \
         patch("sys.stdout", io.StringIO()) as out, \
         patch("sys.stderr", io.StringIO()) as err:
        rc = hook.main([])
    return out.getvalue(), err.getvalue(), rc


def _task_payload() -> str:
    return json.dumps({"tool_name": "Task"})


class NonTaskToolTest(unittest.TestCase):
    def test_non_task_no_output(self):
        out, _, rc = _run(json.dumps({"tool_name": "Read"}), {})
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")


class EscapeHatchTest(unittest.TestCase):
    def test_env_allow_halt_skips(self):
        out, err, rc = _run(
            _task_payload(),
            {"LSKUN_ALLOW_EXTERNAL_HALT": "1"},
        )
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")
        self.assertIn("LSKUN_ALLOW_EXTERNAL_HALT", err)


class MarkerAbsentTest(unittest.TestCase):
    def test_no_marker_no_output(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(paths.Path, "home", return_value=Path(tmp)):
            paths.company_root("Acme").mkdir(parents=True)
            out, _, rc = _run(
                _task_payload(),
                {"LSKUN_SSOT_ROOT": str(paths.company_root("Acme"))},
            )
            self.assertEqual(rc, 0)
            self.assertEqual(out, "")


class MarkerPresentTest(unittest.TestCase):
    def test_marker_present_emits_reminder(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(paths.Path, "home", return_value=Path(tmp)):
            paths.company_root("Acme").mkdir(parents=True)
            state.start("Acme", "proj")
            out, _, rc = _run(
                _task_payload(),
                {"LSKUN_SSOT_ROOT": str(paths.company_root("Acme"))},
            )
            self.assertEqual(rc, 0)
            self.assertIn("<system-reminder>", out)
            self.assertIn("external setup", out)
            self.assertIn("project=proj", out)
            self.assertIn("domain_assessment", out)  # next_action

    def test_step_count_incremented(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(paths.Path, "home", return_value=Path(tmp)):
            paths.company_root("Acme").mkdir(parents=True)
            state.start("Acme", "proj")
            before = state.read("Acme")
            _run(_task_payload(),
                 {"LSKUN_SSOT_ROOT": str(paths.company_root("Acme"))})
            after = state.read("Acme")
            self.assertEqual(after.step_count_so_far, before.step_count_so_far + 1)

    def test_exhausted_auto_unlinks(self):
        # max_step_count=10, step_count=10 인 marker 박제 → hook 진입 시 자동 unlink
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(paths.Path, "home", return_value=Path(tmp)):
            paths.company_root("Acme").mkdir(parents=True)
            state.start("Acme", "proj")
            # 손수 step_count_so_far 를 max 로
            p = state.marker_path("Acme")
            data = json.loads(p.read_text())
            data["step_count_so_far"] = 10
            p.write_text(json.dumps(data))
            out, _, rc = _run(
                _task_payload(),
                {"LSKUN_SSOT_ROOT": str(paths.company_root("Acme"))},
            )
            self.assertEqual(rc, 0)
            self.assertEqual(out, "")  # exhausted → 출력 없음
            self.assertFalse(p.exists())  # auto-unlink


class MalformedMarkerTest(unittest.TestCase):
    def test_invalid_json_auto_unlinks(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(paths.Path, "home", return_value=Path(tmp)):
            paths.company_root("Acme").mkdir(parents=True)
            p = state.marker_path("Acme")
            p.write_text("{ not valid")
            out, _, rc = _run(
                _task_payload(),
                {"LSKUN_SSOT_ROOT": str(paths.company_root("Acme"))},
            )
            self.assertEqual(rc, 0)
            self.assertEqual(out, "")
            self.assertFalse(p.exists())

    def test_evil_step_enum_auto_unlinks(self):
        # current_step="rm -rf" 같은 raw string 박제 → enum 검증 실패 → unlink
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(paths.Path, "home", return_value=Path(tmp)):
            paths.company_root("Acme").mkdir(parents=True)
            p = state.marker_path("Acme")
            p.write_text(json.dumps({
                "started_at": "2026-05-28T14:00:00+00:00",
                "company": "Acme", "project": "p",
                "current_step": "rm -rf /",
                "next_action": "rm -rf /",
                "step_count_so_far": 0, "max_step_count": 10,
            }))
            out, _, rc = _run(
                _task_payload(),
                {"LSKUN_SSOT_ROOT": str(paths.company_root("Acme"))},
            )
            self.assertEqual(rc, 0)
            self.assertNotIn("rm -rf", out)  # 절대 LLM context 에 안 들어감
            self.assertFalse(p.exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit && python3 -m unittest discover -s tests -p "test_hooks_post_tool_use_external.py" -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: 구현**

`src/lskun_kit/hooks/post_tool_use_external.py`:

```python
"""PostToolUse:Task hook — 외주 setup 다음 step push (ADR-0022).

marker 파일(`.external-setup.json`) 존재 시 다음 step 안내를 stdout 으로 emit.
enum allowlist 통과만 출력 — sync-in 인젝션 차단의 핵심.

평가 순서 (spec §5.1):
    1. tool_name != "Task" → exit 0
    2. LSKUN_ALLOW_EXTERNAL_HALT=1 → exit 0 + stderr warn
    3. 활성 회사 root 검출 실패 → exit 0
    4. marker 부재 → exit 0
    5. malformed/stale/exhausted → auto-unlink + exit 0
    6. step_count_so_far += 1 + atomic write
    7. system-reminder 주입 + exit 0

ADR-0009: stdlib only.
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

# self-bootstrap (pre_tool_use.py 패턴)
_SRC_DIR = str(Path(__file__).resolve().parents[2])
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

TOOL_TASK = "Task"
ENV_SSOT_ROOT = "LSKUN_SSOT_ROOT"
ENV_ALLOW_HALT = "LSKUN_ALLOW_EXTERNAL_HALT"


def main(argv: list[str] | None = None) -> int:
    # 예외 시 안전 종료 (block 안 함)
    try:
        _run()
    except Exception as e:  # noqa: BLE001
        print(f"lskun-kit post_tool_use_external: error {e!r}", file=sys.stderr)
    return 0


def _run() -> None:
    stdin_text = sys.stdin.read()

    # 1. Task tool 외 무시
    try:
        data = json.loads(stdin_text) if stdin_text.strip() else {}
    except json.JSONDecodeError:
        return
    if not isinstance(data, dict) or data.get("tool_name") != TOOL_TASK:
        return

    # 2. escape hatch
    if os.environ.get(ENV_ALLOW_HALT, "").strip() == "1":
        print(
            f"lskun-kit: WARNING — {ENV_ALLOW_HALT}=1 활성. "
            "외주 setup 자동 시퀀스가 무력화되고 있다 (ADR-0022). "
            "세션 단위로만 사용하라.",
            file=sys.stderr,
        )
        return

    # 3. 활성 회사 root
    company_root = _detect_company_root()
    if company_root is None:
        return

    # 4-7. marker 처리는 external_setup_state 가 일괄 담당.
    # external_setup_state.read() 가 malformed/stale/exhausted 시 auto-unlink.
    from lskun_kit import external_setup_state as state  # 지연 import

    # company 이름은 company_root.name (paths.company_root 가 보장)
    company = company_root.name
    s = state.read(company)
    if s is None:
        return  # marker 부재 또는 자동 정리됨

    # step_count_so_far += 1 (atomic)
    try:
        new = state.advance(company, s.current_step, s.next_action)
    except ValueError as e:
        # advance 가 실패하면 marker 자체가 잘못된 상태 → 안전하게 unlink
        state.marker_path(company).unlink(missing_ok=True)
        print(f"lskun-kit: marker advance failed: {e!r}", file=sys.stderr)
        return

    # advance 후 exhausted 면 unlink + 종료 (출력 없음)
    if new.is_exhausted():
        state.marker_path(company).unlink(missing_ok=True)
        return

    # system-reminder 주입 — enum 라벨만 노출 (인젝션 차단)
    reminder = (
        "<system-reminder>\n"
        f"LSKun external setup 진행 중 (project={new.project}, "
        f"step={new.current_step}).\n"
        f"다음 판단 step: {new.next_action}.\n"
        "CPO 는 같은 turn 안에 이 step 을 이어서 수행하라. "
        "사용자 응답을 기다리지 말 것.\n"
        "완료 시 external_setup_state.finalize() 로 marker 정리. ADR-0022.\n"
        "</system-reminder>"
    )
    print(reminder)


def _detect_company_root() -> "Path | None":
    """pre_tool_use._detect_company_root 와 동일 로직. 재사용 가능하면 import."""
    env_root = os.environ.get(ENV_SSOT_ROOT, "").strip()
    if env_root:
        path = Path(env_root)
        return path if path.exists() else None
    try:
        from lskun_kit.hooks.session_start import _find_active_company_root  # type: ignore[attr-defined]
    except ImportError:
        return None
    return _find_active_company_root()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
```

> NOTE: `_detect_company_root` 가 pre_tool_use.py 와 거의 동일하므로 `lskun_kit.hooks._common` 모듈로 추출하는 게 깔끔할 수 있습니다. 그러나 본 task 는 신규 모듈만 만들고, 추출은 Task 3 (Stop hook) 에서 같은 함수 필요할 때 결정. 우선 복제 OK.

- [ ] **Step 4: 테스트 통과 확인 + 전체 회귀**

Run: `cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit && python3 -m unittest discover -s tests -p "test_hooks_post_tool_use_external.py" -v && python3 -m unittest discover -s tests -v 2>&1 | tail -3`
Expected: 신규 전부 PASS + 전체 OK.

- [ ] **Step 5: 커밋**

```bash
git add src/lskun_kit/hooks/post_tool_use_external.py tests/test_hooks_post_tool_use_external.py
git commit -m "feat(P121): PostToolUse:Task hook — 외주 setup 다음 step push (enum allowlist)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Stop hook — turn 종료 차단 (hard guard)

**Files:**
- Create: `src/lskun_kit/hooks/stop_external.py`
- Test: `tests/test_hooks_stop_external.py`

평가 순서는 spec §5.2. **`stop_hook_active=true` → 무조건 allow + auto-unlink** 가 무한 lockup 방지의 단일 invariant (architect MAJOR 해소). Task 2 의 `_detect_company_root` 와 중복이 있으면 `_common.py` 로 추출.

- [ ] **Step 1: 공통 모듈 추출 (옵션 — Task 2 의 NOTE 결정)**

`src/lskun_kit/hooks/_common.py` 신규:

```python
"""hook 공통 헬퍼."""
from __future__ import annotations

import os
from pathlib import Path

ENV_SSOT_ROOT = "LSKUN_SSOT_ROOT"


def detect_company_root() -> "Path | None":
    env_root = os.environ.get(ENV_SSOT_ROOT, "").strip()
    if env_root:
        path = Path(env_root)
        return path if path.exists() else None
    try:
        from lskun_kit.hooks.session_start import _find_active_company_root  # type: ignore[attr-defined]
    except ImportError:
        return None
    return _find_active_company_root()
```

post_tool_use_external.py 의 `_detect_company_root` 를 이 헬퍼로 교체 (의도적 회귀 없음 — 동일 함수).

- [ ] **Step 2: 실패 테스트 작성**

`tests/test_hooks_stop_external.py`:

```python
"""ADR-0022 — Stop hook 테스트."""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import external_setup_state as state  # noqa: E402
from lskun_kit import paths  # noqa: E402
from lskun_kit.hooks import stop_external as hook  # noqa: E402


def _run(stdin_text: str, env: dict[str, str]) -> tuple[dict | None, str, int]:
    with patch.dict(os.environ, env, clear=True), \
         patch("sys.stdin", io.StringIO(stdin_text)), \
         patch("sys.stdout", io.StringIO()) as out, \
         patch("sys.stderr", io.StringIO()) as err:
        rc = hook.main([])
    s = out.getvalue().strip()
    parsed = json.loads(s) if s else None
    return parsed, err.getvalue(), rc


def _payload(stop_hook_active: bool = False) -> str:
    return json.dumps({
        "session_id": "test",
        "stop_hook_active": stop_hook_active,
        "transcript_path": "/tmp/x",
    })


class StopHookActiveTest(unittest.TestCase):
    """무한 lockup 방지의 단일 invariant — architect MAJOR."""
    def test_stop_hook_active_passes_immediately(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(paths.Path, "home", return_value=Path(tmp)):
            paths.company_root("Acme").mkdir(parents=True)
            state.start("Acme", "proj")  # marker 살아있음
            parsed, _, rc = _run(
                _payload(stop_hook_active=True),
                {"LSKUN_SSOT_ROOT": str(paths.company_root("Acme"))},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(parsed)  # 출력 없음 = allow
            self.assertFalse(state.marker_path("Acme").exists())  # auto-unlink


class EscapeHatchTest(unittest.TestCase):
    def test_env_skip_passes(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(paths.Path, "home", return_value=Path(tmp)):
            paths.company_root("Acme").mkdir(parents=True)
            state.start("Acme", "proj")
            parsed, err, rc = _run(
                _payload(),
                {"LSKUN_ALLOW_EXTERNAL_HALT": "1",
                 "LSKUN_SSOT_ROOT": str(paths.company_root("Acme"))},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(parsed)
            self.assertIn("LSKUN_ALLOW_EXTERNAL_HALT", err)


class MarkerAbsentTest(unittest.TestCase):
    def test_no_marker_no_block(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(paths.Path, "home", return_value=Path(tmp)):
            paths.company_root("Acme").mkdir(parents=True)
            parsed, _, rc = _run(
                _payload(),
                {"LSKUN_SSOT_ROOT": str(paths.company_root("Acme"))},
            )
            self.assertEqual(rc, 0)
            self.assertIsNone(parsed)


class MarkerPresentBlockTest(unittest.TestCase):
    def test_marker_present_blocks(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(paths.Path, "home", return_value=Path(tmp)):
            paths.company_root("Acme").mkdir(parents=True)
            state.start("Acme", "proj")
            parsed, _, rc = _run(
                _payload(),
                {"LSKUN_SSOT_ROOT": str(paths.company_root("Acme"))},
            )
            self.assertEqual(rc, 0)
            self.assertIsNotNone(parsed)
            self.assertEqual(parsed["decision"], "block")
            self.assertIn("external setup", parsed["reason"])
            self.assertIn("project=proj", parsed["reason"])
            # CPO 결재권 보존 — reason 문구가 "강제" 가 아니라 "이어서 수행"
            self.assertIn("이어서", parsed["reason"])
            # escape hatch 안내
            self.assertIn("LSKUN_ALLOW_EXTERNAL_HALT", parsed["reason"])


class HookSafetyTest(unittest.TestCase):
    def test_malformed_stdin_no_block(self):
        parsed, _, rc = _run("{ bad", {})
        self.assertEqual(rc, 0)
        self.assertIsNone(parsed)

    def test_exception_no_block(self):
        # company_root 가 invalid 경로일 때도 exception 으로 block 안 함
        parsed, _, rc = _run(
            _payload(),
            {"LSKUN_SSOT_ROOT": "/nonexistent/xyz"},
        )
        self.assertEqual(rc, 0)
        self.assertIsNone(parsed)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit && python3 -m unittest discover -s tests -p "test_hooks_stop_external.py" -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 4: 구현**

`src/lskun_kit/hooks/stop_external.py`:

```python
"""Stop hook — 외주 setup turn 종료 차단 (ADR-0022).

marker 파일 살아있고 stop_hook_active != true 인 경우에만 decision="block".

평가 순서 (spec §5.2):
    1. stop_hook_active=true → exit 0 + auto-unlink (무한 lockup 방지 invariant)
    2. LSKUN_ALLOW_EXTERNAL_HALT=1 → exit 0 + stderr warn
    3. 활성 회사 root 부재 → exit 0
    4. marker 부재/malformed/stale/exhausted → exit 0 (read 가 unlink 처리)
    5. block + reason

ADR-0009: stdlib only.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_SRC_DIR = str(Path(__file__).resolve().parents[2])
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

ENV_ALLOW_HALT = "LSKUN_ALLOW_EXTERNAL_HALT"


def main(argv: list[str] | None = None) -> int:
    try:
        out = _decide()
    except Exception as e:  # noqa: BLE001
        print(f"lskun-kit stop_external: error {e!r}", file=sys.stderr)
        return 0
    if out is not None:
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        sys.stdout.write("\n")
    return 0


def _decide() -> "dict | None":
    stdin_text = sys.stdin.read()
    try:
        data = json.loads(stdin_text) if stdin_text.strip() else {}
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    # 1. stop_hook_active=true → 무조건 통과 + marker 정리 (단일 invariant)
    if data.get("stop_hook_active") is True:
        _try_unlink_active_marker()
        return None

    # 2. escape hatch
    if os.environ.get(ENV_ALLOW_HALT, "").strip() == "1":
        print(
            f"lskun-kit: WARNING — {ENV_ALLOW_HALT}=1 활성. "
            "외주 setup turn 차단이 우회되고 있다 (ADR-0022). "
            "세션 단위로만 사용하라.",
            file=sys.stderr,
        )
        return None

    # 3-4. 활성 회사 + marker
    from lskun_kit.hooks._common import detect_company_root
    from lskun_kit import external_setup_state as state

    company_root = detect_company_root()
    if company_root is None:
        return None

    s = state.read(company_root.name)
    if s is None:
        return None  # read() 가 malformed/stale 자동 처리

    # 5. block + reason ("CPO 다음 판단 이어서 수행" — 결재권 보존 문구)
    return {
        "decision": "block",
        "reason": (
            f"LSKun external setup 진행 중 (project={s.project}, "
            f"step={s.current_step}). 다음 판단 step {s.next_action} 을 "
            f"이어서 수행하라. CPO 의 결재 판단 break 가 필요하면 같은 turn "
            f"안에 결재 후 다음 step 으로. 사용자 입력 대기로 turn 종료 금지. "
            f"종료하려면: /lskun-kit:external cancel {s.project} 또는 "
            f"{ENV_ALLOW_HALT}=1."
        ),
    }


def _try_unlink_active_marker() -> None:
    """stop_hook_active=true 경로에서 marker 자동 정리. 실패 무시."""
    try:
        from lskun_kit.hooks._common import detect_company_root
        from lskun_kit import external_setup_state as state
        cr = detect_company_root()
        if cr is not None:
            state.marker_path(cr.name).unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
```

- [ ] **Step 5: 테스트 통과 + 전체 회귀**

Run: `cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit && python3 -m unittest discover -s tests -p "test_hooks_stop_external.py" -v && python3 -m unittest discover -s tests -v 2>&1 | tail -3`
Expected: 신규 전부 PASS + 전체 OK.

- [ ] **Step 6: 커밋**

```bash
git add src/lskun_kit/hooks/stop_external.py src/lskun_kit/hooks/_common.py src/lskun_kit/hooks/post_tool_use_external.py tests/test_hooks_stop_external.py
git commit -m "feat(P121): Stop hook — 외주 setup turn 차단 + stop_hook_active invariant

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: hooks.json 등록 + manifest 테스트 갱신

**Files:**
- Modify: `hooks/hooks.json` — PostToolUse:Task + Stop 등록
- Modify: `tests/test_hooks_manifest.py` — 기존 `test_reflection_hooks_removed` 의도 명시 갱신

- [ ] **Step 1: 기존 manifest 테스트 확인**

Run: `grep -n "test_reflection_hooks_removed\|test_stop\|PostToolUse" /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit/tests/test_hooks_manifest.py`
Expected: `test_reflection_hooks_removed` (line ~32) 의 현재 단언 파악.

- [ ] **Step 2: 실패 테스트 갱신**

`tests/test_hooks_manifest.py` 의 `test_reflection_hooks_removed` 를 다음으로 교체 (이름 의도 명시):

```python
def test_only_external_setup_hooks_allowed_beyond_pre_tool_use(self):
    """ADR-0022: reflection 메커니즘 폐기는 유지, 외주 setup 한정 hook 은 허용.

    SessionStart, PreToolUse:Task 외에 Stop / PostToolUse:Task 가 허용되되,
    각 hook 의 command 경로가 외주 setup 모듈을 가리켜야 한다.
    """
    hooks = self.manifest["hooks"]
    allowed_events = {"SessionStart", "PreToolUse", "PostToolUse", "Stop"}
    self.assertTrue(set(hooks.keys()) <= allowed_events,
                    f"unexpected hook events: {set(hooks.keys()) - allowed_events}")

    # PostToolUse 는 Task matcher + external 모듈 경로 강제
    if "PostToolUse" in hooks:
        entries = hooks["PostToolUse"]
        for e in entries:
            self.assertEqual(e["matcher"], "Task")
            for cmd in e["hooks"]:
                self.assertIn("post_tool_use_external", cmd["command"])

    # Stop 도 external 모듈만 허용
    if "Stop" in hooks:
        entries = hooks["Stop"]
        for e in entries:
            for cmd in e["hooks"]:
                self.assertIn("stop_external", cmd["command"])

def test_external_setup_hooks_registered(self):
    """ADR-0022: PostToolUse:Task + Stop 등록 검증."""
    hooks = self.manifest["hooks"]
    self.assertIn("PostToolUse", hooks)
    self.assertIn("Stop", hooks)
```

- [ ] **Step 3: 실패 확인**

Run: `cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit && python3 -m unittest discover -s tests -p "test_hooks_manifest.py" -v`
Expected: `test_external_setup_hooks_registered` FAIL (등록 안 됨).

- [ ] **Step 4: hooks.json 갱신**

`hooks/hooks.json` 에 PostToolUse + Stop 추가:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/src/lskun_kit/hooks/session_start.py"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Task",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/src/lskun_kit/hooks/pre_tool_use.py"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Task",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/src/lskun_kit/hooks/post_tool_use_external.py"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/src/lskun_kit/hooks/stop_external.py"
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 5: 통과 + 회귀**

Run: `cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit && python3 -m unittest discover -s tests -v 2>&1 | tail -3`
Expected: 전체 OK.

- [ ] **Step 6: 커밋**

```bash
git add hooks/hooks.json tests/test_hooks_manifest.py
git commit -m "feat(P121): hooks.json 에 PostToolUse:Task + Stop 등록 + manifest 테스트 갱신

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: commands/external.md 본문 강화 (pull 갈래 — critic B1 해소)

**Files:**
- Modify: `commands/external.md`
- Test: `tests/test_external_command.py` 확장

setup 시퀀스에 "1턴 완수" 명시 + `/clear` 안내 + cancel 서브명령 본문 추가.

- [ ] **Step 1: 실패 테스트 추가**

`tests/test_external_command.py` 의 ExternalCommandTest 에 추가:

```python
    def test_one_turn_completion_directive(self):
        self.assertIn("한 turn", self.text)  # 1턴 완수 명시
        self.assertIn("사용자 응답을 기다", self.text)  # 대기 금지

    def test_clear_session_guidance(self):
        # critic B1 — /clear 강제 break 안내
        self.assertIn("/clear", self.text)

    def test_cancel_subcommand_documented(self):
        self.assertIn("cancel", self.text)
        self.assertIn("LSKUN_ALLOW_EXTERNAL_HALT", self.text)

    def test_adr_0022_referenced(self):
        self.assertIn("ADR-0022", self.text)
```

- [ ] **Step 2: 실패 확인**

Run: `cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit && python3 -m unittest discover -s tests -p "test_external_command.py" -v`
Expected: 신규 4건 FAIL.

- [ ] **Step 3: commands/external.md 갱신**

`### setup <project>` 섹션을 spec §6.1 의 내용으로 교체:

```markdown
### setup <project> [--redteam] [--customers]

**시퀀스는 한 turn 안에 완수한다. 중간에 사용자 응답을 기다려 turn 을 종료하지 말 것.**
(ADR-0022 — PostToolUse + Stop hook 이 turn 연속성을 강제한다. marker:
`~/.lskun-companies/<company>/.external-setup.json`)

구성 시퀀스 (CPO 주도):

1. CPO 가 프로젝트 도메인 판단.
2. 도메인 워커가 hired/ 에 부재면 자동 채용 (CPO → HR Lead dispatch).
3. CPO 가 도메인 워커를 1회 dispatch → 위험·경쟁구도·급소·타깃 고객 자문 수집.
   **이 step 끝나면 워커 세션 marker(.lskun-session.json) 가 살아있다.** 다음
   dispatch 전에 세션 정리가 필요하다 — PreToolUse hook 의 chain 차단(ADR-0004 §8)
   을 통과하기 위해. 정리 방법:
   - (a) CPO 가 `lskun_kit.session.clear()` 자동 호출 (지원되는 경우)
   - (b) CPO 가 사용자에게 "**워커 세션 정리를 위해 `/clear` 를 입력하면 자동
     재개됩니다**" 1줄 안내 후 turn 종료가 아닌 다음 입력 대기.
   어느 쪽이든 **Stop hook 이 turn 종료를 차단하므로** CPO 는 이 안내만 출력하고
   다음 step 으로 넘어간다.
4. 자문을 `external/<project>/brief.md` 합성.
5. HR Lead dispatch → `templates/redteam.md`, `templates/customer.md` 기반으로
   `external/<project>/{redteam,customers}/` 에 페르소나 박제.
6. `external_setup_state.finalize()` 호출 → marker 자동 삭제.

시작 시 CPO 는 사용자에게 다음 1줄 안내한다:
> "외주 setup 자동 시퀀스 시작 (project=<project>). 도중에 `/clear` 안내가 나오면
> 입력해주세요. 그 외엔 자동 진행됩니다 (보통 30~60초). 중단하려면
> `/lskun-kit:external cancel <project>` 또는 `LSKUN_ALLOW_EXTERNAL_HALT=1`."

### cancel <project>

진행 중인 외주 setup 을 중단한다. marker 파일을 atomic unlink + audit entry 박제
(`event_type="external_setup_cancelled"`). 새 setup 즉시 가능.

긴급 중단이 필요하면 env var: `export LSKUN_ALLOW_EXTERNAL_HALT=1` (세션 단위만,
`.zshrc` 영구 export 는 doctor [34] 가 검출).
```

기존 `### list <project>` / `### consult` 는 그대로 유지.

- [ ] **Step 4: 통과 + 회귀**

Run: `cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit && python3 -m unittest discover -s tests -v 2>&1 | tail -3`
Expected: 전체 OK.

- [ ] **Step 5: 커밋**

```bash
git add commands/external.md tests/test_external_command.py
git commit -m "feat(P121): commands/external.md 강화 — 1턴 완수 + /clear 안내 + cancel 서브명령

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: sync.py 가드 — sync-in 시 marker 명시 confirm (security C1)

**Files:**
- Modify: `src/lskun_kit/sync.py`
- Test: `tests/test_sync_external_marker.py` 신규 또는 기존 test_sync 확장

`.external-setup.json` 발견 시 사용자 명시 confirm (기존 덮어쓰기 confirm 과 별도).

- [ ] **Step 1: 기존 sync.py 확인**

Run: `cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit && grep -n "_walk_size\|notes\|confirm" src/lskun_kit/sync.py | head -20`
Expected: `_walk_size` 함수와 confirm/notes 패턴 위치 파악. 그 패턴에 맞춰 marker 발견 시 경고 append.

- [ ] **Step 2: 실패 테스트 작성**

`tests/test_sync_external_marker.py` (또는 기존 test_sync_*.py 가 있으면 거기에 추가):

```python
"""ADR-0022 — sync-in 시 .external-setup.json 가드 (security C1)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import sync  # noqa: E402


class SyncMarkerGuardTest(unittest.TestCase):
    def test_walk_size_warns_on_external_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "company.md").write_text("co")
            (src / ".external-setup.json").write_text(json.dumps({
                "started_at": "2026-05-28T14:00:00+00:00",
                "company": "Acme", "project": "evil",
                "current_step": "init", "next_action": "domain_assessment",
                "step_count_so_far": 0, "max_step_count": 10,
            }))
            # _walk_size 의 정확한 시그니처는 기존 sync.py 확인 후 호출.
            # 핵심 단언: notes 또는 warnings 에 .external-setup.json 언급.
            result = sync._walk_size(src)  # 시그니처는 Step 1 에서 확정
            # 다음 둘 중 하나로 검증 (실제 sync.py 의 반환 구조에 맞춤):
            notes_repr = repr(result)
            self.assertIn(".external-setup.json", notes_repr)


if __name__ == "__main__":
    unittest.main()
```

> NOTE: 본 테스트는 sync._walk_size 의 정확한 시그니처/반환에 따라 조정. Step 1 에서 정확한 형태 확인 후 테스트와 구현 둘 다 맞춤. 만약 _walk_size 가 단순 size 만 반환하면 별도 `notes` 수집 구조를 sync 모듈에 신설 또는 사용자 confirm prompt 가 호출되는 경로를 직접 테스트.

- [ ] **Step 3: 실패 확인**

Run: `cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit && python3 -m unittest discover -s tests -p "test_sync_external_marker.py" -v`
Expected: FAIL.

- [ ] **Step 4: sync.py 갱신**

Step 1 에서 본 _walk_size / confirm 패턴에 따라 `.external-setup.json` 발견 시 경고 append 또는 별도 confirm prompt:

```python
EXTERNAL_MARKER_NAME = ".external-setup.json"
# ... _walk_size 내부 또는 별도 함수에서:
for f in src.rglob("*"):
    if f.is_file() and f.name == EXTERNAL_MARKER_NAME:
        notes.append(
            f"⚠️ {f.relative_to(src)} — 외주 setup 진행 상태 파일 (ADR-0022). "
            "외부 mirror 의 marker 는 인젝션 가능성 있음. sync 후 자동으로 "
            "취급되지 않도록 무결성 확인 필요."
        )
```

또는 `sync_in` 진입 시 명시 confirm prompt 1줄 추가 (기존 사용자 confirm 패턴 따름).

- [ ] **Step 5: 통과 + 회귀**

Run: 전체 OK.

- [ ] **Step 6: 커밋**

```bash
git add src/lskun_kit/sync.py tests/test_sync_external_marker.py
git commit -m "fix(P121): sync-in 시 .external-setup.json 발견 경고 (security C1)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: doctor [33] stale marker + [34] zshrc env grep

**Files:**
- Modify: `src/lskun_kit/external_diagnostics.py` (또는 신규 모듈)
- Modify: `commands/doctor.md`
- Test: `tests/test_external_doctor_setup.py` 신규

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_external_doctor_setup.py`:

```python
"""ADR-0022 — doctor [33][34] 진단 테스트."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import external_setup_state as state  # noqa: E402
from lskun_kit import external_diagnostics  # noqa: E402
from lskun_kit import paths  # noqa: E402


class StaleMarkerDetectionTest(unittest.TestCase):
    def _patch_home(self, tmp):
        return mock.patch.object(paths.Path, "home", return_value=Path(tmp))

    def test_no_marker_clean(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            findings = external_diagnostics.diagnose_external_setup("Acme")
            self.assertEqual(findings.issues, [])

    def test_fresh_marker_clean(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            state.start("Acme", "proj")
            findings = external_diagnostics.diagnose_external_setup("Acme")
            self.assertEqual(findings.issues, [])  # 살아있는 marker = OK

    def test_stale_marker_flagged(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            marker = state.marker_path("Acme")
            old = datetime.now(timezone.utc) - timedelta(hours=30)
            marker.write_text(json.dumps({
                "started_at": old.isoformat(),
                "company": "Acme", "project": "p",
                "current_step": "init", "next_action": "domain_assessment",
                "step_count_so_far": 0, "max_step_count": 10,
            }))
            findings = external_diagnostics.diagnose_external_setup("Acme")
            self.assertTrue(any("stale" in i.lower() or "오래" in i
                                for i in findings.issues))


class EnvGrepTest(unittest.TestCase):
    def test_no_env_files_clean(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(Path, "home", return_value=Path(tmp)):
            findings = external_diagnostics.diagnose_external_env_export()
            self.assertEqual(findings.issues, [])

    def test_zshrc_with_halt_flagged(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(Path, "home", return_value=Path(tmp)):
            (Path(tmp) / ".zshrc").write_text(
                "export LSKUN_ALLOW_EXTERNAL_HALT=1\n"
            )
            findings = external_diagnostics.diagnose_external_env_export()
            self.assertTrue(any("LSKUN_ALLOW_EXTERNAL_HALT" in i
                                for i in findings.issues))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 실패 확인**

Run: `cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit && python3 -m unittest discover -s tests -p "test_external_doctor_setup.py" -v`
Expected: AttributeError (diagnose_external_setup, diagnose_external_env_export 미정의).

- [ ] **Step 3: 구현 (external_diagnostics.py 확장)**

```python
# external_diagnostics.py 끝에 추가:

import re
from datetime import datetime, timezone

@dataclass
class SetupFindings:
    """외주 setup 진단."""
    issues: list[str] = field(default_factory=list)


def diagnose_external_setup(company: str) -> SetupFindings:
    """marker 파일의 stale 검출 (doctor [33])."""
    from lskun_kit import external_setup_state as state
    findings = SetupFindings()
    p = state.marker_path(company)
    if not p.exists():
        return findings
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        s = state.ExternalSetupState.from_dict(raw)
    except (json.JSONDecodeError, ValueError, OSError) as e:
        findings.issues.append(
            f"외주 setup marker 손상 (.external-setup.json): {e}. "
            "정리하려면 rm 또는 /lskun-kit:external cancel."
        )
        return findings
    if s.is_stale():
        findings.issues.append(
            f"외주 setup marker 가 오래됨 (started_at={s.started_at.isoformat()}, "
            f"project={s.project}). 24h 초과 — stale. "
            "정리: /lskun-kit:external cancel."
        )
    return findings


#: zshrc/bashrc 등에서 검사할 env var 이름.
_ENV_NAME = "LSKUN_ALLOW_EXTERNAL_HALT"
_ENV_FILES = (".zshrc", ".bashrc", ".zshenv", ".profile", ".bash_profile")
_ENV_GREP_PAT = re.compile(rf"^\s*export\s+{_ENV_NAME}=", re.MULTILINE)


def diagnose_external_env_export() -> SetupFindings:
    """``~/.zshrc`` 등에 ``LSKUN_ALLOW_EXTERNAL_HALT`` 영구 export 검출 (doctor [34])."""
    findings = SetupFindings()
    home = Path.home()
    for fname in _ENV_FILES:
        p = home / fname
        if not p.exists():
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if _ENV_GREP_PAT.search(txt):
            findings.issues.append(
                f"~/{fname} 에 {_ENV_NAME} 영구 export 가 박혀있음. "
                "외주 setup 가드를 무력화함 (ADR-0022). 세션 단위로만 사용 권장."
            )
    return findings
```

- [ ] **Step 4: 통과 + 회귀**

Run: 전체 OK.

- [ ] **Step 5: commands/doctor.md 에 [33][34] 항목 추가**

[32] external 정합성 (P120) 바로 아래에 동일 패턴으로 추가:

```markdown
### 33. **외주 setup marker stale 검출 (ADR-0022, P121)**
…`lskun_kit.external_diagnostics.diagnose_external_setup(<company>)` 호출, read-only.
- 살아있는 marker (24h 이내): ✅ 정상 진행 중
- stale marker (24h 초과): ⚠️ "외주 setup marker 가 오래됨 — 정리 권장: /lskun-kit:external cancel"
- 손상된 marker (malformed JSON): ⚠️ 정리 안내

### 34. **`LSKUN_ALLOW_EXTERNAL_HALT` 영구 export 검출 (ADR-0022, P121)**
…`lskun_kit.external_diagnostics.diagnose_external_env_export()` 호출, read-only.
- ~/.zshrc, ~/.bashrc, ~/.zshenv, ~/.profile, ~/.bash_profile 에서 grep.
- 발견 시 ⚠️ "외주 setup 가드 무력화 — 세션 단위로만 사용 권장"
```

- [ ] **Step 6: 커밋**

```bash
git add src/lskun_kit/external_diagnostics.py tests/test_external_doctor_setup.py commands/doctor.md
git commit -m "feat(P121): doctor [33] stale marker + [34] env export 검출 (ADR-0022)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: external cancel 명령 구현 + state.start 의 stale 정리

**Files:**
- Modify: `commands/external.md` — cancel 본문은 Task 5 에서 박제됨. 여기선 audit entry 박제 로직 확인.
- Modify: `src/lskun_kit/hire_audit.py` — `record_external_setup_event(event_type)` 추가 또는 generic 함수 검토.
- Test: `tests/test_external_setup_cancel.py` 신규

cancel slash 명령 자체는 LLM 지시문이므로 코드 변경은 audit 측이 핵심. 또는 cancel 을 Python entry function (`external_setup_state.cancel`) 으로 제공해 LLM 이 호출.

- [ ] **Step 1: 결정 — cancel 구현 위치**

옵션:
(A) `external_setup_state.cancel(company, project)` 함수 신규 — marker unlink + audit append. LLM 이 호출.
(B) 순수 LLM 지시문 — finalize 와 거의 동일.

권장: (A). audit 추적 + 사용자가 호출 시 race 안전성 (cooldown 등 향후 확장 여지).

- [ ] **Step 2: 실패 테스트 작성**

`tests/test_external_setup_cancel.py`:

```python
"""ADR-0022 — external setup cancel 테스트."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import external_setup_state as state  # noqa: E402
from lskun_kit import paths  # noqa: E402


class CancelTest(unittest.TestCase):
    def _patch_home(self, tmp):
        return mock.patch.object(paths.Path, "home", return_value=Path(tmp))

    def test_cancel_unlinks_marker(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            state.start("Acme", "proj")
            state.cancel("Acme")
            self.assertFalse(state.marker_path("Acme").exists())

    def test_cancel_no_marker_no_raise(self):
        with tempfile.TemporaryDirectory() as tmp, self._patch_home(tmp):
            paths.company_root("Acme").mkdir(parents=True)
            state.cancel("Acme")  # no-op, no exception


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 실패 확인**

Run: `... -p "test_external_setup_cancel.py" -v` → AttributeError.

- [ ] **Step 4: 구현 — `state.cancel` 추가**

`src/lskun_kit/external_setup_state.py` 에 추가:

```python
def cancel(company: str) -> None:
    """진행 중인 외주 setup 중단. marker unlink. 부재 시 no-op."""
    marker_path(company).unlink(missing_ok=True)
    # audit entry 박제는 별도 (hire_audit.record_external_onboard 참고).
    # 본 함수는 marker 정리만 담당, audit 은 commands/external.md 가 호출.
```

`__all__` 에 `cancel` 추가.

- [ ] **Step 5: 통과 + 회귀**

Run: 전체 OK.

- [ ] **Step 6: 커밋**

```bash
git add src/lskun_kit/external_setup_state.py tests/test_external_setup_cancel.py
git commit -m "feat(P121): external_setup_state.cancel — marker unlink

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: ADR-0022 박제 + 문서 갱신 + version bump

**Files:**
- Modify: `docs/internals/adr-index.md` — ADR-0022 행 + supersede chain
- Modify: `docs/internals/forbidden-history.md` — :45 갱신 + ADR-0022 신규 금지 섹션
- Modify: `CLAUDE.md` — §1 Phase 21 / 0.28.0 / slash command 표 / §6 금지 요약 / §8 로드맵 / doctor 항목 수
- Modify: `.claude-plugin/plugin.json` — version 0.28.0

(P120 Task 9 와 동일 패턴.)

- [ ] **Step 1: 사전 grep**

```bash
cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit
python3 -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'])"  # 0.27.0 예상
tail -20 docs/internals/adr-index.md
grep -n "ADR-0020 신규 금지\|ADR-0021 신규 금지" docs/internals/forbidden-history.md
```

- [ ] **Step 2: adr-index.md 갱신**

ADR-0021 행 아래에 추가:

```markdown
| ADR-0022 | **Multi-step CPO 시퀀스 결정론 강제 (외주 setup hook)** | 활성 (v0.28.0+, ADR-0021 보강 / forbidden-history.md:45 부분 supersede — spec: `docs/superpowers/specs/2026-05-28-external-setup-auto-sequence-design.md`) |
```

Supersede chain 시각화에 추가:
```
forbidden-history.md:45 → ADR-0022 (부분)
```

- [ ] **Step 3: forbidden-history.md 갱신**

(a) `:45` 줄 갱신 (spec §2.2 의 갱신문). (b) 마지막 `---` 위에 spec §2.3 의 신규 금지 6개 박제:

```markdown
### ADR-0022 신규 금지 (외주 setup hook, P121)

- **Stop hook 의 `stop_hook_active=true` payload 무시** — 무한 lockup. 무조건 allow + marker auto-unlink 단일 invariant.
- **PostToolUse/Stop hook 에서 `.external-setup.json` 외 입력 (Task description/prompt 내용 파싱) 으로 시퀀스 의도 추론** — forbidden-history.md:60 계승.
- **marker 파일 schema 의 enum 미강제** — 자유 string 박제는 sync-in 경유 prompt 인젝션 표면 (security C1).
- **marker wall-clock TTL 부재** — 영구 stuck. 24h 초과 시 자동 unlink.
- **`LSKUN_ALLOW_EXTERNAL_HALT` 의 `.zshrc/.bashrc` 영구 export** — 가드 무력화. doctor [34] 검출.
- **hook 의 trigger 범위 확장 (외주 setup 외 일반 dispatch 로 침투)** — marker 파일 존재 시에만 동작.
```

- [ ] **Step 4: CLAUDE.md 갱신**

(P120 Task 9 와 동일 5점 갱신: §1 Phase 21/0.28.0, slash command 표에 cancel 표시 (`external setup|list|consult|cancel`), §6 금지 요약 1줄, §8 로드맵, doctor 항목 수 31→33.)

§6 추가 줄:
```markdown
- 외주 setup hook 의 marker 외 입력 파싱 / stop_hook_active 무시 — ADR-0022
```

- [ ] **Step 5: plugin.json version bump**

Edit `0.27.0` → `0.28.0` (한 줄만).

- [ ] **Step 6: 정합성 + 회귀**

```bash
grep -c "ADR-0022" docs/internals/adr-index.md docs/internals/forbidden-history.md CLAUDE.md  # 각 ≥1
python3 -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'])"  # 0.28.0
python3 -m unittest discover -s tests -v 2>&1 | tail -3
```

- [ ] **Step 7: 커밋**

```bash
git add docs/internals/adr-index.md docs/internals/forbidden-history.md CLAUDE.md .claude-plugin/plugin.json
git commit -m "docs(P121): ADR-0022 박제 + forbidden 갱신 + version 0.28.0

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: 최종 회귀 + 통합 보고

**Files:**
- Test: 전체 스위트

- [ ] **Step 1: 전체 unittest**

Run: `cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit && python3 -m unittest discover -s tests -v 2>&1 | tail -10`
Expected: 신규 + 기존 PASS.

- [ ] **Step 2: import 무결성 + self-contained**

```bash
python3 -c "
from lskun_kit import external_setup_state
from lskun_kit.hooks import post_tool_use_external, stop_external
print('imports ok')
"
grep -rn "import requests\|import urllib\|import socket\|subprocess" \
  src/lskun_kit/external_setup_state.py \
  src/lskun_kit/hooks/post_tool_use_external.py \
  src/lskun_kit/hooks/stop_external.py \
  || echo "self-contained: no network/subprocess"
```

- [ ] **Step 3: hook smoke test (선택)**

직접 stdin/stdout 시뮬레이션:
```bash
echo '{"tool_name":"Task","tool_input":{}}' | python3 src/lskun_kit/hooks/post_tool_use_external.py
echo '{"session_id":"x","stop_hook_active":false,"transcript_path":"/tmp/x"}' | python3 src/lskun_kit/hooks/stop_external.py
```
marker 부재 환경에서 출력 0 확인.

- [ ] **Step 4: spec §1~§11 매핑 자체 검증**

각 spec 요구사항 → task 매핑 표 작성하여 gap 0 확인. 누락 발견 시 추가 task.

- [ ] **Step 5: 최종 commit log 정리**

```bash
git log feat/p121-external-setup-auto-sequence --oneline | head -20
```

- [ ] **Step 6: 최종 보고** (verification-before-completion 형식)
- 전체 unittest 통과 개수
- ADR-0022 3개 문서 박제 grep 결과
- self-contained 결과
- BLOCKER 3건 + MAJOR 3건 해소 증거 매핑
- P121 commit 시퀀스
- 잔존 known issue (없으면 명시)
- Status: DONE / DONE_WITH_CONCERNS / BLOCKED

---

## Self-Review (작성자 체크)

**1. Spec coverage (spec §별 → task):**
- §1 문제와 맥락 → Task 5,9 (문서)
- §2 ADR-0022 결정 → Task 9
- §3 아키텍처 → Task 1,2,3,4 전반
- §4 데이터 구조 (enum allowlist) → Task 1 (state schema)
- §5 hook 동작 → Task 2 (PostToolUse), Task 3 (Stop)
- §6 문서 강화 → Task 5
- §7 lifecycle → Task 1 (start/advance/finalize), Task 8 (cancel)
- §8 sync-in 보안 → Task 6
- §9 테스트 → 전 task TDD
- §10 ADR/문서 → Task 9
- §11 범위 → 전체
- ✅ gap 0.

**2. Placeholder scan:** `<company>`, `<project>` 는 의도된 추상 placeholder. TBD/TODO 없음. Task 6 의 _walk_size 시그니처는 Step 1 에서 확인 후 맞춤 — NOTE 로 명시. Task 8 의 cancel 위치 결정도 Step 1 옵션 명시.

**3. Type consistency:** `state.start(company, project)`, `state.read(company) → State|None`, `state.advance(company, current_step, next_action)`, `state.finalize(company)`, `state.cancel(company)`, `state.marker_path(company)`, `STEP_ENUM`, `MAX_STEP_COUNT_DEFAULT=10`, `STALE_SECONDS=24*3600`. 모든 task 에서 동일 시그니처 사용.
