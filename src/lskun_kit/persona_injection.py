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
#: ADR-0029 D2 — 포인터가 사는 곳. Claude Code 공식 용도 = 버전 관리에 올리지 않는 개인용 지침.
CLAUDE_LOCAL_MD_FILENAME = "CLAUDE.local.md"
BACKUP_SUFFIX = ".lskun.bak"

#: ADR-0029 D7 — marker 탐색 순서. local 이 우선.
MARKER_FILENAMES = (CLAUDE_LOCAL_MD_FILENAME, CLAUDE_MD_FILENAME)

#: ADR-0029 D4 — persona 본문 (templates/cpo.md) 끝의 로드 표식.
PERSONA_LOADED_SENTINEL = "LSKUN-PERSONA-LOADED"

MODE_POINTER = "pointer"
MODE_INLINE = "inline"

#: ADR-0004 §1 — plugin 관리 구간 marker. 본 marker 사이는 사용자 수정 금지.
PERSONA_MARKER_START = "<!-- LSKUN-CPO:START - DO NOT EDIT INSIDE. Managed by LSKunCompanyKit -->"
PERSONA_MARKER_END = "<!-- LSKUN-CPO:END -->"
#: 구간 **인식**용 접두. 실사용에서 손으로 쓰인 변형 (``<!-- LSKUN-CPO:START -->``,
#: ``<!-- LSKUN-CPO:START company=X -->``) 이 발견됐다 (ADR-0029 실측). 인식은 접두로
#: 넓히고, plugin 이 **쓰는** marker 는 항상 표준형 ``PERSONA_MARKER_START`` 다.
PERSONA_MARKER_START_PREFIX = "<!-- LSKUN-CPO:START"


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
        f"> 본 구간은 `/lskun-kit:init` · `/lskun-kit:migrate-schema` · `/lskun-kit:sync-persona --execute` 가 관리한다.\n"
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


@dataclass(frozen=True)
class PointerResult:
    """``inject_pointer()`` 의 결과 (ADR-0029)."""

    local_md_path: Path
    action: str  # "created" | "updated" | "unchanged" | "skipped-no-project-root"
    removed_inline: bool = False  # 추적 CLAUDE.md 에서 inline 구간을 제거했는가
    claude_md_deleted: bool = False  # 구간 제거 후 남는 내용이 없어 파일을 지웠는가
    backup_path: Path | None = None  # inline 제거 전 CLAUDE.md 원본
    git_excluded: bool = False  # .git/info/exclude 에 기록됐는가
    notes: tuple[str, ...] = ()


def pointer_import_line(company_name: str) -> str:
    """CPO persona 본문을 가리키는 import 1줄 (ADR-0029 D1).

    ``~`` 표기를 쓴다 — 홈 경로 (사용자명) 가 파일에 남지 않고 머신 간에 같다.
    """

    from lskun_kit.paths import LSKUN_COMPANIES_DIRNAME, validate_company_name

    validate_company_name(company_name)  # 경로에 들어가는 값 — 조작 문자 차단
    return f"@~/{LSKUN_COMPANIES_DIRNAME}/{company_name}/hired/cpo.md"


def render_pointer_block(company_name: str, cpo_display_name: str) -> str:
    """marker 사이에 들어갈 포인터 블록 (ADR-0029 D1).

    머리말 1줄은 inline 블록과 같은 형식이다 — ``extract_company_name`` 이
    회사명을 이 줄에서 읽는다.
    """

    import_line = pointer_import_line(company_name)
    inner = (
        f"# CPO Persona — {cpo_display_name} of {company_name} "
        f"(auto-injected by LSKunCompanyKit)\n"
        f"\n"
        f"> 포인터 방식 (ADR-0029) — persona 본문은 회사 SSOT 의 한 부를 import 한다.\n"
        f"> 갱신은 회사당 1회 `/lskun-kit:sync-persona --execute`. 이 파일은 다시 건드릴 필요가 없다.\n"
        f"> 처음 열 때 Claude Code 가 외부 import 승인을 묻는다 — 승인해야 persona 가 로드된다.\n"
        f"\n"
        f"{import_line}\n"
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

    start = _find_line_start_marker(text, PERSONA_MARKER_START_PREFIX)
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


def _marker_block(project_root: Path | str) -> tuple[Path, str] | None:
    """marker 구간을 가진 첫 파일과 그 구간 텍스트 (ADR-0029 D7 — local 우선)."""

    root = Path(project_root).expanduser()
    for filename in MARKER_FILENAMES:
        path = root / filename
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        span = find_marker_span(text)
        if span is not None:
            return path, text[span[0]:span[1]]
    return None


def has_marker_file(project_root: Path | str) -> bool:
    """marker 를 담을 수 있는 지침 파일이 하나라도 있는가 (상위 탐색의 빠른 필터)."""

    root = Path(project_root).expanduser()
    return any((root / name).is_file() for name in MARKER_FILENAMES)


def detect(project_root: Path | str) -> bool:
    """프로젝트 지침 파일 (local → CLAUDE.md) 에 정상 marker 구간이 존재하는지."""

    return _marker_block(project_root) is not None


def detect_mode(project_root: Path | str) -> str | None:
    """marker 구간의 방식 — ``"pointer"`` / ``"inline"`` / ``None`` (marker 없음).

    포인터 = 구간 안에 회사 SSOT 를 가리키는 import 줄이 있다. 그 밖은 inline
    (본문 복사, ADR-0004 §1 의 옛 방식 — 머리말 형식이 다른 옛 세대 포함).
    """

    found = _marker_block(project_root)
    if found is None:
        return None
    _, block = found
    for line in block.splitlines():
        if line.startswith("@") and line.rstrip().endswith("/hired/cpo.md"):
            return MODE_POINTER
    return MODE_INLINE


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

    found = _marker_block(project_root)
    if found is None:
        return None
    _, block = found
    m = _MARKER_COMPANY_PAT.search(block)
    if m is None:
        return None
    return m.group(1).strip()


def inject_pointer(
    project_root: Path | str,
    company_name: str,
    cpo_display_name: str,
) -> PointerResult:
    """``CLAUDE.local.md`` 에 포인터 블록을 쓰고, 추적 ``CLAUDE.md`` 의 inline 구간을 걷어낸다.

    ADR-0029 D1·D2·D3·D5. 멱등. 커밋하지 않는다.

    - ``CLAUDE.local.md``: marker 구간만 plugin 이 관리 (사용자 본문 보존)
    - ``CLAUDE.md``: inline 구간이 있으면 제거 (항상 백업). 남는 내용이 없으면 파일 삭제
    - git 저장소면 ``.git/info/exclude`` 에 local 파일과 백업을 기록 (``.gitignore`` 불변)
    """

    new_block = render_pointer_block(company_name, cpo_display_name)  # 회사명 검증 포함
    root = Path(project_root).expanduser()
    local_path = root / CLAUDE_LOCAL_MD_FILENAME
    if not root.exists():
        return PointerResult(local_md_path=local_path, action="skipped-no-project-root")

    # 1. CLAUDE.local.md — marker 구간 교체 또는 append.
    if not local_path.exists():
        local_path.write_text(new_block.lstrip(), encoding="utf-8")
        action = "created"
    else:
        current = local_path.read_text(encoding="utf-8")
        span = find_marker_span(current)
        if span is None:
            suffix = "" if current.endswith("\n") or not current else "\n"
            new_text = f"{current}{suffix}{new_block}"
        else:
            new_text = current[: span[0]] + new_block.lstrip("\n") + current[span[1]:]
        if new_text == current:
            action = "unchanged"
        else:
            local_path.write_text(new_text, encoding="utf-8")
            action = "updated"

    # 2. 추적 CLAUDE.md 의 inline 구간 제거.
    removed_inline = False
    deleted = False
    backup_path: Path | None = None
    tracked_path = root / CLAUDE_MD_FILENAME
    if tracked_path.is_file():
        tracked = tracked_path.read_text(encoding="utf-8")
        span = find_marker_span(tracked)
        if span is not None:
            backup_path = _unique_backup_path(tracked_path)
            backup_path.write_text(tracked, encoding="utf-8")
            remainder = (tracked[: span[0]].rstrip("\n") + "\n" + tracked[span[1]:].lstrip("\n")).strip("\n")
            if remainder.strip():
                tracked_path.write_text(remainder + "\n", encoding="utf-8")
            else:
                tracked_path.unlink()
                deleted = True
            removed_inline = True
            if action == "unchanged":
                action = "updated"

    # 3. git 제외.
    # 백업은 충돌 시 ``.lskun.bak.1`` 처럼 번호가 붙는다 — 패턴 끝의 ``*`` 가 전부 덮는다.
    excluded, note = _ensure_git_excluded(
        root, (CLAUDE_LOCAL_MD_FILENAME, CLAUDE_MD_FILENAME + BACKUP_SUFFIX + "*")
    )
    return PointerResult(
        local_md_path=local_path,
        action=action,
        removed_inline=removed_inline,
        claude_md_deleted=deleted,
        backup_path=backup_path,
        git_excluded=excluded,
        notes=(note,) if note else (),
    )


def _unique_backup_path(path: Path) -> Path:
    """``<path>.lskun.bak`` — 이미 있으면 ``.1``, ``.2`` … 를 붙인다.

    기존 백업을 **절대 덮어쓰지 않는다.** 앞선 전환 시도나 P34 의 손편집 감지가 남긴
    백업은 사용자 원본의 유일한 사본일 수 있다.
    """

    base = path.with_suffix(path.suffix + BACKUP_SUFFIX)
    if not base.exists():
        return base
    n = 1
    while True:
        candidate = base.with_name(f"{base.name}.{n}")
        if not candidate.exists():
            return candidate
        n += 1


def _ensure_git_excluded(project_root: Path, names: tuple[str, ...]) -> tuple[bool, str]:
    """``<repo>/.git/info/exclude`` 에 ``names`` 를 기록 (ADR-0029 D3).

    추적되는 ``.gitignore`` 를 건드리지 않는다 — 외주·협업 저장소에 diff 가 생기지 않는다.

    **``project_root`` 자신의 ``.git`` 만 대상이다. 상위로 올라가지 않는다.** 상위에는
    프로젝트와 무관한 저장소 (홈의 dotfiles 저장소, 다른 팀의 monorepo) 가 있을 수 있고,
    plugin 이 그 설정을 고쳐서는 안 된다. 프로젝트가 저장소의 하위 디렉토리면 건너뛰고 안내한다.

    Returns:
        (기록 보장 여부, 건너뛴 경우의 안내문).
    """

    git_dir = project_root / ".git"
    if git_dir.is_file():
        return False, (
            ".git 이 파일이다 (worktree / submodule) — exclude 를 기록하지 않았다. "
            f"{', '.join(names)} 를 직접 ignore 하라."
        )
    if not git_dir.is_dir():
        if _inside_some_git_repo(project_root):
            return False, (
                "이 프로젝트는 상위 저장소의 하위 디렉토리다 — 상위 저장소의 설정은 건드리지 않는다. "
                f"{', '.join(names)} 를 직접 ignore 하라 (그 저장소의 .git/info/exclude 권장)."
            )
        return False, ""  # git 저장소 아님 — 할 일 없음

    exclude = git_dir / "info" / "exclude"
    try:
        existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
        present = {ln.strip() for ln in existing.splitlines()}
        missing = [n for n in names if n not in present]
        if missing:
            exclude.parent.mkdir(parents=True, exist_ok=True)
            prefix = "" if existing.endswith("\n") or not existing else "\n"
            header = "# LSKunCompanyKit (ADR-0029) — 개인용 persona 포인터·백업\n"
            exclude.write_text(
                existing + prefix + header + "\n".join(missing) + "\n", encoding="utf-8"
            )
    except OSError as e:
        return False, f".git/info/exclude 기록 실패 ({e}) — {', '.join(names)} 를 직접 ignore 하라."
    return True, ""


def _inside_some_git_repo(path: Path) -> bool:
    """상위 어딘가에 ``.git`` 이 있는가 — 안내문 분기용. **읽기만 한다.**"""

    cur = path.resolve()
    while cur.parent != cur:
        cur = cur.parent
        if (cur / ".git").exists():
            return True
    return False


__all__ = [
    "CLAUDE_LOCAL_MD_FILENAME",
    "MARKER_FILENAMES",
    "PERSONA_LOADED_SENTINEL",
    "MODE_POINTER",
    "MODE_INLINE",
    "PointerResult",
    "pointer_import_line",
    "render_pointer_block",
    "inject_pointer",
    "detect_mode",
    "has_marker_file",
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
