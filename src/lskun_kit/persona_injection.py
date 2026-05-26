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

import re
from dataclasses import dataclass
from pathlib import Path

CLAUDE_MD_FILENAME = "CLAUDE.md"
BACKUP_SUFFIX = ".lskun.bak"

#: ADR-0004 §1 — plugin 관리 구간 marker. 본 marker 사이는 사용자 수정 금지.
PERSONA_MARKER_START = "<!-- LSKUN-CPO:START - DO NOT EDIT INSIDE. Managed by LSKunCompanyKit -->"
PERSONA_MARKER_END = "<!-- LSKUN-CPO:END -->"


@dataclass(frozen=True)
class InjectionResult:
    """``inject()`` 의 결과 — caller (init / doctor) 가 진단에 사용."""

    claude_md_path: Path
    action: str  # "created" | "updated" | "unchanged"
    had_existing_marker: bool
    backup_path: Path | None = None  # P34 — 사용자 손편집 감지 시 백업 경로


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

    P42 (#19) — marker 가 **줄의 첫 글자에서 시작** 하는 경우에만 인식한다.
    사용자가 markdown 코드 블록 (``` ... ```) 안에 marker 텍스트를 예시로
    적어 놓아도 실제 marker 로 오인하지 않는다. 줄 시작 매칭 + 펜스 깊이
    추적으로 fenced block 내부의 marker 도 제외.

    end_idx 는 ``PERSONA_MARKER_END`` 줄 끝 다음 newline 까지 포함.
    """

    start = _find_line_start_marker(text, PERSONA_MARKER_START)
    if start == -1:
        return None
    # start 이후에서 END marker 도 줄 시작에서 찾는다.
    end = _find_line_start_marker(text, PERSONA_MARKER_END, search_from=start)
    if end == -1:
        return None
    end_line_close = text.find("\n", end + len(PERSONA_MARKER_END))
    if end_line_close == -1:
        end_line_close = len(text)
    else:
        end_line_close += 1
    return start, end_line_close


def _find_line_start_marker(text: str, marker: str, search_from: int = 0) -> int:
    """marker 가 줄의 첫 글자에서 시작하면서 fenced code block 밖에 있는 위치 반환.

    못 찾으면 ``-1``. fenced block 은 ``` 또는 ~~~ 라인 페어로 추적.
    """

    in_fence = False
    fence_char = ""
    pos = 0  # 줄 시작 인덱스
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        # fenced code block 감지 (``` 또는 ~~~ 로 시작하는 줄)
        if stripped.startswith("```") or stripped.startswith("~~~"):
            this_char = stripped[0]
            if not in_fence:
                in_fence = True
                fence_char = this_char
            elif fence_char == this_char:
                in_fence = False
                fence_char = ""
        elif not in_fence and pos >= search_from and line.startswith(marker):
            return pos
        pos += len(line)
    return -1


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

    # P34 — 사용자가 marker 구간을 손편집했는지 감지: 기존 구간의 body 가 cpo.md
    # body 의 정규화 텍스트를 포함하지 않으면 손편집 가능성으로 보고 백업한다.
    backup_path: Path | None = None
    existing_block = current[start:end]
    if not _block_contains_cpo_body(existing_block, cpo_body):
        backup_path = path.with_suffix(path.suffix + BACKUP_SUFFIX)
        backup_path.write_text(current, encoding="utf-8")

    path.write_text(new_text, encoding="utf-8")
    return InjectionResult(
        claude_md_path=path, action="updated", had_existing_marker=True,
        backup_path=backup_path,
    )


def _block_contains_cpo_body(block: str, cpo_body: str) -> bool:
    """marker 구간 본문이 현재 cpo.md body 를 (헤더·trailing whitespace 제외) 포함하는지.

    P42 (#10) — fenced code block (``` ... ```) 안의 indentation 은 strip 하지
    않는다. 코드 블록 indent 가 의미를 가지는 cpo.md (예: Python 예제) 가 단순
    strip 으로 깨져 false-negative (정상 재박제를 손편집으로 오감지) 가 나는
    것을 방지. 보수적 가드 — 일치하면 손편집 아님, 일치 안 하면 손편집 가능성.
    """

    def normalize(text: str) -> str:
        out: list[str] = []
        in_fence = False
        fence_char = ""
        for ln in text.splitlines():
            stripped = ln.lstrip()
            is_fence_line = (
                stripped.startswith("```") or stripped.startswith("~~~")
            )
            if is_fence_line:
                this_char = stripped[0]
                if not in_fence:
                    in_fence = True
                    fence_char = this_char
                elif fence_char == this_char:
                    in_fence = False
                    fence_char = ""
                out.append(ln.rstrip())  # fence 라인 자체는 trailing 만 제거
                continue
            if in_fence:
                out.append(ln.rstrip())  # 코드 블록 내부 — leading whitespace 보존
            else:
                s = ln.strip()
                if s:
                    out.append(s)
        return "\n".join(out)

    body = normalize(cpo_body)
    if not body:
        return True
    return body in normalize(block)


def detect(project_root: Path | str) -> bool:
    """``<project_root>/CLAUDE.md`` 안에 정상 marker 구간이 존재하는지."""

    path = Path(project_root).expanduser() / CLAUDE_MD_FILENAME
    if not path.exists():
        return False
    return find_marker_span(path.read_text(encoding="utf-8")) is not None


#: marker 본문 첫 줄에서 회사 이름을 추출하는 패턴.
#: ``render_persona_block`` 이 박는 ``# CPO Persona — {display} of {company} (auto-injected by ...)``
#: 형식과 정합. ``of`` 뒤부터 ``(auto-injected`` 직전까지가 회사 이름.
_MARKER_COMPANY_PAT = re.compile(
    r"^#\s*CPO Persona\s*—\s*.+?\s+of\s+(.+?)\s+\(auto-injected\s+by\s+",
    re.MULTILINE,
)


def extract_company_name(project_root: Path | str) -> str | None:
    """``<project_root>/CLAUDE.md`` 의 marker 구간에서 회사 이름 추출.

    ADR-0015 결정 2-B — ``/init <name>`` 멱등성 분기에서 marker 의 회사 이름과
    인자의 회사 이름을 cross-check 하여 same / different 를 판정.

    Returns:
        회사 이름 (str) 또는 ``None`` (CLAUDE.md 부재 / marker 부재 / parse 실패).
    """

    path = Path(project_root).expanduser() / CLAUDE_MD_FILENAME
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    span = find_marker_span(text)
    if span is None:
        return None
    start, end = span
    block = text[start:end]
    m = _MARKER_COMPANY_PAT.search(block)
    if m is None:
        return None
    return m.group(1).strip()


__all__ = [
    "CLAUDE_MD_FILENAME",
    "BACKUP_SUFFIX",
    "PERSONA_MARKER_START",
    "PERSONA_MARKER_END",
    "InjectionResult",
    "render_persona_block",
    "find_marker_span",
    "inject",
    "detect",
    "extract_company_name",
]
