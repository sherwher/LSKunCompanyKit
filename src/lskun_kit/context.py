"""워커 컨텍스트 빌더 (ADR-0014, 2026-05-22).

ADR-0001 §3 의 Reflection 메커니즘 폐기 (ADR-0014). 워커는 채용 시점에 JD
(persona body) 로 완성형이며, history 누적은 워커 state 가 아니다. 따라서
워커 dispatch 컨텍스트는 JD only — 옛 ``## Past Patterns`` 섹션 주입 제거.
"""

from __future__ import annotations

from lskun_kit.adapters.base import StorageAdapter


def build_worker_context(
    adapter: StorageAdapter, name: str, recent: int = 0
) -> str:
    """워커 메타 정보 (이름 / role / hired_at) 를 컨텍스트 문자열로 반환.

    Claude Code 가 워커 Task dispatch 시 system prompt 또는 첫 user 메시지
    앞에 prepend. ADR-0014 이후 history 섹션 주입은 제거되었다 — JD 본문이
    persona body 로 별도 주입되므로 본 함수는 메타 정보만 담당.

    Args:
        adapter: storage adapter
        name: 워커 이름
        recent: ADR-0014 이전 호환을 위해 인자 유지. 값은 무시.
    """

    worker = adapter.read_worker(name)
    return (
        f"# Worker: {worker.name} ({worker.role})\n"
        f"Hired: {worker.hired_at.isoformat()} · Backend: {worker.storage_backend}\n"
    )
