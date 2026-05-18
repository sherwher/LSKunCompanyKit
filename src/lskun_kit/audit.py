"""CPO 결재 audit log — ADR-0006.

``.audit/decisions.jsonl`` (append-only JSONL) 에 CPO 의 결재 의사결정을 박제한다.
reflection 과 ``request_id`` (uuid4) 로 1:1 link.

호출자는 메인 세션 = CPO. hook 자동화는 도입하지 않는다 (ADR-0006 §2).

원칙 (불변, ADR-0006 §6):
    - append-only (overwrite/delete 금지)
    - 1줄 1 JSON object
    - ``request_id`` 필수
    - ``verdict`` enum 외 거부
    - ``.audit/`` 자동 생성
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.errors import LSKunKitError

#: ADR-0006 §5 — 결재 verdict enum
VERDICT_APPROVED = "approved"
VERDICT_REWORK = "rework"
VERDICT_REJECTED = "rejected"
VERDICT_REROUTED = "rerouted"
_VALID_VERDICTS = frozenset({
    VERDICT_APPROVED, VERDICT_REWORK, VERDICT_REJECTED, VERDICT_REROUTED,
})

AUDIT_DIRNAME = ".audit"
AUDIT_FILENAME = "decisions.jsonl"


class AuditError(LSKunKitError):
    """audit schema 위반."""


@dataclass(frozen=True)
class AuditEntry:
    """CPO 결재 1건. ADR-0006 §4 schema."""

    request_id: str
    company: str
    worker: str
    domain: str
    model: str
    first_pass_score: int
    rounds: int
    verdict: str
    reason: str
    auto_hired: bool
    final_score: int | None = None
    router: str = "cpo"
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.request_id:
            raise AuditError("request_id is required")
        if self.verdict not in _VALID_VERDICTS:
            raise AuditError(
                f"verdict must be one of {sorted(_VALID_VERDICTS)}, "
                f"got {self.verdict!r}"
            )
        if not 0 <= int(self.first_pass_score) <= 100:
            raise AuditError(
                f"first_pass_score must be 0..100, got {self.first_pass_score!r}"
            )
        if self.final_score is not None and not 0 <= int(self.final_score) <= 100:
            raise AuditError(
                f"final_score must be 0..100 or None, got {self.final_score!r}"
            )
        if int(self.rounds) < 1:
            raise AuditError(f"rounds must be >= 1, got {self.rounds!r}")
        if not self.reason or not self.reason.strip():
            raise AuditError("reason must be non-empty")
        for label, value in (
            ("company", self.company), ("worker", self.worker),
            ("domain", self.domain), ("model", self.model),
        ):
            if not value or not str(value).strip():
                raise AuditError(f"{label} must be non-empty")

    def to_json_line(self) -> str:
        """JSONL 1줄로 직렬화 (newline 미포함)."""
        return json.dumps(asdict(self), ensure_ascii=False, separators=(",", ":"))


def new_request_id() -> str:
    """uuid4 hex 32자 (dash 없음)."""
    return uuid.uuid4().hex


def record(adapter: StorageAdapter, entry: AuditEntry) -> Path:
    """schema 검증 후 adapter.append_audit() 로 append. 박제된 파일 경로 반환."""
    return adapter.append_audit(entry.to_json_line())


__all__ = [
    "AUDIT_DIRNAME",
    "AUDIT_FILENAME",
    "VERDICT_APPROVED",
    "VERDICT_REWORK",
    "VERDICT_REJECTED",
    "VERDICT_REROUTED",
    "AuditError",
    "AuditEntry",
    "new_request_id",
    "record",
]
