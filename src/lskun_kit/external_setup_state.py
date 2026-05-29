"""ADR-0022 — 외주 setup 자동 시퀀스 marker 파일 schema + lifecycle.

위치: ``~/.lskun-companies/<company>/.external-setup.json``

CPO 가 ``/lskun-kit:external`` 명령을 받아 setup 시퀀스를 진행하는 동안 한 줄로
"지금 어디까지 왔는가" 를 공유한다. session.py 와 동일한 패턴:

- atomic write (tmp + os.replace)
- TTL (24h) 초과 시 stale 로 간주, ``read()`` 가 자동 정리 후 ``None``
- step 폭주 가드 (max_step_count) — exhausted 도 자동 정리

ADR-0009 정합: stdlib only (json / dataclasses / datetime / pathlib / os).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lskun_kit import external, paths

#: marker 파일 이름. 회사 SSOT 디렉토리 직속.
MARKER_FILENAME = ".external-setup.json"

#: marker TTL — 24h. session.py 와 동일 정책.
STALE_SECONDS = 24 * 60 * 60

#: step 폭주 가드 default. ADR-0022 — 정상 시퀀스 7 step. 여유 + 3.
MAX_STEP_COUNT_DEFAULT = 10

#: 허용 step allowlist (security C1 — enum 위반 차단).
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
        if not isinstance(data, dict):
            raise ValueError(f"external-setup marker: expected dict, got {type(data).__name__}")

        # 필수 필드 존재 검증
        required = (
            "started_at",
            "company",
            "project",
            "current_step",
            "next_action",
            "step_count_so_far",
        )
        for key in required:
            if key not in data:
                raise ValueError(f"external-setup marker: missing field {key!r}")

        # 이름 검증 (company / project)
        paths.validate_company_name(data["company"])
        external.validate_project_name(data["project"])

        # step enum 검증
        if data["current_step"] not in STEP_ENUM:
            raise ValueError(
                f"external-setup marker: invalid current_step {data['current_step']!r} "
                f"(allowed: {STEP_ENUM})"
            )

        # next_action enum 검증 (security C1 후속 — current_step 과 동일 allowlist)
        if data["next_action"] not in STEP_ENUM:
            raise ValueError(
                f"external-setup marker: invalid next_action {data['next_action']!r} "
                f"(allowed: {STEP_ENUM})"
            )

        # step_count 타입 — bool 도 int 의 subclass 라 명시 차단
        sc = data["step_count_so_far"]
        if not isinstance(sc, int) or isinstance(sc, bool):
            raise ValueError("external-setup marker: step_count_so_far must be int")
        mc = data.get("max_step_count", MAX_STEP_COUNT_DEFAULT)
        if not isinstance(mc, int) or isinstance(mc, bool):
            raise ValueError("external-setup marker: max_step_count must be int")

        # datetime — tzinfo 필수
        started_raw = data["started_at"]
        if not isinstance(started_raw, str):
            raise ValueError("external-setup marker: started_at must be ISO string")
        try:
            started_at = datetime.fromisoformat(started_raw)
        except ValueError as e:
            raise ValueError(f"external-setup marker: invalid started_at ({e})")
        if started_at.tzinfo is None:
            raise ValueError("external-setup marker: started_at must be tz-aware")

        return cls(
            started_at=started_at,
            company=data["company"],
            project=data["project"],
            current_step=data["current_step"],
            next_action=data["next_action"],
            step_count_so_far=sc,
            max_step_count=mc,
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

    def is_stale(self, now: datetime | None = None) -> bool:
        # from_dict 가 naive datetime 을 차단하므로 started_at 은 항상 tz-aware.
        now = now or datetime.now(timezone.utc)
        return (now - self.started_at) > timedelta(seconds=STALE_SECONDS)

    def is_exhausted(self) -> bool:
        return self.step_count_so_far > self.max_step_count


def marker_path(company: str) -> Path:
    """``~/.lskun-companies/<company>/.external-setup.json`` 절대경로."""
    return paths.company_root(company) / MARKER_FILENAME


def _atomic_write(path: Path, data: dict) -> None:
    """tmp + os.replace 로 atomic write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(path))


def read(company: str) -> ExternalSetupState | None:
    """marker 를 읽어 :class:`ExternalSetupState` 반환.

    부재 / malformed / stale / exhausted 면 ``None``. malformed·stale·exhausted
    의 경우 자동 unlink 하여 다음 ``start()`` 가 가능하게 만든다.
    """
    path = marker_path(company)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = ExternalSetupState.from_dict(data)
    except (json.JSONDecodeError, ValueError):
        _safe_unlink(path)
        return None
    if state.is_stale() or state.is_exhausted():
        _safe_unlink(path)
        return None
    return state


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def start(company: str, project: str) -> ExternalSetupState:
    """setup 시퀀스 시작 — marker 생성.

    살아있는 marker (stale/exhausted 아닌) 가 이미 있으면 ``ValueError`` raise.
    stale/exhausted marker 는 ``read()`` 가 자동 정리하므로 새로 시작 가능.
    """
    paths.validate_company_name(company)
    external.validate_project_name(project)

    # read() 가 stale/malformed 정리. 살아있으면 None 아님 → 거부.
    existing = read(company)
    if existing is not None:
        raise ValueError(
            f"external-setup marker already exists for company {company!r} "
            f"(project={existing.project!r}, step={existing.current_step!r}). "
            "finalize 먼저 호출하거나 marker 를 직접 정리하세요."
        )

    state = ExternalSetupState(
        started_at=datetime.now(timezone.utc),
        company=company,
        project=project,
        current_step="init",
        next_action="domain_assessment",
        step_count_so_far=1,
        max_step_count=MAX_STEP_COUNT_DEFAULT,
    )
    _atomic_write(marker_path(company), state.to_dict())
    return state


def advance(company: str, current_step: str, next_action: str) -> ExternalSetupState:
    """marker 의 current_step / next_action 을 갱신하고 step_count +1.

    Raises:
        ValueError: marker 부재, current_step 이 enum 위반, next_action 이 str 아님.
    """
    if current_step not in STEP_ENUM:
        raise ValueError(
            f"invalid current_step: {current_step!r} (allowed: {STEP_ENUM})"
        )
    if next_action not in STEP_ENUM:
        raise ValueError(
            f"invalid next_action: {next_action!r} (allowed: {STEP_ENUM})"
        )

    state = read(company)
    if state is None:
        raise ValueError(
            f"no live external-setup marker for company {company!r} — call start() first"
        )

    new_state = ExternalSetupState(
        started_at=state.started_at,
        company=state.company,
        project=state.project,
        current_step=current_step,
        next_action=next_action,
        step_count_so_far=state.step_count_so_far + 1,
        max_step_count=state.max_step_count,
    )
    _atomic_write(marker_path(company), new_state.to_dict())
    return new_state


def finalize(company: str) -> None:
    """setup 시퀀스 정상 완료 — marker 삭제. 부재해도 raise 안 함 (idempotent)."""
    paths.validate_company_name(company)
    path = marker_path(company)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def cancel(company: str) -> None:
    """진행 중인 외주 setup 사용자 명시 중단 — marker unlink. 부재 시 no-op.

    ``finalize`` 와 marker 정리 동작은 같으나 의미가 다르다 (finalize = 정상
    완료, cancel = 사용자 중단). audit entry 박제 (event_type=
    ``external_setup_cancelled``) 는 ``commands/external.md`` 가 호출하며, 본
    함수는 marker 정리만 담당 (SRP).
    """
    paths.validate_company_name(company)
    path = marker_path(company)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


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
    "cancel",
]
