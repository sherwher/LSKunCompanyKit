"""Reflection 자동화 — 작업 종료 시 1줄을 history 에 append.

ADR-0001 §3 의 핵심 동작. 호출자는 두 종류:

1. ``/lskun-kit:reflect`` — 사용자 명시 입력
2. ``hooks/stop_reflect.py`` — Stop hook 이 세션 상태와 함께 자동 호출

P30 — Reflection 진실성 가드:
    ``outcome`` 인자로 ``"success" | "aborted"`` 를 받아 ``aborted`` 면
    history append 를 skip 한다. 실패·중단된 작업이 첨자 first-pass 점수와 함께
    워커 history 를 오염시키는 것을 방지한다.
"""

from __future__ import annotations

from datetime import date as date_cls

from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.models import HistoryEntry

#: P30 — outcome 가 본 값이면 박제 skip (호출은 성공으로 처리).
OUTCOME_SUCCESS = "success"
OUTCOME_ABORTED = "aborted"
_VALID_OUTCOMES = frozenset({OUTCOME_SUCCESS, OUTCOME_ABORTED})


class ReflectionSkipped(Exception):
    """outcome=aborted 에 의해 박제가 의도적으로 skip 됐음을 caller 에 알린다.

    caller (Stop hook / slash command) 는 본 예외를 catch 해 silent 처리한다.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def record(
    adapter: StorageAdapter,
    worker: str,
    project: str,
    topic: str,
    pattern: str,
    first_pass_score: int,
    when: date_cls | None = None,
    outcome: str = OUTCOME_SUCCESS,
) -> HistoryEntry:
    """워커 history 에 1줄을 append 하고 :class:`HistoryEntry` 를 반환한다.

    입력 검증:
        - project / topic / pattern 에 ``/`` 가 들어가면 ValueError (구분자 충돌)
        - first_pass_score 는 0..100 범위
        - outcome 는 ``"success" | "aborted"`` (그 외는 ValueError)

    Raises:
        ReflectionSkipped: ``outcome=aborted`` 일 때. caller 가 silent 처리해야 한다.
    """

    if outcome not in _VALID_OUTCOMES:
        raise ValueError(
            f"outcome must be one of {sorted(_VALID_OUTCOMES)}, got {outcome!r}"
        )
    if outcome == OUTCOME_ABORTED:
        raise ReflectionSkipped(
            f"reflection skipped for worker={worker!r}: outcome=aborted"
        )

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
