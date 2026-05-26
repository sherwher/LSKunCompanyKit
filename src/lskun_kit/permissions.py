"""``~/.claude/settings.json`` 의 permissions.allow 자동 박제 — ADR-0015 결정 4.

ADR-0015 (2026-05-22) 결정 4-A — Plugin 이 신규 회사를 만들거나 sync target
경로를 사용할 때, 그 경로에 대한 5개 권한 패턴 (Read/Edit/Write/Bash ls/cat)
을 글로벌 settings.json 에 자동 박제.

ADR-0009 정합 — JSON read/write 만 (Python stdlib ``json``). 외부 SDK 0건.

ADR-0015 결정 4-C — 사용자 confirm 1회 강제. 거부 시 권한 자동 박제 skip +
수동 안내. ``ConfirmRequired`` 패턴 (ADR-0015 결정 3-A 옵션 B) 으로 plugin
core 는 stdin 안 잡음.

ADR-0015 결정 5-D — sync target 박제는 incremental. 새 target 마다 본 모듈을
호출하여 settings.json 갱신.

박제 패턴 (회사 root ``co_root`` 의 expanduser 절대경로 기준):
    Read(<co_root>/**)
    Edit(<co_root>/**)
    Write(<co_root>/**)
    Bash(ls <co_root>*)
    Bash(cat <co_root>/**)

멱등성:
    - 이미 박제된 패턴은 skip
    - 일부만 박제된 상태에서 호출하면 누락분만 추가
    - 모두 박제된 상태에서 호출하면 PermissionsResult.action = "unchanged"
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from lskun_kit.errors import ConfirmRequired

#: Claude Code 의 글로벌 settings.json 경로 (홈 기준).
GLOBAL_SETTINGS_PATH_NAME = ".claude/settings.json"


@dataclass
class PermissionsResult:
    """``ensure_for_path()`` 결과 — caller (init / sync) 가 진단에 사용."""

    settings_path: Path
    action: str  # "added" | "unchanged" | "skipped_by_user" | "created"
    added_patterns: list[str] = field(default_factory=list)
    already_present: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def global_settings_path() -> Path:
    """``~/.claude/settings.json`` 절대경로."""

    return Path.home() / GLOBAL_SETTINGS_PATH_NAME


def patterns_for_path(co_root: Path | str) -> list[str]:
    """주어진 회사 root 에 대해 박제할 5개 권한 패턴 목록.

    Tilde expansion: ``co_root`` 가 ``~`` 로 시작하면 expand 한 절대경로를
    settings.json 에 박제 (ADR-0015 결정 4-A 의 "절대경로로 변환" 박제).

    Returns:
        ``Read(...)`` / ``Edit(...)`` / ``Write(...)`` / ``Bash(ls ...)`` /
        ``Bash(cat ...)`` 의 5개 패턴 문자열 리스트. 호출 시점에 평가되며
        order 보장.
    """

    abs_root = str(Path(co_root).expanduser().resolve())
    return [
        f"Read({abs_root}/**)",
        f"Edit({abs_root}/**)",
        f"Write({abs_root}/**)",
        f"Bash(ls {abs_root}*)",
        f"Bash(cat {abs_root}/**)",
    ]


def render_confirm_prompt(patterns: list[str]) -> str:
    """ADR-0015 결정 4-C 의 사용자 confirm 메시지 1줄.

    caller (slash command 의 LLM) 가 이 문자열을 사용자에게 그대로 보여주고
    y/N 입력을 받는다.
    """

    lines = ["다음 권한 패턴을 ~/.claude/settings.json 에 추가합니다:"]
    for p in patterns:
        lines.append(f"  {p}")
    lines.append("")
    lines.append("진행하시겠습니까? [y/N]")
    return "\n".join(lines)


def ensure_for_path(
    co_root: Path | str,
    *,
    confirmed: bool = False,
    settings_path: Path | None = None,
) -> PermissionsResult:
    """``co_root`` 에 대한 5개 권한 패턴을 settings.json 에 박제 (멱등).

    Args:
        co_root: 권한 박제 대상 경로 (회사 root 또는 sync target).
        confirmed: 사용자 confirm 완료 신호. 누락된 패턴이 있고 ``False`` 면
            ``ConfirmRequired`` raise. 이미 모두 박제됐다면 confirm 불필요.
        settings_path: ``~/.claude/settings.json`` 경로 override (테스트용).

    Returns:
        ``PermissionsResult`` —
            - action="unchanged": 모든 패턴이 이미 박제됨 (멱등 no-op)
            - action="created": settings.json 자체가 신규 생성됨 + 패턴 박제
            - action="added": 일부 패턴만 추가됨
            - action="skipped_by_user": 본 함수가 ``confirmed=False`` 인 상태
              에서 reachable 하지 않음. ``ConfirmRequired`` 가 먼저 raise 됨

    Raises:
        ConfirmRequired: 추가할 패턴이 있는데 ``confirmed=False`` 일 때.
            ``kind="permissions"``, ``prompt=render_confirm_prompt(...)``,
            ``context={"settings_path": ..., "patterns": [...]}``.
    """

    path = settings_path if settings_path is not None else global_settings_path()
    desired = patterns_for_path(co_root)
    notes: list[str] = []

    # settings.json read (없으면 빈 dict)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                # corrupted — 덮어쓰지 않고 에러
                raise ValueError(
                    f"~/.claude/settings.json is not a JSON object: "
                    f"got {type(data).__name__}"
                )
        except json.JSONDecodeError as e:
            raise ValueError(
                f"~/.claude/settings.json parse failed: {e}. "
                f"수동 검토 후 재시도하라 (자동 수정 금지)."
            )
        created = False
    else:
        data = {}
        created = True

    perms = data.setdefault("permissions", {})
    if not isinstance(perms, dict):
        raise ValueError(
            f"~/.claude/settings.json의 'permissions' 가 object 아님: "
            f"got {type(perms).__name__}"
        )
    allow = perms.setdefault("allow", [])
    if not isinstance(allow, list):
        raise ValueError(
            f"~/.claude/settings.json의 'permissions.allow' 가 list 아님: "
            f"got {type(allow).__name__}"
        )

    existing = set(allow)
    missing = [p for p in desired if p not in existing]
    already = [p for p in desired if p in existing]

    if not missing:
        return PermissionsResult(
            settings_path=path,
            action="unchanged",
            added_patterns=[],
            already_present=already,
            notes=["모든 권한 패턴이 이미 박제됨 (멱등 no-op)"],
        )

    if not confirmed:
        raise ConfirmRequired(
            kind="permissions",
            prompt=render_confirm_prompt(missing),
            context={
                "settings_path": str(path),
                "patterns": missing,
                "co_root": str(co_root),
            },
        )

    # confirmed=True — 누락분 append (기존 항목 보존, order 유지)
    for p in missing:
        allow.append(p)

    # settings.json write (atomic-ish — 같은 디렉토리에 .tmp 후 rename)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".lskun-tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)

    if created:
        notes.append("~/.claude/settings.json 신규 생성")

    return PermissionsResult(
        settings_path=path,
        action="created" if created else "added",
        added_patterns=missing,
        already_present=already,
        notes=notes,
    )


__all__ = [
    "GLOBAL_SETTINGS_PATH_NAME",
    "PermissionsResult",
    "global_settings_path",
    "patterns_for_path",
    "render_confirm_prompt",
    "ensure_for_path",
]
