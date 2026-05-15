"""세션-범위 상태 — "지금 누가 일하고 있는가" 를 한 곳에서 답한다.

Claude Code 의 slash command 와 Stop hook 은 별도 프로세스에서 실행되므로,
"현재 활성 워커" 를 디스크 한 줄로 공유한다. 이 파일은 의도적으로 단순하다:

- 위치: ``<root>/.lskun-session.json`` (root 는 사용자 SSOT root)
- 내용: ``{"active_worker": "<name>", "started_at": "<ISO>"}``
- 생명주기: ``/lskun-kit:work`` 가 시작, Stop hook 의 Reflection 직후 정리

이 모듈은 :class:`StorageAdapter` 가 아니라 file 단위로 동작한다 — 워커 데이터가
아니라 휘발성 세션 상태이기 때문. 사용자 SSOT 의 일부지만 git 추적 대상이 아님.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path

SESSION_FILENAME = ".lskun-session.json"


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


def read(root: Path | str) -> Session | None:
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
    return Session(active_worker=worker, started_at=datetime.fromisoformat(started))


def clear(root: Path | str) -> None:
    path = session_path(root)
    if path.exists():
        path.unlink()
