"""Audit log 회전 — P109-B.

``.audit/decisions.jsonl`` 의 무한 누적 차단. 옛 월 entry 를
``decisions.<YYYY-MM>.jsonl.gz`` 로 gzip 묶음, 현재 월만 평문 jsonl 에 남김.

원칙 (불변):
    - **사용자 명시 명령만** — 자동 회전 X (ADR-0006 §6 정합)
    - **append-only 유지** — 옛 데이터 rewrite 절대 금지 (월별 묶기 = ts 보존, 내용 불변)
    - **idempotent** — 재실행 시 이미 회전된 파일에 append 안 함
    - **atomic-ish** — gzip 파일 먼저 write → 원본 truncate. 중간 실패 시 데이터 손실 0
    - **`/org --usage` 정합** — read_usage 가 회전된 파일도 읽음 (P109-A 와 연동)
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


class AuditRotateError(Exception):
    """audit 회전 실패."""


@dataclass(frozen=True)
class MonthBucket:
    """단일 월의 회전 대상."""

    month: str  # "YYYY-MM"
    lines: list[str] = field(default_factory=list)


@dataclass
class RotationPlan:
    """``plan_rotation()`` 의 결과 — 어떤 월이 어디로 가는지.

    - ``current_month``: 평문 ``decisions.jsonl`` 에 남길 월. ``None`` 이면 빈 파일
    - ``rotate_buckets``: 회전 대상 (옛 월) — 각자 ``decisions.<month>.jsonl.gz`` 로
    - ``malformed_count``: parse 실패 라인 수 (best-effort, plan 단계에서 skip)
    """

    audit_dir: Path
    current_month: str | None = None
    current_lines: list[str] = field(default_factory=list)
    rotate_buckets: list[MonthBucket] = field(default_factory=list)
    malformed_count: int = 0

    @property
    def is_no_op(self) -> bool:
        return not self.rotate_buckets

    def render(self) -> str:
        lines = [
            "Audit Log Rotation Plan",
            "================================================",
            f"audit dir       : {self.audit_dir}",
            f"current month   : {self.current_month or '(none)'}",
            f"current lines   : {len(self.current_lines)}",
            f"malformed lines : {self.malformed_count} (skipped)",
            "",
            f"회전 대상       : {len(self.rotate_buckets)} buckets",
        ]
        for b in self.rotate_buckets:
            lines.append(f"  - {b.month}: {len(b.lines)} entries → decisions.{b.month}.jsonl.gz")
        if self.is_no_op:
            lines.append("")
            lines.append("결과: 회전 불필요 (옛 월 entry 0건).")
        return "\n".join(lines) + "\n"


def _extract_month(line: str) -> str | None:
    """JSONL 1줄에서 ``ts`` ISO 문자열 앞 7자 (``YYYY-MM``) 추출.

    schema 검증 안 함 (best-effort). ``ts`` 부재 / 비-str / 형식 불일치 시 None.
    """

    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(obj, dict):
        return None
    ts = obj.get("ts")
    if not isinstance(ts, str) or len(ts) < 7:
        return None
    month = ts[:7]
    # "YYYY-MM" 형식 가벼운 검증
    if len(month) == 7 and month[4] == "-" and month[:4].isdigit() and month[5:].isdigit():
        return month
    return None


def _today_month_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def plan_rotation(
    audit_dir: Path,
    now_month: str | None = None,
) -> RotationPlan:
    """회전 계획 작성. **어떤 파일도 수정하지 않는다**.

    Args:
        audit_dir: ``<company_root>/.audit/`` 경로
        now_month: 현재 월 (``"YYYY-MM"``). ``None`` 이면 ``datetime.now(UTC)`` 사용.
            테스트 시 명시 주입 권장.

    Returns:
        ``RotationPlan``. 파일 부재 / decisions.jsonl 부재 시 no-op plan.
    """

    current_month = now_month or _today_month_utc()
    plan = RotationPlan(audit_dir=audit_dir, current_month=current_month)

    current_path = audit_dir / "decisions.jsonl"
    if not current_path.exists() or not current_path.is_file():
        return plan

    bucket_map: dict[str, list[str]] = {}
    malformed = 0
    with current_path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n").rstrip("\r")
            if not line.strip():
                continue
            month = _extract_month(line)
            if month is None:
                malformed += 1
                # malformed 는 현재 월에 잔존시켜 사용자 수동 정리 가능하게 함
                plan.current_lines.append(line)
                continue
            if month == current_month:
                plan.current_lines.append(line)
            else:
                bucket_map.setdefault(month, []).append(line)

    plan.malformed_count = malformed
    for month in sorted(bucket_map.keys()):
        plan.rotate_buckets.append(MonthBucket(month=month, lines=bucket_map[month]))
    return plan


def execute_rotation(plan: RotationPlan) -> RotationPlan:
    """``plan`` 실행. gzip write → 원본 truncate 순서.

    Idempotent: 이미 ``decisions.<month>.jsonl.gz`` 가 있으면 그 월 bucket 의 lines
    를 append (gzip 안에서). 옛 데이터 손실 0.

    Atomic-ish:
        1. 각 bucket → ``decisions.<month>.jsonl.gz`` write (덮어쓰기 아닌 append)
        2. 모두 성공 시 ``decisions.jsonl`` 을 ``current_lines`` 만으로 rewrite
    """

    if plan.is_no_op:
        return plan

    for bucket in plan.rotate_buckets:
        rotated_path = plan.audit_dir / f"decisions.{bucket.month}.jsonl.gz"
        # 기존 회전 파일이 있으면 그 내용을 먼저 읽어 합침 (idempotent)
        existing_lines: list[str] = []
        if rotated_path.exists():
            try:
                with gzip.open(rotated_path, "rt", encoding="utf-8") as f:
                    existing_lines = [ln.rstrip("\n").rstrip("\r") for ln in f if ln.strip()]
            except OSError as exc:
                raise AuditRotateError(
                    f"failed to read existing rotated file: {rotated_path} ({exc})"
                ) from exc
        merged = existing_lines + bucket.lines
        body = ("\n".join(merged) + "\n").encode("utf-8")
        try:
            with gzip.open(rotated_path, "wb") as f:
                f.write(body)
        except OSError as exc:
            raise AuditRotateError(
                f"failed to write rotated file: {rotated_path} ({exc})"
            ) from exc

    # 원본 truncate — 현재 월 lines 만 남김
    current_path = plan.audit_dir / "decisions.jsonl"
    new_body = ("\n".join(plan.current_lines) + "\n") if plan.current_lines else ""
    current_path.write_text(new_body, encoding="utf-8")
    return plan


def render_result(plan: RotationPlan) -> str:
    lines = [
        "Audit Log Rotation Result",
        "================================================",
        f"audit dir       : {plan.audit_dir}",
        f"current 잔존    : {len(plan.current_lines)} lines",
    ]
    total = 0
    for b in plan.rotate_buckets:
        lines.append(f"  - decisions.{b.month}.jsonl.gz: {len(b.lines)} entries 박제")
        total += len(b.lines)
    lines.append("")
    lines.append(f"총 회전: {total} entries")
    return "\n".join(lines) + "\n"


__all__ = [
    "AuditRotateError",
    "MonthBucket",
    "RotationPlan",
    "plan_rotation",
    "execute_rotation",
    "render_result",
]
