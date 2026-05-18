"""CPO 라우팅 컨텍스트 빌더 — ``/lskun-kit:work`` 의 워커 이름 생략 경로.

ADR-0002 §1 (Q1=ii) — 사용자가 워커 이름 없이 ``/lskun-kit:work "<요청>"`` 을
호출하면 CPO 가 1차 수신자가 된다. 본 모듈은 CPO 에게 주입할 컨텍스트
(현재 hired 워커 목록 + CPO 자기 history) 를 만든다.

핵심 정책:
    - CPO 가 인사팀장을 chain 호출하지 않는다 (ADR-0002 §1 금지).
    - CPO 의 응답은 사용자가 다음 명령을 실행하도록 "다음 명령" 을 항상 포함.
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
    recent_history: int = 10,
) -> str:
    """CPO 가 라우팅 결정을 내릴 수 있는 컨텍스트 문자열을 만든다.

    구조:
        1. CPO 본인 frontmatter + history (다음 라우팅 정확도용)
        2. 현재 hired 워커 목록 (CPO/HR 제외 — CPO 가 본인을 추천하면 무한 루프)
        3. 사용자 요청 원문
        4. 응답 형식 (추천 워커 / 적합 없음 두 양식)
    """

    try:
        cpo_context = build_worker_context(adapter, CPO_WORKER_NAME, recent=recent_history)
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
                parts.append(f"- {name} ({worker.role})")
            except Exception:
                parts.append(f"- {name} (role unknown)")
    else:
        parts.append("_(현재 라우팅 후보 워커 없음 — 인사팀장에게 채용 권장 안내 필요)_")

    parts.extend(
        [
            "",
            "## User Request",
            user_request.strip() or "_(empty)_",
            "",
            "## 응답 형식",
            "적합 워커가 있을 때:",
            "```",
            "추천 워커: <worker> (<role>)",
            "근거: <한 줄>",
            "다음 명령: /lskun-kit:work <worker> \"<요청 그대로>\"",
            "```",
            "",
            "적합 워커가 없을 때 (CPO 는 인사팀장을 직접 호출하지 않는다):",
            "```",
            "추천 워커: 없음",
            "사유: <한 줄>",
            "권장 조치: /lskun-kit:work hr-lead \"신규 채용 요청 — role=<role>, 사유=<...>\"",
            "```",
        ]
    )
    return "\n".join(parts) + "\n"


__all__ = [
    "CPO_WORKER_NAME",
    "HR_LEAD_WORKER_NAME",
    "RoutingDecision",
    "decide_target",
    "build_cpo_routing_context",
]
