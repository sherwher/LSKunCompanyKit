"""HR Lead 자동 채용의 audit log + rate-limit 가드.

ADR-0004 §3 — CPO 가 HR Lead 를 Task tool 로 호출하면 자동 채용이 진행된다.
사용자 알림 1줄 외 어떤 차단도 없는 정책은, 라우팅 오판이 누적되면 ``hired/``
가 무한 팽창할 위험을 안고 있다. 본 모듈은 다음 2가지를 제공한다:

1. **Audit log** — ``<company_root>/hired/.audit.jsonl`` 에 채용 이벤트 1줄 append.
   사람·코드 모두 손쉽게 grep / tail / parse 가능.
2. **Rate-limit** — 같은 ``role + domain`` 으로 ``cooldown_seconds`` 내 재채용 시도
   시 ``HireRateLimited`` 예외 raise. 기본값 30분.

HR Lead persona 는 본 모듈을 호출해 채용 직전 가드를 통과해야 한다. 사용자 명시
호출 (``/lskun-kit:hire``) 은 본 가드를 적용하지 않는다 (사람의 의사 결정 신뢰).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

AUDIT_FILENAME = ".audit.jsonl"
DEFAULT_COOLDOWN_SECONDS = 30 * 60  # 30분


class HireRateLimited(Exception):
    """동일 ``role + domain`` 채용 쿨다운 중일 때 raise.

    caller (HR Lead) 는 본 예외를 catch 해 CPO 에게 "기존 워커 추천" 응답으로
    전환해야 한다.
    """

    def __init__(self, role: str, domain: str, last_at: datetime, cooldown: int) -> None:
        super().__init__(
            f"hire rate-limited: role={role!r} domain={domain!r} "
            f"last_hired_at={last_at.isoformat()} cooldown={cooldown}s"
        )
        self.role = role
        self.domain = domain
        self.last_at = last_at
        self.cooldown = cooldown


@dataclass(frozen=True)
class HireEvent:
    """audit log 의 한 줄을 표현."""

    at: datetime
    actor: str  # "hr-lead" | "user" | "<other>"
    name: str
    role: str
    domain: str
    model: str | None
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "at": self.at.isoformat(),
            "actor": self.actor,
            "name": self.name,
            "role": self.role,
            "domain": self.domain,
            "model": self.model,
            "reason": self.reason,
        }


def audit_path(company_root: Path | str) -> Path:
    return Path(company_root).expanduser() / "hired" / AUDIT_FILENAME


def append_event(company_root: Path | str, event: HireEvent) -> Path:
    """audit log 에 1줄 append. ``hired/`` 디렉토리가 없으면 생성."""

    path = audit_path(company_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event.to_dict(), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return path


def read_events(company_root: Path | str) -> list[HireEvent]:
    """audit log 전체를 파싱. 손상된 줄은 silent skip."""

    path = audit_path(company_root)
    if not path.exists():
        return []
    out: list[HireEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            out.append(
                HireEvent(
                    at=datetime.fromisoformat(data["at"]),
                    actor=data["actor"],
                    name=data["name"],
                    role=data["role"],
                    domain=data["domain"],
                    model=data.get("model"),
                    reason=data.get("reason", ""),
                )
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    return out


def check_rate_limit(
    company_root: Path | str,
    role: str,
    domain: str,
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    now: datetime | None = None,
) -> None:
    """같은 ``role + domain`` 으로 ``cooldown_seconds`` 내 채용 이력 있으면 raise.

    user actor 의 이벤트는 무시 — 사람의 의사 결정은 신뢰한다.
    """

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=cooldown_seconds)
    for ev in reversed(read_events(company_root)):
        if ev.actor == "user":
            continue
        if ev.role != role or ev.domain != domain:
            continue
        if ev.at >= cutoff:
            raise HireRateLimited(role, domain, ev.at, cooldown_seconds)
        # 같은 role+domain 의 가장 최근 자동 채용이 cutoff 이전 → 통과.
        return


def record_hire(
    company_root: Path | str,
    actor: str,
    name: str,
    role: str,
    domain: str,
    model: str | None = None,
    reason: str = "",
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
    now: datetime | None = None,
) -> HireEvent:
    """rate-limit 검사 + audit 기록을 한 번에. ``actor='user'`` 는 검사 skip."""

    now = now or datetime.now(timezone.utc)
    if actor != "user":
        check_rate_limit(company_root, role, domain, cooldown_seconds, now=now)
    event = HireEvent(
        at=now, actor=actor, name=name, role=role, domain=domain,
        model=model, reason=reason,
    )
    append_event(company_root, event)
    return event


__all__ = [
    "AUDIT_FILENAME",
    "DEFAULT_COOLDOWN_SECONDS",
    "HireRateLimited",
    "HireEvent",
    "audit_path",
    "append_event",
    "read_events",
    "check_rate_limit",
    "record_hire",
]
