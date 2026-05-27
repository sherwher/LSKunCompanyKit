"""Audit log read-only view — P109-A.

``.audit/decisions.jsonl`` (현재 월) + ``.audit/decisions.<YYYY-MM>.jsonl.gz``
(회전된 월, P109-B 와 연동) 를 읽어 워커별 dispatch count + last_seen 집계.

원칙 (불변):
    - **read-only** — audit 파일을 수정하지 않음 (ADR-0006 정신)
    - **best-effort** — 불량 JSON 라인 1개로 전체 fail 하지 않음
    - **사용자 명시 옵션** — 자동 집계 호출 없음 (org.build(with_usage=True) 또는 cli_org --usage)
    - **평가 없음** — 단순 count + ISO timestamp. 랭킹·점수·hint 0
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkerUsage:
    """워커 1명의 audit log 집계.

    - ``dispatches``: 본 워커가 ``worker`` 필드로 박제된 entry 총 수
    - ``last_seen``: 가장 최근 entry 의 ``ts`` (ISO 8601 UTC) 또는 ``None``
    """

    name: str
    dispatches: int
    last_seen: str | None


def _iter_audit_lines(audit_dir: Path):
    """``audit_dir`` 의 모든 audit 파일 (현재 + 회전된) 의 라인을 yield.

    파일 발견 순서:
        1. ``decisions.jsonl`` (현재 월, 평문)
        2. ``decisions.*.jsonl.gz`` (회전된, P109-B)

    각 파일 부재 시 silently skip. 파일 자체를 못 읽으면 (permission 등) skip.
    """

    if not audit_dir.exists() or not audit_dir.is_dir():
        return

    current = audit_dir / "decisions.jsonl"
    if current.exists() and current.is_file():
        try:
            with current.open("r", encoding="utf-8") as f:
                for line in f:
                    yield line
        except OSError:
            pass

    for path in sorted(audit_dir.glob("decisions.*.jsonl.gz")):
        if not path.is_file():
            continue
        try:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                for line in f:
                    yield line
        except OSError:
            continue


def read_usage(audit_dir: Path) -> dict[str, WorkerUsage]:
    """``audit_dir`` 의 모든 audit 파일을 집계해 워커별 ``WorkerUsage`` 반환.

    Args:
        audit_dir: ``<company_root>/.audit/`` 절대 경로.

    Returns:
        ``{worker_name: WorkerUsage}``. 파일 부재 / audit 0건 시 빈 dict.

    Best-effort:
        - 빈 라인 skip
        - JSON parse 실패 skip
        - ``worker`` 필드 부재·비-str skip
        - ``ts`` 부재 시 entry 카운트는 하되 last_seen 갱신 안 함
    """

    counts: dict[str, int] = {}
    last_seen: dict[str, str] = {}

    for raw in _iter_audit_lines(audit_dir):
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(entry, dict):
            continue
        worker = entry.get("worker")
        if not isinstance(worker, str) or not worker:
            continue

        counts[worker] = counts.get(worker, 0) + 1

        ts = entry.get("ts")
        if isinstance(ts, str) and ts:
            prev = last_seen.get(worker)
            # ISO 8601 UTC 문자열은 lexicographic compare 가 시간 순서 보존.
            if prev is None or ts > prev:
                last_seen[worker] = ts

    return {
        name: WorkerUsage(
            name=name,
            dispatches=counts[name],
            last_seen=last_seen.get(name),
        )
        for name in counts
    }


__all__ = ["WorkerUsage", "read_usage"]
