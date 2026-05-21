"""audit ↔ reflection cross-check 진단 — P76 박제.

doctor (`/lskun-kit:doctor`) 진단 항목 추가용 helper. 다음을 검출:
- audit 에 `approved` verdict 가 박혀있는 request_id 중, 어느 워커 history 에도
  대응 entry 가 없는 누락 케이스.
- legacy entry (request_id 없음) 와 신규 entry (request_id 박힘) 의 비율.

본 모듈은 **read-only**. 자동 복구하지 않는다 (사용자가 doctor 결과를 보고
`/lskun-kit:reflect` 로 수동 정정).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.audit import AUDIT_DIRNAME, AUDIT_FILENAME, VERDICT_APPROVED

#: HistoryEntry.render() (P76 신 format) 의 `req:XXXXXXXX` 박제 매처.
_RE_REQ = re.compile(r"\breq:([0-9a-f]{6,})\b")


@dataclass(frozen=True)
class CrossCheckReport:
    """audit vs reflection 정합성 진단 결과."""

    audit_approved_count: int
    reflection_entries_total: int
    reflection_entries_with_req: int
    reflection_entries_legacy: int  # request_id 없는 옛 entry
    missing_request_ids: tuple[str, ...]  # audit approved 인데 history 박제 안 됨
    coverage_pct: float  # request_id 박힌 entry / approved audit 비율 (0..100)

    def is_healthy(self) -> bool:
        """누락 0 + coverage ≥ 80% 면 healthy."""
        return not self.missing_request_ids and self.coverage_pct >= 80.0


def _iter_audit_approved_ids(company_root: Path) -> list[str]:
    """`.audit/decisions.jsonl` 에서 verdict=approved 의 request_id 목록."""
    audit_file = company_root / AUDIT_DIRNAME / AUDIT_FILENAME
    if not audit_file.exists():
        return []
    ids: list[str] = []
    for line in audit_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("verdict") == VERDICT_APPROVED:
            rid = obj.get("request_id")
            if rid:
                ids.append(rid)
    return ids


def _scan_history_entries(company_root: Path) -> tuple[int, int, set[str]]:
    """`hired/*.md` 의 `## Project History` 섹션을 전체 스캔.

    Returns:
        (전체_entry_수, request_id_박힌_entry_수, 박힌_req_id_8자_접두사_set)
    """
    hired = company_root / "hired"
    if not hired.exists():
        return (0, 0, set())
    total = 0
    with_req = 0
    seen_prefixes: set[str] = set()
    for path in hired.glob("*.md"):
        if path.name.endswith(".bak"):
            continue
        text = path.read_text(encoding="utf-8")
        if "## Project History" not in text:
            continue
        section = text.split("## Project History", 1)[1]
        for raw in section.splitlines():
            line = raw.strip()
            if not (line.startswith("- ") and "first-pass" in line):
                continue
            total += 1
            m = _RE_REQ.search(line)
            if m:
                with_req += 1
                seen_prefixes.add(m.group(1))
    return (total, with_req, seen_prefixes)


def build(adapter: StorageAdapter) -> CrossCheckReport:
    """audit ↔ reflection cross-check. read-only."""
    if not hasattr(adapter, "root"):
        raise ValueError("adapter has no root attribute — cross-check 불가")
    company_root = Path(getattr(adapter, "root"))

    audit_ids = _iter_audit_approved_ids(company_root)
    total, with_req, seen_prefixes = _scan_history_entries(company_root)

    # 누락 검출: audit approved 인데 어느 history entry 의 req:접두사와도 매치 안 됨.
    # HistoryEntry.render() 가 `req:{request_id[:8]}` 로 박제하므로 8자 접두사 비교.
    missing = tuple(
        sorted(
            rid for rid in audit_ids
            if rid[:8] not in seen_prefixes
        )
    )
    coverage = (
        100.0 if not audit_ids
        else round((len(audit_ids) - len(missing)) / len(audit_ids) * 100, 1)
    )

    return CrossCheckReport(
        audit_approved_count=len(audit_ids),
        reflection_entries_total=total,
        reflection_entries_with_req=with_req,
        reflection_entries_legacy=total - with_req,
        missing_request_ids=missing,
        coverage_pct=coverage,
    )


def render(report: CrossCheckReport) -> str:
    """진단 결과를 사람이 읽는 텍스트로."""
    icon = "✅" if report.is_healthy() else "⚠️"
    lines = [
        f"{icon} audit ↔ reflection cross-check (P76)",
        f"  - audit approved: {report.audit_approved_count}건",
        f"  - history entries (총): {report.reflection_entries_total}",
        f"    · request_id 박힘: {report.reflection_entries_with_req}",
        f"    · legacy (req 없음): {report.reflection_entries_legacy}",
        f"  - coverage: {report.coverage_pct}%",
    ]
    if report.missing_request_ids:
        lines.append(
            f"  ⚠️ 누락 {len(report.missing_request_ids)}건: "
            f"{', '.join(rid[:8] for rid in report.missing_request_ids[:5])}"
            + ("..." if len(report.missing_request_ids) > 5 else "")
        )
        lines.append(
            "    → 사용자 명시 `/lskun-kit:reflect` 로 정정 가능 (자동 복구 X)"
        )
    return "\n".join(lines) + "\n"


__all__ = ["CrossCheckReport", "build", "render"]
