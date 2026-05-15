"""Reflection 자동화 — 작업 종료 시 1줄을 history 에 append.

ADR-0001 §3 의 핵심 동작. 호출자는 두 종류:

1. ``/lskun-kit:reflect`` — 사용자 명시 입력
2. ``hooks/stop_reflect.py`` — Stop hook 이 세션 상태와 함께 자동 호출
"""

from __future__ import annotations

from datetime import date as date_cls

from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.models import HistoryEntry


def record(
    adapter: StorageAdapter,
    worker: str,
    project: str,
    topic: str,
    pattern: str,
    first_pass_score: int,
    when: date_cls | None = None,
) -> HistoryEntry:
    """워커 history 에 1줄을 append 하고 :class:`HistoryEntry` 를 반환한다.

    입력 검증:
        - project / topic 에 ``/`` 가 들어가면 ValueError (구분자 충돌)
        - first_pass_score 는 0..100 범위
    """

    for label, value in (("project", project), ("topic", topic), ("pattern", pattern)):
        if not value or "/" in value:
            raise ValueError(f"{label} must be non-empty and contain no '/': {value!r}")
    if not 0 <= int(first_pass_score) <= 100:
        raise ValueError(
            f"first_pass_score must be 0..100, got {first_pass_score!r}"
        )

    entry = HistoryEntry(
        date=when or date_cls.today(),
        project=project,
        topic=topic,
        pattern=pattern,
        first_pass_score=int(first_pass_score),
    )
    adapter.append_history(worker, entry)
    return entry
