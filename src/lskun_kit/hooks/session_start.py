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

활성 회사 감지 우선순위 (ADR-0015 — Vault backend 폐기):
    1. ``$PWD/.company/`` → Local backend.
    2. 부재 시 부모 디렉토리로 올라가며 ``.company/`` 탐색 (최대 5 depth, git root 경계).
    3. 끝까지 없으면 silent no-op.

P88 에서 CLAUDE.md marker 기반 통일 + ``~/.lskun-companies/<name>/`` 직접 read 로 교체 예정.

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


def main(argv: list[str] | None = None) -> int:
    try:
        context = _build_context()
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


def _build_context() -> str:
    company_root = _find_active_company_root()
    if company_root is None:
        return ""

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
        "",
        "### Hired 워커",
    ]
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
    return "\n".join(lines) + "\n"


def _find_active_company_root() -> Path | None:
    """cwd 부터 상위로 ``.company/`` 탐색 (최대 5 depth, git root 경계).

    ADR-0015 (2026-05-22) — Vault backend 폐기. ``LSKUN_VAULT`` env 분기 제거.
    P88 에서 CLAUDE.md marker 기반 통일 예정.
    """

    cwd = Path.cwd()
    for i in range(MAX_PARENT_DEPTH + 1):
        candidate = cwd / ".company"
        if (candidate / "company.md").exists():
            return candidate
        # P38 (#17) — git repo root 를 넘지 않는다. monorepo 의 하위 프로젝트에서
        # 세션을 열었을 때 상위의 다른 회사 .company/ 가 잘못 잡히는 것을 방지.
        if (cwd / ".git").exists():
            break
        if cwd.parent == cwd:  # filesystem root
            break
        cwd = cwd.parent
        if i >= MAX_PARENT_DEPTH:
            break

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
