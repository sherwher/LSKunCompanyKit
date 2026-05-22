"""CPO 라우팅 컨텍스트 빌더 — ``/lskun-kit:work`` 의 워커 이름 생략 경로.

사용자가 워커 이름 없이 ``/lskun-kit:work "<요청>"`` 을 호출하면 CPO 가 1차
수신자가 된다. 본 모듈은 CPO 에게 주입할 컨텍스트 (현재 hired 워커 목록 +
CPO 본인 메타) 를 만든다.

핵심 정책:
    - CPO 는 적합 워커 부재 시 HR Lead 를 Task tool 로 호출해 **자동 채용** 한다.
    - 자동 채용은 사용자 알림 1줄만 emit, 차단 없음. 신규 워커 dispatch 까지
      CPO 가 한 흐름으로 처리.
    - 워커 → 워커 chain 은 여전히 금지 (PreToolUse hook 이 차단).

ADR-0014 (2026-05-22) — Reflection 메커니즘 폐기. 워커 history tie-break 제거.
라우팅 신호는 JD (persona body) + keywords + role × domain. 워커는 채용 시
완성형이며 시간 흐름으로 진화하지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass

from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.context import build_worker_context
from lskun_kit.errors import WorkerNotFoundError

CPO_WORKER_NAME = "cpo"
HR_LEAD_WORKER_NAME = "hr-lead"


@dataclass(frozen=True)
class RoutingDecision:
    """``decide_target()`` 의 분기 결과 — slash command 가 이것으로 동작 분기."""

    mode: str  # "direct" | "cpo" | "missing-cpo"
    target_worker: str | None = None  # direct 일 때만 채워짐
    reason: str = ""


def decide_target(
    adapter: StorageAdapter,
    requested_worker: str | None,
) -> RoutingDecision:
    """워커 이름 입력 유무로 직통 / CPO / 에러 분기 결정.

    - ``requested_worker`` 가 비어 있지 않으면 → direct (CPO 경유 안 함)
    - 비어 있으면 → CPO 라우팅 시도
      - CPO 가 hired 되어 있지 않으면 → ``missing-cpo`` (사용자에게 init 안내)
    """

    name = (requested_worker or "").strip()
    if name:
        return RoutingDecision(mode="direct", target_worker=name)

    workers = set(adapter.list_workers())
    if CPO_WORKER_NAME not in workers:
        return RoutingDecision(
            mode="missing-cpo",
            reason=(
                f"워커 이름이 생략됐는데 '{CPO_WORKER_NAME}' 가 hired 되어 있지 않다. "
                f"`/lskun-kit:init` 을 먼저 실행해 CPO/HR 를 셋업하라."
            ),
        )
    return RoutingDecision(mode="cpo", target_worker=CPO_WORKER_NAME)


def build_cpo_routing_context(
    adapter: StorageAdapter,
    user_request: str,
    recent_history: int = 0,  # ADR-0014 이전 호환을 위해 인자 유지. 값 무시.
) -> str:
    """CPO 가 라우팅 결정을 내릴 수 있는 컨텍스트 문자열을 만든다.

    구조:
        1. CPO 본인 메타 (이름 / role / hired_at)
        2. 현재 hired 워커 목록 (CPO/HR 제외 — CPO 가 본인을 추천하면 무한 루프)
        3. 사용자 요청 원문
        4. 응답 형식 (추천 워커 / 적합 없음 두 양식)
    """

    try:
        cpo_context = build_worker_context(adapter, CPO_WORKER_NAME)
    except WorkerNotFoundError as e:
        raise WorkerNotFoundError(
            f"CPO ('{CPO_WORKER_NAME}') 가 hired 되어 있지 않다. "
            f"`/lskun-kit:init` 을 먼저 실행하라."
        ) from e

    all_workers = adapter.list_workers()
    candidate_workers = [
        w for w in all_workers if w not in (CPO_WORKER_NAME, HR_LEAD_WORKER_NAME)
    ]

    parts = [cpo_context.rstrip(), ""]
    parts.append("## Hired Workers (라우팅 후보)")
    if candidate_workers:
        for name in candidate_workers:
            try:
                worker = adapter.read_worker(name)
                parts.append(_format_worker_line(name, worker))
            except Exception:
                parts.append(f"- {name} (role unknown)")
    else:
        parts.append(
            "_(현재 라우팅 후보 워커 없음 — HR Lead 를 Task tool 로 호출해 "
            "자동 채용 진행.)_"
        )

    # P69 — user_request 를 fence 로 감싸 markdown injection 차단.
    safe_request = (user_request.strip() or "_(empty)_").replace("```", "ˋˋˋ")
    parts.extend(
        [
            "",
            "## User Request",
            "```user-request",
            safe_request,
            "```",
            "",
            "## 응답 형식",
            "적합 워커가 있을 때 — Task tool 로 dispatch:",
            "```",
            "추천 워커: <worker> (<role>, domain=<domain>, model=<sonnet|opus>)",
            "근거: <한 줄>",
            "행동: Task tool 호출 → 워커 컨텍스트 + 사용자 요청 주입",
            "```",
            "",
            "적합 워커가 없을 때 — HR Lead 를 Task tool 로 호출해 자동 채용:",
            "```",
            "사유: 적합 워커 부재 (역할=<role>, 도메인=<domain>)",
            "행동:",
            "  1. Task tool 로 hr-lead 호출 → 채용 요청 (role, domain, 한 줄 사유)",
            "  2. HR Lead 가 hire_audit.record_hire(actor='hr-lead', ...) 통과 시 신규 워커 박제",
            "  3. 사용자 알림 1줄: [채용 알림] <display_name> (<role>, domain=<domain>, model=<model>) — <사유>",
            "  4. 신규 워커를 Task tool 로 즉시 dispatch → 결재 → 사용자 응답",
            "```",
            "",
            "주의: 워커 → 워커 chain 은 금지. 워커는 CPO 에게만 보고하고",
            "다른 워커를 직접 호출하지 않는다. PreToolUse hook 이 차단한다.",
            "",
            "라우팅 hint (ADR-0014 — JD-driven, history tie-break 폐기):",
            "  1. 각 후보의 ``keywords:`` 와 사용자 요청의 의미를 매칭",
            "  2. ``domain=`` 일치 (회사 도메인 vs 후보 도메인) 가 동률 tie-break 1순위",
            "  3. role 매칭이 동률 tie-break 2순위",
            "  4. 그래도 동률이면 사용자에게 1줄로 후보 2~3명 제시하고 선택 요청",
            "  주의: keywords 는 워커 자기 신고이므로 과대광고 가능. 의심 시 JD 본문 확인.",
        ]
    )
    return "\n".join(parts) + "\n"


def _format_worker_line(name: str, worker) -> str:
    """라우팅 후보 1줄 포맷. CPO 가 적합 워커를 고를 때 참조하는 메타데이터.

    ADR-0014 — history 요약 제거. keywords (있을 때만) 와 JD 메타만 노출.
    """

    line = f"- {name} ({worker.role}, domain={worker.domain}"
    if worker.model:
        line += f", model={worker.model}"
    line += ")"
    if worker.keywords:
        safe_kw = worker.keywords.replace("`", "'")
        line += f" — keywords: {safe_kw}"
    return line


__all__ = [
    "CPO_WORKER_NAME",
    "HR_LEAD_WORKER_NAME",
    "RoutingDecision",
    "decide_target",
    "build_cpo_routing_context",
]
