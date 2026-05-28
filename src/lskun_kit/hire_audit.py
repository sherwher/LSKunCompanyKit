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
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lskun_kit.errors import LSKunKitError

AUDIT_FILENAME = ".audit.jsonl"
DEFAULT_COOLDOWN_SECONDS = 30 * 60  # 30분


class HireRateLimited(LSKunKitError):
    """동일 ``role + domain`` 채용 쿨다운 중일 때 raise.

    P41 — ``LSKunKitError`` 를 상속해 ``except LSKunKitError`` 일괄 catch 가 동작.
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
class AuditEvent:
    """P45 (#16) — 일반화된 audit log 이벤트.

    ``event_type`` 으로 hire/fire/evaluate 등을 구분, payload 에 타입별 필드 보관.
    HR 평가·해고 등 향후 audit 이벤트를 같은 ``.audit.jsonl`` 에 통합 보관 가능.
    """

    at: datetime
    actor: str
    event_type: str  # "hire" | "fire" | "evaluate" | ...
    payload: dict

    def to_dict(self) -> dict:
        return {
            "at": self.at.isoformat(),
            "actor": self.actor,
            "event_type": self.event_type,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class HireEvent:
    """audit log 의 hire 이벤트 (backward-compatible 표현).

    P45 이전의 평탄 스키마 (at/actor/name/role/domain/model/reason) 를 유지하되
    내부적으로는 :class:`AuditEvent` 와 상호 변환 가능. JSONL 에 저장될 때는
    평탄 형태 (기존 포맷) 와 새 형태 (``event_type="hire"`` + ``payload``) 둘 다
    read 시 정상 파싱된다.
    """

    at: datetime
    actor: str  # "hr-lead" | "user" | "<other>"
    name: str
    role: str
    domain: str
    model: str | None
    reason: str = ""

    def to_dict(self) -> dict:
        # 기존 호환 — 평탄 키 유지
        return {
            "at": self.at.isoformat(),
            "actor": self.actor,
            "name": self.name,
            "role": self.role,
            "domain": self.domain,
            "model": self.model,
            "reason": self.reason,
        }

    def to_audit_event(self) -> AuditEvent:
        return AuditEvent(
            at=self.at,
            actor=self.actor,
            event_type="hire",
            payload={
                "name": self.name,
                "role": self.role,
                "domain": self.domain,
                "model": self.model,
                "reason": self.reason,
            },
        )


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
    """hire 이벤트만 추려 :class:`HireEvent` 목록으로 반환. 손상 / 다른 event_type 은 skip.

    P45 — 평탄 스키마 (P32) 와 일반화 스키마 (``event_type=hire`` + ``payload``)
    모두 호환. ``read_audit_events`` 로 모든 이벤트 일반 형태로 읽을 수도 있다.
    """

    out: list[HireEvent] = []
    for ev in read_audit_events(company_root):
        if ev.event_type != "hire":
            continue
        p = ev.payload
        try:
            out.append(
                HireEvent(
                    at=ev.at, actor=ev.actor,
                    name=p["name"], role=p["role"], domain=p["domain"],
                    model=p.get("model"), reason=p.get("reason", ""),
                )
            )
        except KeyError:
            continue
    return out


def read_audit_events(company_root: Path | str) -> list[AuditEvent]:
    """P45 (#16) — 모든 audit 이벤트를 일반 형태로 읽는다.

    JSONL 에 평탄 스키마 (구) 와 일반화 스키마 (신) 가 섞여 있어도 둘 다 정상 파싱.
    손상된 줄은 silent skip.
    """

    path = audit_path(company_root)
    if not path.exists():
        return []
    out: list[AuditEvent] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            at = datetime.fromisoformat(data["at"])
            actor = data["actor"]
            if "event_type" in data and "payload" in data:
                # 신규 일반화 스키마
                out.append(
                    AuditEvent(
                        at=at, actor=actor,
                        event_type=data["event_type"],
                        payload=dict(data["payload"]),
                    )
                )
            else:
                # P32 평탄 스키마 — hire 로 간주
                out.append(
                    AuditEvent(
                        at=at, actor=actor, event_type="hire",
                        payload={
                            "name": data["name"],
                            "role": data["role"],
                            "domain": data["domain"],
                            "model": data.get("model"),
                            "reason": data.get("reason", ""),
                        },
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
    """rate-limit 검사 + audit 기록을 한 번에. ``actor='user'`` 는 검사 skip.

    P39 (#11) — timestamp tampering 가드:
        직전 audit 이벤트의 ``at`` 보다 ``now`` 가 과거이면 stderr 로 경고 emit.
        공유 Vault 환경에서 다른 사용자가 JSONL 을 손편집해 rate-limit 우회
        시도하는 것을 가시화한다.
    """

    now = now or datetime.now(timezone.utc)

    previous = read_events(company_root)
    if previous and now < previous[-1].at:
        print(
            f"lskun-kit: WARNING — audit timestamp regression detected "
            f"(new={now.isoformat()} < last={previous[-1].at.isoformat()}). "
            f"공유 SSOT 환경에서 .audit.jsonl 손편집 가능성. 검토 필요.",
            file=sys.stderr,
        )

    if actor != "user":
        check_rate_limit(company_root, role, domain, cooldown_seconds, now=now)
    event = HireEvent(
        at=now, actor=actor, name=name, role=role, domain=domain,
        model=model, reason=reason,
    )
    append_event(company_root, event)
    return event


def record_external_onboard(
    target_path: Path | str,
    *,
    actor: str,
    name: str,
    kind: str,
    project: str,
    at: datetime | None = None,
) -> None:
    """외주 (레드팀/고객) 박제를 audit 에 기록 — ADR-0021.

    hire rate-limit (같은 role+domain 30분) 을 타지 않는다. 고객 N명은 같은
    role(customer) 로 동시 다수 박제가 정상이기 때문 (``event_type`` 분리).

    ADR-0006 정신: 단발 기록만. 집계/KPI/대시보드 금지.

    ``target_path`` 는 (company_root 가 아닌) 기록할 JSONL 파일 경로 자체다.
    부모 디렉토리가 없으면 생성한다. JSONL 직렬화는 :meth:`AuditEvent.to_dict`
    + :func:`append_event` 와 동일한 ``ensure_ascii=False`` 한 줄 append.
    """

    path = Path(target_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = AuditEvent(
        at=at or datetime.now(timezone.utc),
        actor=actor,
        event_type="onboard_external",
        payload={"name": name, "kind": kind, "project": project},
    )
    line = json.dumps(event.to_dict(), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


__all__ = [
    "AUDIT_FILENAME",
    "DEFAULT_COOLDOWN_SECONDS",
    "HireRateLimited",
    "AuditEvent",
    "HireEvent",
    "audit_path",
    "append_event",
    "read_events",
    "read_audit_events",
    "check_rate_limit",
    "record_hire",
    "record_external_onboard",
]
