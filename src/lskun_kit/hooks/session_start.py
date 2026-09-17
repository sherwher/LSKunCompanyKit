"""SessionStart hook — 활성 회사가 있으면 dynamic context 를 메인 세션에 주입.

ADR-0004 §1 의 2-layer persona 주입 중 layer B (보조):
    - layer A: 사용자 프로젝트 root 의 ``CLAUDE.md`` marker 구간 (정적 persona) — P23
    - **layer B (본 모듈): 매 세션 시작 시 회사/hired 동적 주입** — P24

ADR-0014 (2026-05-22) — Reflection 메커니즘 폐기. CPO history 컨텍스트 주입
제거. 회사 + hired 워커 목록만 동적 주입한다.

ADR-0004 §7 — 활성 회사 없으면 silent no-op (출력 0). 사용자가 LSKunCompanyKit 을
설치만 했고 회사 셋업을 안 했다면 본 hook 은 침묵.

출력 포맷 (stdout):
    Claude Code 의 SessionStart hook 사양에 따라 JSON 1줄 emit:
    {"hookSpecificOutput": {"hookEventName": "SessionStart",
                             "additionalContext": "<markdown 문자열>"}}

입력 (stdin):
    Claude Code 가 hook payload 를 JSON 으로 주입할 수 있으나, 본 hook 은 그것에
    의존하지 않고 환경변수 / 현재 작업 디렉토리만으로 활성 회사를 감지한다.

활성 회사 감지 (ADR-0015 결정 1-A + 결정 2-B):
    1. cwd 부터 상위로 ``CLAUDE.md`` 탐색 (최대 5 depth, git root 경계).
    2. 발견된 ``CLAUDE.md`` 의 LSKUN-CPO marker 구간에서 회사 이름 추출.
    3. ``~/.lskun-companies/<name>/`` 가 존재하면 그 root 의 컨텍스트 emit.
    4. marker 부재 또는 회사 디렉토리 부재 시 silent no-op.

CLAUDE.md marker 가 단일 진실원 — ``LSKUN_VAULT`` env var / cwd ``.company/`` 같은
옛 경로 탐색은 모두 폐기 (결정 1-A).

종료 코드: 항상 0 (hook 실패가 세션을 막으면 안 됨).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# P48 — Claude Code 가 본 hook 을 `python3 <plugin>/src/lskun_kit/hooks/...py` 로
# 직접 경로 호출하면 ``from lskun_kit...`` import 가 깨진다. ``src/`` 를 sys.path 에
# 삽입해 self-bootstrap. ``-m`` 진입점에서는 부작용 없이 idempotent.
_SRC_DIR = str(Path(__file__).resolve().parents[2])
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

# stdlib only — plugin 정책

MAX_PARENT_DEPTH = 5

# P36 — Prompt injection 가드 (Vault 공유 환경의 악성 markdown 차단).
#: HTML comment 패턴 — <!-- system: ... --> 류 hijack 시도 제거.
_HTML_COMMENT_PAT = re.compile(r"<!--.*?-->", re.DOTALL)
#: 한 줄 / 필드 최대 길이 — 비정상적으로 긴 입력 차단.
MAX_LINE_LENGTH = 500
MAX_FIELD_LENGTH = 200


def _sanitize_inline(value: str, max_len: int = MAX_FIELD_LENGTH) -> str:
    """frontmatter value / history line 등 컨텍스트 inject 직전 sanitize.

    - HTML comment 제거 (LSKUN-CPO marker 포함 — 가짜 marker 주입 방지)
    - 줄바꿈 제거 (첫 줄만 취함)
    - ``max_len`` 초과 시 잘라냄
    """

    if not value:
        return value
    s = _HTML_COMMENT_PAT.sub("", value)
    lines = s.splitlines()
    s = lines[0] if lines else s
    if len(s) > max_len:
        s = s[: max_len - 3] + "..."
    return s


SOURCE_COMPACT = "compact"
STDIN_WAIT_SECONDS = 0.5
STDIN_MAX_BYTES = 64 * 1024  # SessionStart payload 는 수백 바이트


def _read_stdin_nonblocking() -> str:
    """stdin payload 를 블로킹 없이 읽는다.

    Claude Code 는 payload 를 쓰고 stdin 을 닫지만, 수동 실행·테스트처럼 EOF 가
    오지 않는 환경에서 ``read()`` 는 영원히 멈춘다. hook 은 세션을 막으면 안 되므로
    읽을 데이터가 준비된 경우에만 읽는다.
    """

    import os
    import select

    stream = sys.stdin
    if stream is None:
        return ""
    try:
        fd = stream.fileno()
    except (AttributeError, OSError, ValueError):
        return stream.read()  # fileno 없는 in-memory stream (테스트 mock)
    if stream.isatty():
        return ""
    if os.name == "nt":
        # Windows 의 select 는 소켓만 지원한다. Claude Code 는 payload 후 stdin 을 닫는다.
        return stream.read()
    ready, _, _ = select.select([fd], [], [], STDIN_WAIT_SECONDS)
    if not ready:
        return ""
    # os.read 는 준비된 만큼만 돌려준다 — 상대가 stdin 을 닫지 않아도 멈추지 않는다.
    return os.read(fd, STDIN_MAX_BYTES).decode("utf-8", errors="replace")


def _read_source() -> str:
    """stdin payload 의 ``source`` (startup / resume / clear / compact). 실패 시 ""."""

    try:
        data = json.loads(_read_stdin_nonblocking() or "{}")
    except Exception:  # noqa: BLE001 — hook 은 절대 세션을 막으면 안 됨
        return ""
    source = data.get("source") if isinstance(data, dict) else ""
    return source if isinstance(source, str) else ""


def main(argv: list[str] | None = None) -> int:
    try:
        context = _build_context(source=_read_source())
    except Exception as e:  # noqa: BLE001 — hook 은 절대 세션을 막으면 안 됨
        # 디버그용 stderr — Claude Code 는 stderr 를 사용자에게 직접 보여줌
        print(f"lskun-kit session_start: error {e!r}", file=sys.stderr)
        return 0

    if not context:
        return 0  # silent no-op

    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


def _build_context(source: str = "") -> str:
    company_root = _find_active_company_root()
    if company_root is None:
        return _orphan_marker_notice()

    company_meta = _read_company_meta(company_root)
    workers = _list_workers_with_meta(company_root)

    # P36 — 모든 외부 입력 (frontmatter) 을 inject 전에 sanitize.
    company_name = _sanitize_inline(company_meta.get("name", "(이름 미박제)"))
    company_domain = _sanitize_inline(company_meta.get("domain", ""))

    lines = [
        "## LSKunCompanyKit — 활성 회사",
        "",
        f"- 회사: **{company_name}**"
        + (f" (domain={company_domain})" if company_domain else ""),
        f"- 회사 root: `{company_root}`",
    ]
    # ADR-0029 D4·D6 — 워커 명단 (수십 줄) 뒤에 두면 묻힌다. 실측: 맨 끝에 뒀을 때 작은
    # 모델이 점검을 놓쳤다. 명단 앞에 둔다.
    lines.extend(_persona_mode_lines(company_name))
    lines.extend(["", "### Hired 워커"])
    if workers:
        for w in workers:
            name = _sanitize_inline(w.get("name", "?"), max_len=80)
            role = _sanitize_inline(w.get("role", "?"), max_len=80)
            domain = _sanitize_inline(w.get("domain", "?"), max_len=80)
            display = _sanitize_inline(
                w.get("display_name", w.get("name", "?")), max_len=80
            )
            model = _sanitize_inline(w.get("model", ""), max_len=80)
            model_part = f", model={model}" if model else ""
            lines.append(
                f"- `{name}` — {display} ({role}, domain={domain}{model_part})"
            )
    else:
        lines.append("_(없음)_")

    lines.extend(
        [
            "",
            "> ADR-0004 §1 — 본 메인 세션은 CPO persona 로 동작.",
            "> CPO 의 책임 / 직접 응답 조건 / Task dispatch 절차 / 결재 / 자동 채용 /"
            " 에스컬레이션 / 금지 사항은 모두 **CLAUDE.md 의 LSKUN-CPO marker 구간 박제**"
            " (cpo.md SSOT) 를 따른다.",
            "> ADR-0014 (2026-05-22) — Reflection 폐기. 본 hook 은 회사·hired"
            " 동적 정보만 주입한다. 행동 지시는 CLAUDE.md 가 단일 SSOT.",
        ]
    )
    if source == SOURCE_COMPACT:
        lines.extend(_compact_recovery_lines(company_root))
    return "\n".join(lines) + "\n"


def _persona_file_has_sentinel(company_root: Path) -> bool:
    """회사 SSOT 의 ``hired/cpo.md`` 에 로드 표식이 있는가. 읽기 실패 시 True (점검 경로 유지)."""

    from lskun_kit.persona_injection import PERSONA_LOADED_SENTINEL

    try:
        return PERSONA_LOADED_SENTINEL in (company_root / "hired" / "cpo.md").read_text(
            encoding="utf-8"
        )
    except OSError:
        return True


def _orphan_marker_notice() -> str:
    """marker 는 있는데 회사를 식별하지 못한 프로젝트용 안내 (ADR-0029 D6).

    옛 세대 inline 구간은 머리말 형식이 달라 회사명 추출이 실패한다. 그런 프로젝트는
    hook · 가드가 전부 비활성인데도 persona 본문만 남아 있다 — 조용히 넘어가지 않는다.
    회사 디렉토리가 없는 경우 (다른 머신 · 협업자) 는 기존대로 silent.
    """

    from lskun_kit.persona_injection import detect, extract_company_name

    cwd = Path.cwd()
    for _ in range(MAX_PARENT_DEPTH + 1):
        if detect(cwd):
            if extract_company_name(cwd):
                return ""  # 회사명은 읽힘 — 회사 디렉토리 부재. 기존 동작 (silent) 유지
            return (
                "## LSKunCompanyKit — 구버전 CPO 구간\n\n"
                "- 이 프로젝트의 지침 파일에 LSKUN-CPO 구간이 있지만 형식이 오래되어 회사를 식별할 수 없다."
                " 그래서 회사 컨텍스트 주입 · dispatch 가드가 모두 꺼져 있다. 첫 응답에서 사용자에게 1줄로 알려라:"
                " \"이 프로젝트의 CPO 구간이 구버전입니다 — `/lskun-kit:init <회사 이름>` 으로 전환하세요.\"\n"
            )
        if (cwd / ".git").exists() or cwd.parent == cwd:
            break
        cwd = cwd.parent
    return ""


def _persona_mode_lines(company_name: str) -> list[str]:
    """ADR-0029 D4·D6 — persona 배포 방식에 따른 안내 (동적 정보 + 조용한 실패 방지).

    - pointer: import 가 승인되지 않았거나 파일이 없으면 persona 가 **조용히** 빠진다.
      본문 끝의 표식이 지침에 보이는지 CPO 스스로 확인하게 한다.
    - inline (옛 방식): 프로젝트마다 복사본이라 stale 해진다. 전환 명령을 알린다.
    """

    from lskun_kit.persona_injection import (
        MODE_INLINE,
        MODE_POINTER,
        PERSONA_LOADED_SENTINEL,
        detect_mode,
    )

    found = _find_marker_project()
    if found is None:
        return []
    mode = detect_mode(found[0])
    if mode == MODE_POINTER and not _persona_file_has_sentinel(found[1]):
        # plugin 은 올라갔는데 회사 persona 가 아직 옛 template — 표식이 없으니 로드 점검을
        # 시키면 항상 오경고가 난다. 결정론적으로 판정해 정확한 조치를 알린다.
        return [
            "",
            "### CPO persona 구버전 (ADR-0029)",
            "",
            "- 회사의 CPO persona 파일 (`hired/cpo.md`) 이 현재 plugin 보다 오래된 template 이다."
            " 첫 응답에서 사용자에게 1줄로 알려라: \"회사 CPO persona 가 구버전입니다 —"
            " `/lskun-kit:sync-persona --execute` 를 실행하세요 (회사당 1회, 모든 프로젝트에 반영).\"",
        ]
    if mode == MODE_POINTER:
        return [
            "",
            "### CPO persona 로드 확인 (ADR-0029)",
            "",
            f"- 이 프로젝트의 CPO persona 는 `CLAUDE.local.md` 의 import 로 로드된다. 네 지침 안에"
            f" `{PERSONA_LOADED_SENTINEL}` 표식이 **보이지 않으면** persona 본문이 로드되지 않은 것이다"
            " — 첫 응답에서 사용자에게 알려라: \"CPO persona 가 로드되지 않았습니다. Claude Code 의 외부"
            " import 승인이 필요합니다 (세션 재시작 시 승인 창) — 또는 `/lskun-kit:doctor` 로 점검하세요.\"",
            "- 표식이 보이면 이 항목은 무시한다 (사용자에게 언급하지 않는다).",
        ]
    if mode == MODE_INLINE:
        return [
            "",
            "### 구버전 inline persona (ADR-0029)",
            "",
            "- 이 프로젝트는 CPO persona 본문을 지침 파일에 복사해 둔 구버전 inline 방식이다. 복사본은 plugin"
            " 업데이트를 따라오지 못한다. 첫 응답에서 사용자에게 1줄로 알려라:"
            f" \"이 프로젝트의 CPO persona 는 구버전 방식입니다 — `/lskun-kit:init {company_name}` 로"
            " 포인터 방식으로 전환하세요 (마지막 1회).\"",
        ]
    return []


def _compact_recovery_lines(company_root: Path) -> list[str]:
    """P131 — 컨텍스트 압축 직후에만 덧붙는 복구용 동적 정보.

    압축은 빙의 중이던 워커 JD 본문과 진행 중 결재 맥락을 요약으로 뭉갠다.
    행동 규칙을 새로 만들지 않는다 — 현재 상태와, 원문이 어디 있는지만 알린다.
    """

    from lskun_kit import session  # 지연 import — hooks 의존성 격리

    sess = session.read(company_root)
    active = (
        f"`{_sanitize_inline(sess.active_worker, max_len=80)}`" if sess is not None else "없음"
    )
    return [
        "",
        "### 컨텍스트 압축 직후",
        "",
        f"- 활성 워커 세션: {active}",
        f"- 워커 JD 원문은 `{company_root}/hired/<name>.md` 에 있다. 압축 전에 어떤 워커로"
        " 빙의 (embody) 해 작업 중이었다면, 요약된 기억으로 이어가지 말고 그 파일을 다시 읽는다.",
        "- 압축 전에 끝낸 작업의 결재 기록 (`lskun-audit record`) 여부가 불확실하면"
        f" `{company_root}/.audit/decisions.jsonl` 마지막 줄로 확인한다.",
    ]


def _find_active_company_root() -> Path | None:
    """cwd 부터 상위로 ``CLAUDE.md`` 의 LSKUN-CPO marker 탐색 → 회사 root 반환.

    ADR-0015 결정 1-A + 결정 2-B — CLAUDE.md marker 가 회사-프로젝트 결합의
    단일 진실원. marker 의 회사 이름으로 ``~/.lskun-companies/<name>/`` 를
    resolve.

    git root 경계: monorepo 의 하위 프로젝트에서 세션을 열어도 상위의 다른
    회사 marker 가 잘못 잡히지 않도록 차단.

    Returns:
        활성 회사 root path (``~/.lskun-companies/<name>/``) 또는 ``None``.
    """

    found = _find_marker_project()
    return found[1] if found is not None else None


def _find_marker_project() -> "tuple[Path, Path] | None":
    """(marker 가 있는 프로젝트 디렉토리, 활성 회사 root). 없으면 ``None``.

    ``_find_active_company_root`` 와 같은 탐색 규칙. ADR-0029 D4·D6 는 marker 가
    어느 디렉토리의 어떤 방식 (pointer / inline) 인지 알아야 한다.
    """

    from lskun_kit.paths import company_root
    from lskun_kit.persona_injection import (
        extract_company_name,
        has_marker_file,
    )

    cwd = Path.cwd()
    for _ in range(MAX_PARENT_DEPTH + 1):
        if has_marker_file(cwd):  # ADR-0029 D7 — CLAUDE.local.md 우선, 그다음 CLAUDE.md
            name = extract_company_name(cwd)
            if name:
                try:
                    co_root = company_root(name)
                except ValueError:
                    return None
                if (co_root / "company.md").exists():
                    return cwd, co_root
                return None  # marker 는 있는데 회사 디렉토리 부재 — silent
        if (cwd / ".git").exists():
            break
        if cwd.parent == cwd:  # filesystem root
            break
        cwd = cwd.parent

    return None


def _read_company_meta(company_root: Path) -> dict[str, str]:
    company_md = company_root / "company.md"
    if not company_md.exists():
        return {}
    try:
        text = company_md.read_text(encoding="utf-8")
    except OSError:
        return {}
    return _parse_frontmatter_dict(text)


def _list_workers_with_meta(company_root: Path) -> list[dict[str, str]]:
    hired = company_root / "hired"
    if not hired.exists():
        return []
    out: list[dict[str, str]] = []
    for p in sorted(hired.glob("*.md")):
        if not p.is_file():
            continue
        # P39 (#5) 의 allowlist 와 호환되지 않는 파일명 (예: .audit.jsonl 등) 제외.
        if p.name.startswith("."):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = _parse_frontmatter_dict(text)
        fm.setdefault("name", p.stem)
        out.append(fm)
    return out


def _parse_frontmatter_dict(text: str) -> dict[str, str]:
    """LSKunCompanyKit 공식 frontmatter 파서로 위임 (P40).

    이전 인라인 구현은 따옴표 strip / CRLF 처리 등에서 ``adapters.frontmatter.parse``
    와 미묘하게 달랐다. 단일 진입점으로 통합해 동작 불일치를 제거한다.
    지연 import 로 hooks 모듈의 직접 import 의존성은 그대로 회피.
    """

    from lskun_kit.adapters.frontmatter import parse  # 지연 import

    return dict(parse(text).frontmatter)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
