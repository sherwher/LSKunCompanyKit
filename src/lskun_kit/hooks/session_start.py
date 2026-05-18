"""SessionStart hook — 활성 회사가 있으면 dynamic context 를 메인 세션에 주입.

ADR-0004 §1 의 2-layer persona 주입 중 layer B (보조):
    - layer A: 사용자 프로젝트 root 의 ``CLAUDE.md`` marker 구간 (정적 persona) — P23
    - **layer B (본 모듈): 매 세션 시작 시 회사/hired/CPO history 동적 주입** — P24

ADR-0004 §7 — 활성 회사 없으면 silent no-op (출력 0). 사용자가 LSKunCompanyKit 을
설치만 했고 회사 셋업을 안 했다면 본 hook 은 침묵.

출력 포맷 (stdout):
    Claude Code 의 SessionStart hook 사양에 따라 JSON 1줄 emit:
    {"hookSpecificOutput": {"hookEventName": "SessionStart",
                             "additionalContext": "<markdown 문자열>"}}

입력 (stdin):
    Claude Code 가 hook payload 를 JSON 으로 주입할 수 있으나, 본 hook 은 그것에
    의존하지 않고 환경변수 / 현재 작업 디렉토리만으로 활성 회사를 감지한다.

활성 회사 감지 우선순위:
    1. ``LSKUN_VAULT`` 환경변수 → Vault backend. ``LSKUN_COMPANY`` 가 가리키는 회사.
    2. ``$PWD/.company/`` → Local backend.
    3. 위 둘 다 부재 → 부모 디렉토리로 올라가며 ``.company/`` 탐색 (최대 5 depth).
    4. 끝까지 없으면 silent no-op.

종료 코드: 항상 0 (hook 실패가 세션을 막으면 안 됨).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# stdlib only — plugin 정책

MAX_PARENT_DEPTH = 5
RECENT_HISTORY_LINES = 5


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
    cpo_history = _read_cpo_recent_history(company_root, RECENT_HISTORY_LINES)

    lines = [
        "## LSKunCompanyKit — 활성 회사",
        "",
        f"- 회사: **{company_meta.get('name', '(이름 미박제)')}**"
        + (f" (domain={company_meta['domain']})" if company_meta.get("domain") else ""),
        f"- 회사 root: `{company_root}`",
        "",
        "### Hired 워커",
    ]
    if workers:
        for w in workers:
            role = w.get("role", "?")
            domain = w.get("domain", "?")
            display = w.get("display_name", w["name"])
            model = w.get("model")
            model_part = f", model={model}" if model else ""
            lines.append(
                f"- `{w['name']}` — {display} ({role}, domain={domain}{model_part})"
            )
    else:
        lines.append("_(없음)_")

    if cpo_history:
        lines.extend(["", f"### CPO 최근 history ({len(cpo_history)} lines)"])
        lines.extend(cpo_history)

    lines.extend(
        [
            "",
            "> ADR-0004 §1 — 본 메인 세션은 CPO persona 로 동작 (CLAUDE.md 박제 참조).",
            "> 사용자 요청 처리 시: `hired/` 워커 검색 → 적합 워커가 있으면 Task tool 로 dispatch,",
            "> 없으면 HR Lead 를 Task tool 로 호출해 채용 → 신규 워커 dispatch. 사용자 알림 1줄.",
            "> ADR-0004 §8 — **워커 세션 중 Task tool 호출은 PreToolUse hook 이 차단한다** "
            "(워커 → 워커 chain 금지). 결재 필요 시 세션 종료 후 메인 세션 = CPO 가 처리.",
        ]
    )
    return "\n".join(lines) + "\n"


def _find_active_company_root() -> Path | None:
    """우선순위: Vault env → cwd 의 .company → 부모 디렉토리 탐색."""

    vault = os.environ.get("LSKUN_VAULT", "").strip()
    company = os.environ.get("LSKUN_COMPANY", "").strip()
    if vault and company:
        candidate = Path(vault).expanduser() / "03_Companies" / company
        if (candidate / "company.md").exists():
            return candidate

    cwd = Path.cwd()
    for i in range(MAX_PARENT_DEPTH + 1):
        candidate = cwd / ".company"
        if (candidate / "company.md").exists():
            return candidate
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
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = _parse_frontmatter_dict(text)
        fm.setdefault("name", p.stem)
        out.append(fm)
    return out


def _read_cpo_recent_history(company_root: Path, n: int) -> list[str]:
    cpo_md = company_root / "hired" / "cpo.md"
    if not cpo_md.exists():
        return []
    try:
        text = cpo_md.read_text(encoding="utf-8")
    except OSError:
        return []
    marker = "## Project History"
    if marker not in text:
        return []
    body = text.split(marker, 1)[1]
    # 다음 ## 헤딩 전까지
    if "\n## " in body:
        body = body.split("\n## ", 1)[0]
    history_lines = [ln for ln in body.splitlines() if ln.startswith("- ")]
    return history_lines[-n:]


def _parse_frontmatter_dict(text: str) -> dict[str, str]:
    """YAML 의존 없이 ``key: value`` 단순 frontmatter 만 파싱.

    list / nested 는 지원하지 않음 — LSKunCompanyKit frontmatter 는 모두 scalar.
    """

    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    block = text[4:end]
    out: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        out[k.strip()] = v.strip()
    return out


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
