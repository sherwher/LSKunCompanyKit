"""Reflection 자동화 — 작업 종료 시 1줄을 history 에 append.

ADR-0001 §3 의 핵심 동작. 호출자는 두 종류:

1. ``/lskun-kit:reflect`` — 사용자 명시 입력 (정정 경로)
2. CPO 결재 절차 §4 — 워커 보고를 받은 직후 (메인 경로)

P30 — Reflection 진실성 가드:
    ``outcome`` 인자로 ``"success" | "aborted"`` 를 받아 ``aborted`` 면
    history append 를 skip 한다. 실패·중단된 작업이 첨자 first-pass 점수와 함께
    워커 history 를 오염시키는 것을 방지한다.

P76 — 입력 방식 재설계 (4 에이전트 합의안):
    1. ``record_from_report()`` 신규 — 워커 보고 markdown 의 ``## reflection 후보``
       섹션에서 topic/pattern/한줄 을 plugin core 가 자동 파싱. CPO 가 entry 를
       직접 짜지 않음 → 530자 narrative 변질 원천 차단.
    2. ``HistoryEntry`` 에 ``outcome`` + ``request_id`` 필드 추가.
       ``h=N`` 카운트가 audit log 와 cross-check 가능해짐.
    3. ``topic`` / ``pattern`` 각 ``HISTORY_FIELD_MAX_LEN`` (80자) 길이 가드.
    4. 옛 ``record()`` 는 deprecated — 하위호환 유지 (수동 정정 경로용).
"""

from __future__ import annotations

import re
import warnings
from datetime import date as date_cls

from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.errors import LSKunKitError
from lskun_kit.models import HISTORY_FIELD_MAX_LEN, HistoryEntry

#: P30 — outcome 가 본 값이면 박제 skip (호출은 성공으로 처리).
OUTCOME_SUCCESS = "success"
OUTCOME_ABORTED = "aborted"
_VALID_OUTCOMES = frozenset({OUTCOME_SUCCESS, OUTCOME_ABORTED})

#: P76 — HistoryEntry.outcome 의 valid set (audit verdict 와 정합).
VALID_ENTRY_OUTCOMES = frozenset({"approved", "rework", "rejected"})


class ReflectionSkipped(LSKunKitError):
    """outcome=aborted 에 의해 박제가 의도적으로 skip 됐음을 caller 에 알린다.

    P41 — ``LSKunKitError`` 를 상속해 ``except LSKunKitError`` 일괄 catch 가 동작.
    caller (Stop hook / slash command) 는 본 예외를 catch 해 silent 처리한다.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ReportParseError(LSKunKitError):
    """워커 보고 markdown 에서 reflection 후보 섹션 파싱 실패."""


# P76 — 보고 양식 파싱 정규식. cpo.md §"보고 양식" 참조.
_RE_TOPIC = re.compile(r"^\s*-\s*topic:\s*(.+?)\s*$", re.MULTILINE)
_RE_PATTERN = re.compile(r"^\s*-\s*pattern:\s*(.+?)\s*$", re.MULTILINE)
_RE_FIRSTPASS = re.compile(
    r"first-pass\s*(?:자가\s*)?점수[^\d]*([0-9]+)\s*%?", re.IGNORECASE
)
_RE_REFLECTION_SECTION = re.compile(
    r"##\s*reflection\s*후보\s*\n(.*?)(?=\n##\s|\Z)", re.DOTALL | re.IGNORECASE
)


def _validate_field(label: str, value: str) -> str:
    """topic/pattern 단일 필드 검증 — 비어있지 않고, 길이 ≤ 80, 줄바꿈 X, ``/`` X."""
    if not value or not value.strip():
        raise ValueError(f"{label} must be non-empty")
    value = value.strip()
    if "/" in value:
        raise ValueError(f"{label} must not contain '/': {value!r}")
    if "\n" in value or "\r" in value:
        raise ValueError(f"{label} must not contain newline: {value!r}")
    if len(value) > HISTORY_FIELD_MAX_LEN:
        raise ValueError(
            f"{label} too long ({len(value)} > {HISTORY_FIELD_MAX_LEN}): "
            f"{value[:30]!r}..."
        )
    return value


def record_from_report(
    adapter: StorageAdapter,
    worker: str,
    project: str,
    report_md: str,
    request_id: str,
    outcome: str = "approved",
    when: date_cls | None = None,
) -> HistoryEntry:
    """워커 보고 markdown 에서 reflection entry 를 자동 파싱·박제.

    **P76 권장 진입점.** CPO 가 entry 를 직접 짜지 않음으로써 narrative 변질
    (530자 압축) 을 원천 차단.

    파싱 규칙 (cpo.md §"보고 양식"):
        - ``## reflection 후보`` 섹션 추출
        - 그 안의 ``- topic: <한 단어>`` / ``- pattern: <한 단어>`` 줄 추출
        - first-pass 점수는 보고 본문 어디든의 ``first-pass ... N%`` 패턴
        - 각 필드는 ``_validate_field`` 길이/줄바꿈 가드 통과 필수

    Raises:
        ReflectionSkipped: outcome 이 audit aborted 신호로 명시되면 (구현 예약)
        ReportParseError: reflection 후보 섹션이 없거나 필수 필드 누락
        ValueError: 필드 검증 실패
    """

    if not request_id:
        raise ValueError("request_id is required (P76 — audit cross-check)")
    if outcome not in VALID_ENTRY_OUTCOMES:
        raise ValueError(
            f"outcome must be one of {sorted(VALID_ENTRY_OUTCOMES)}, got {outcome!r}"
        )

    section_match = _RE_REFLECTION_SECTION.search(report_md)
    if not section_match:
        raise ReportParseError(
            "워커 보고에 '## reflection 후보' 섹션이 없습니다. "
            "cpo.md §보고 양식 참조."
        )
    section = section_match.group(1)

    topic_match = _RE_TOPIC.search(section)
    pattern_match = _RE_PATTERN.search(section)
    if not (topic_match and pattern_match):
        raise ReportParseError(
            "reflection 후보 섹션에 'topic:' 또는 'pattern:' 줄이 없습니다."
        )

    score_match = _RE_FIRSTPASS.search(report_md)
    if not score_match:
        raise ReportParseError(
            "보고 본문에 'first-pass ... N%' 점수가 없습니다."
        )
    score = int(score_match.group(1))
    if not 0 <= score <= 100:
        raise ValueError(f"first_pass_score out of range: {score}")

    topic = _validate_field("topic", topic_match.group(1))
    pattern = _validate_field("pattern", pattern_match.group(1))
    project = _validate_field("project", project)

    entry = HistoryEntry(
        date=when or date_cls.today(),
        project=project,
        topic=topic,
        pattern=pattern,
        first_pass_score=score,
        outcome=outcome,
        request_id=request_id,
    )
    adapter.append_history(worker, entry)
    return entry


def record(
    adapter: StorageAdapter,
    worker: str,
    project: str,
    topic: str,
    pattern: str,
    first_pass_score: int,
    when: date_cls | None = None,
    outcome: str = OUTCOME_SUCCESS,
    request_id: str | None = None,
) -> HistoryEntry:
    """워커 history 에 1줄을 append 하고 :class:`HistoryEntry` 를 반환한다.

    .. deprecated:: 0.16 (P76)
        ``record_from_report()`` 사용을 권장한다. 본 함수는 ``/lskun-kit:reflect``
        사용자 정정 경로의 하위호환을 위해 유지된다. CPO 결재 경로에서는
        ``record_from_report()`` 가 narrative 변질을 원천 차단한다.

    입력 검증:
        - project / topic / pattern: 비어있지 않고, ``/`` 미포함, 줄바꿈 미포함,
          각 ``HISTORY_FIELD_MAX_LEN`` (80자) 이내 (P76)
        - first_pass_score 는 0..100 범위
        - outcome 는 ``"success" | "aborted"`` (P30 ABORTED 가드)

    ``request_id`` (ADR-0006 + P76): 제공되면 ``HistoryEntry`` 에 박혀 audit
    log 와 cross-check 가능. None 이면 옛 5필드 format 으로 박제.

    Raises:
        ReflectionSkipped: ``outcome=aborted`` 일 때. caller 가 silent 처리해야 한다.
        ValueError: 필드 검증 실패.
    """

    if outcome not in _VALID_OUTCOMES:
        raise ValueError(
            f"outcome must be one of {sorted(_VALID_OUTCOMES)}, got {outcome!r}"
        )
    if outcome == OUTCOME_ABORTED:
        raise ReflectionSkipped(
            f"reflection skipped for worker={worker!r}: outcome=aborted"
        )

    # P76 — CPO 결재 경로에서 본 함수를 호출 시 deprecation 알림 (silent log).
    # /lskun-kit:reflect 정정 경로 (request_id=None) 는 알림 skip.
    if request_id is not None:
        warnings.warn(
            "reflection.record() is deprecated for CPO 결재 경로. "
            "Use record_from_report(report_md=..., request_id=..., outcome=...)",
            DeprecationWarning,
            stacklevel=2,
        )

    project = _validate_field("project", project)
    topic = _validate_field("topic", topic)
    pattern = _validate_field("pattern", pattern)
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
        outcome="approved",
        request_id=(request_id or "")[:32],
    )
    adapter.append_history(worker, entry)
    return entry
