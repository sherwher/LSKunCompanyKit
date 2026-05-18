"""세션-범위 상태 — "지금 누가 일하고 있는가" 를 한 곳에서 답한다.

Claude Code 의 slash command 와 Stop hook 은 별도 프로세스에서 실행되므로,
"현재 활성 워커" 를 디스크 한 줄로 공유한다. 이 파일은 의도적으로 단순하다:

- 위치: ``<root>/.lskun-session.json`` (root 는 사용자 SSOT root)
- 내용: ``{"active_worker": "<name>", "started_at": "<ISO>"}``
- 생명주기: ``/lskun-kit:work`` 가 시작, Stop hook 의 Reflection 직후 정리

P38 — Stale 세션 가드:
    Stop hook 이 비정상 종료 (사용자가 강제 종료, hook crash 등) 시 세션 파일이
    잔존하면 PreToolUse hook 이 메인 세션 = CPO 의 정당한 Task dispatch 까지
    차단한다. ``read()`` 가 TTL (default 24h) 초과 세션을 stale 로 보고 None
    반환 + 파일 삭제해 자동 복구한다.

이 모듈은 :class:`StorageAdapter` 가 아니라 file 단위로 동작한다 — 워커 데이터가
아니라 휘발성 세션 상태이기 때문. 사용자 SSOT 의 일부지만 git 추적 대상이 아님.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from pathlib import Path

SESSION_FILENAME = ".lskun-session.json"

#: P38 — 세션이 본 시간 이상 살아있으면 stale 로 간주, read() 가 None 반환 + 정리.
#: 24시간 — 정상 작업은 하루 안에 끝나며, hook crash / 강제 종료가 누적되어 PreToolUse
#: 가 CPO 의 dispatch 까지 차단하는 사고를 막는다.
STALE_SESSION_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class Session:
    active_worker: str
    started_at: datetime


def session_path(root: Path | str) -> Path:
    return Path(root).expanduser() / SESSION_FILENAME


def start(root: Path | str, worker: str) -> Session:
    """워커 호출 시작 — 세션 파일을 새로 쓴다."""

    started = datetime.now(timezone.utc)
    payload = {"active_worker": worker, "started_at": started.isoformat()}
    path = session_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return Session(active_worker=worker, started_at=started)


def read(
    root: Path | str,
    now: datetime | None = None,
    stale_seconds: int = STALE_SESSION_SECONDS,
) -> Session | None:
    """세션 파일을 읽어 :class:`Session` 반환. 없거나 손상되면 ``None``.

    P38 — ``stale_seconds`` 초과 시 stale 세션으로 간주, 파일 자동 삭제 + ``None``
    반환. ``now`` 는 테스트 주입용.
    """

    path = session_path(root)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    worker = data.get("active_worker")
    started = data.get("started_at")
    if not worker or not started:
        return None
    try:
        started_at = datetime.fromisoformat(started)
    except ValueError:
        return None

    now = now or datetime.now(timezone.utc)
    # naive datetime 안전 처리 — UTC 로 간주.
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    if (now - started_at) > timedelta(seconds=stale_seconds):
        # P38 — stale 세션 자동 정리. 다음 dispatch 가 막히지 않도록.
        try:
            path.unlink()
        except OSError:
            pass
        return None

    return Session(active_worker=worker, started_at=started_at)


def clear(root: Path | str) -> None:
    path = session_path(root)
    if path.exists():
        path.unlink()
