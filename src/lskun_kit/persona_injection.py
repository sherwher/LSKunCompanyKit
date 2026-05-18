"""CPO persona 를 사용자 프로젝트 root 의 ``CLAUDE.md`` 에 inline 박제.

ADR-0004 §1 — 메인 Claude Code 세션 자체를 CPO persona 로 운영하기 위한 메커니즘.
SessionStart hook 의 ``additionalContext`` 는 참고 정보로만 취급되어 behavior 강제력이
부족하므로, ``CLAUDE.md`` hot-load (Claude Code 가 매 세션 자동 read) 가 가장 강한
persona 주입 경로다.

구현 원칙:
    - **marker 구간만 plugin 이 관리.** 사용자가 작성한 CLAUDE.md 본문은 한 줄도 건드리지 않는다.
    - **멱등.** 같은 인자로 여러 번 호출해도 marker 구간만 갱신.
    - **CLAUDE.md 가 없으면 새로 생성.** 단, marker 외 본문은 빈 채로.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

CLAUDE_MD_FILENAME = "CLAUDE.md"

#: ADR-0004 §1 — plugin 관리 구간 marker. 본 marker 사이는 사용자 수정 금지.
PERSONA_MARKER_START = "<!-- LSKUN-CPO:START - DO NOT EDIT INSIDE. Managed by LSKunCompanyKit -->"
PERSONA_MARKER_END = "<!-- LSKUN-CPO:END -->"


@dataclass(frozen=True)
class InjectionResult:
    """``inject()`` 의 결과 — caller (init / doctor) 가 진단에 사용."""

    claude_md_path: Path
    action: str  # "created" | "updated" | "unchanged"
    had_existing_marker: bool


def render_persona_block(
    company_name: str,
    cpo_display_name: str,
    cpo_body: str,
) -> str:
    """marker 사이에 들어갈 persona 본문 생성.

    Args:
        company_name: 회사 이름 (헤더에 노출)
        cpo_display_name: CPO 의 ``display_name`` (예: "이세근")
        cpo_body: ``hired/cpo.md`` 의 frontmatter 제외 본문

    Returns:
        marker 두 줄을 포함한 완성된 블록 (앞뒤에 빈 줄 1개씩 포함).
    """

    inner = (
        f"# CPO Persona — {cpo_display_name} of {company_name} "
        f"(auto-injected by LSKunCompanyKit)\n"
        f"\n"
        f"> 본 구간은 `/lskun-kit:init` 또는 `/lskun-kit:doctor --reinject-cpo` 가 관리한다.\n"
        f"> marker 사이는 직접 수정하지 말 것 — 다음 init 시 덮어쓴다.\n"
        f"> ADR-0004 §1 — 메인 Claude Code 세션이 본 persona 로 동작한다.\n"
        f"\n"
        f"{cpo_body.strip()}\n"
    )
    return (
        f"\n{PERSONA_MARKER_START}\n"
        f"{inner}"
        f"{PERSONA_MARKER_END}\n"
    )


def find_marker_span(text: str) -> tuple[int, int] | None:
    """기존 marker 구간의 (start_idx, end_idx_exclusive) 반환. 없으면 ``None``.

    end_idx 는 ``PERSONA_MARKER_END`` 줄 끝 다음 newline 까지 포함.
    """

    start = text.find(PERSONA_MARKER_START)
    if start == -1:
        return None
    end = text.find(PERSONA_MARKER_END, start)
    if end == -1:
        # marker 손상 — start 만 있고 end 없음. caller 가 doctor 에서 경고 처리.
        return None
    end_line_close = text.find("\n", end + len(PERSONA_MARKER_END))
    if end_line_close == -1:
        end_line_close = len(text)
    else:
        end_line_close += 1  # newline 포함
    return start, end_line_close


def inject(
    project_root: Path | str,
    company_name: str,
    cpo_display_name: str,
    cpo_body: str,
) -> InjectionResult:
    """``<project_root>/CLAUDE.md`` 의 marker 구간에 CPO persona 박제.

    - CLAUDE.md 없음 → 신규 생성, persona 블록만 포함
    - 있음 + marker 있음 → 구간만 교체 (사용자 본문 보존)
    - 있음 + marker 없음 → 파일 끝에 persona 블록 append

    Returns:
        InjectionResult — action ∈ {"created", "updated", "unchanged"}.
    """

    root = Path(project_root).expanduser()
    path = root / CLAUDE_MD_FILENAME
    new_block = render_persona_block(company_name, cpo_display_name, cpo_body)

    # project_root 자체가 없으면 박제 skip — caller 가 notes 로 안내.
    if not root.exists():
        return InjectionResult(
            claude_md_path=path, action="skipped-no-project-root",
            had_existing_marker=False,
        )

    if not path.exists():
        path.write_text(new_block.lstrip(), encoding="utf-8")
        return InjectionResult(
            claude_md_path=path, action="created", had_existing_marker=False
        )

    current = path.read_text(encoding="utf-8")
    span = find_marker_span(current)
    if span is None:
        # marker 부재 → 파일 끝에 append (trailing newline 확보 후)
        suffix = "" if current.endswith("\n") else "\n"
        new_text = f"{current}{suffix}{new_block}"
        if new_text == current:
            return InjectionResult(
                claude_md_path=path, action="unchanged", had_existing_marker=False
            )
        path.write_text(new_text, encoding="utf-8")
        return InjectionResult(
            claude_md_path=path, action="updated", had_existing_marker=False
        )

    start, end = span
    # marker 구간을 신규 블록으로 교체. 앞 leading "\n" 은 기존 위치 보존을 위해 조정.
    replacement = new_block.lstrip("\n")
    new_text = current[:start] + replacement + current[end:]
    if new_text == current:
        return InjectionResult(
            claude_md_path=path, action="unchanged", had_existing_marker=True
        )
    path.write_text(new_text, encoding="utf-8")
    return InjectionResult(
        claude_md_path=path, action="updated", had_existing_marker=True
    )


def detect(project_root: Path | str) -> bool:
    """``<project_root>/CLAUDE.md`` 안에 정상 marker 구간이 존재하는지."""

    path = Path(project_root).expanduser() / CLAUDE_MD_FILENAME
    if not path.exists():
        return False
    return find_marker_span(path.read_text(encoding="utf-8")) is not None


__all__ = [
    "CLAUDE_MD_FILENAME",
    "PERSONA_MARKER_START",
    "PERSONA_MARKER_END",
    "InjectionResult",
    "render_persona_block",
    "find_marker_span",
    "inject",
    "detect",
]
