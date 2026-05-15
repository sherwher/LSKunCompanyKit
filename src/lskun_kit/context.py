"""워커 컨텍스트 주입 — 워커가 자기 history 를 다음 작업에 인용하게 만든다.

ADR-0001 §3 의 Reflection 메커니즘에서 사용자 마주하는 절반.
다른 절반은 :mod:`lskun_kit.reflection` 의 append.
"""

from __future__ import annotations

from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.adapters._markdown_tree import HISTORY_HEADING

DEFAULT_RECENT_N = 10


def build_worker_context(
    adapter: StorageAdapter, name: str, recent: int = DEFAULT_RECENT_N
) -> str:
    """워커의 history 중 최근 N줄을 컨텍스트 문자열로 반환한다.

    이 문자열은 Claude Code 가 워커를 호출할 때 system prompt 또는
    첫 user 메시지 앞에 prepend 한다. 포맷은 markdown 으로, 사용자가 직접
    읽어도 의미가 통하도록 유지.
    """

    worker = adapter.read_worker(name)
    history_lines = _extract_recent_history(worker.body, recent)

    parts = [
        f"# Worker: {worker.name} ({worker.role})",
        f"Hired: {worker.hired_at.isoformat()} · Backend: {worker.storage_backend}",
        "",
    ]

    if history_lines:
        parts.append(f"## Past Patterns (recent {len(history_lines)})")
        parts.extend(history_lines)
    else:
        parts.append("## Past Patterns")
        parts.append("_(no history yet — this is the worker's first task)_")

    return "\n".join(parts) + "\n"


def _extract_recent_history(body: str, recent: int) -> list[str]:
    """워커 본문에서 ``## Project History`` 섹션의 끝 N줄을 뽑는다."""

    if HISTORY_HEADING not in body:
        return []
    after_heading = body.split(HISTORY_HEADING, 1)[1]
    section: list[str] = []
    for raw in after_heading.splitlines():
        stripped = raw.strip()
        if stripped.startswith("## "):
            break
        if stripped.startswith("- "):
            section.append(stripped)
    if recent <= 0:
        return section
    return section[-recent:]
