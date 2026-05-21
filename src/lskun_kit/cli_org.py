"""``/lskun-kit:org`` canonical entrypoint — P75 합의안.

P75 — 4 에이전트 (critic / architect / analyst / planner) 합의로 다음 박제:
- **self-bootstrap**: ``$CLAUDE_PLUGIN_ROOT`` env var 미주입 회피.
  파일 자기 위치 기반으로 ``sys.path`` 자체 보정 → PYTHONPATH 의존 0.
  ``python3 <plugin>/src/lskun_kit/cli_org.py`` 직접 실행 가능.
- **--domain** 필터: 출력 길이 제어 (41명 → 도메인별 N명).
- **--export <path>**: stdout dump 를 파일에 쓰기 (Obsidian/GitHub 렌더링용).
- **org-chart.md 정적 인덱스 도입 폐기** — SSOT 이중화·SRP 위반 위험으로 합의 거부.

사용::

    python3 /path/to/cli_org.py [--full] [--include-archived]
                                [--domain DOM] [--export PATH]
"""

from __future__ import annotations

# ── P75-1: self-bootstrap (PYTHONPATH 의존 제거) ──
# `cli_org.py` 가 `lskun_kit/` 안에 있으므로 부모 디렉토리를 sys.path 에 넣으면
# `from lskun_kit import org` 가 외부 env var 없이 동작.
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
_PKG_PARENT = _THIS.parent.parent  # .../src/
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

import argparse
import os

MAX_PARENT_DEPTH = 5


def _find_active_company_root() -> Path | None:
    """우선순위: ``LSKUN_VAULT`` + ``LSKUN_COMPANY`` → cwd 상향 ``.company/``."""
    vault = os.environ.get("LSKUN_VAULT", "").strip()
    company = os.environ.get("LSKUN_COMPANY", "").strip()
    if vault and company:
        candidate = Path(vault).expanduser() / "03_Companies" / company
        if (candidate / "company.md").exists():
            return candidate

    cwd = Path.cwd()
    for _ in range(MAX_PARENT_DEPTH + 1):
        candidate = cwd / ".company"
        if (candidate / "company.md").exists():
            return candidate
        if (cwd / ".git").exists():
            break
        if cwd.parent == cwd:
            break
        cwd = cwd.parent
    return None


def _build_adapter(root: Path):
    from lskun_kit.adapters.local import LocalAdapter
    from lskun_kit.adapters.vault import COMPANIES_DIRNAME, VaultAdapter

    parts = root.parts
    if COMPANIES_DIRNAME in parts:
        idx = parts.index(COMPANIES_DIRNAME)
        vault = Path(*parts[:idx])
        company = parts[idx + 1]
        return VaultAdapter(vault, company)
    return LocalAdapter(root)


def _filter_by_domain(report, domain: str):
    """OrgReport 의 entries 를 domain prefix 매칭으로 필터.

    완전일치 또는 prefix 일치 (``tech`` 입력 시 ``tech-backend`` / ``tech-frontend``
    모두 매치). 대소문자 무시.
    """
    needle = domain.strip().lower()
    if not needle:
        return report
    filtered = [
        e for e in report.entries
        if e.domain.lower() == needle or e.domain.lower().startswith(needle + "-")
    ]
    report.entries = filtered
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lskun-kit:org",
        description="조직도 read-only view (P75 합의안)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="옛 markdown table 포맷 (ADR-0013 stable). 기본은 compact 1줄.",
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="archived/ 워커도 별도 섹션으로 표시",
    )
    parser.add_argument(
        "--domain",
        default=None,
        help="도메인 필터 (prefix 매칭). 예: --domain tech 는 tech-* 모두 매치",
    )
    parser.add_argument(
        "--export",
        default=None,
        help="stdout 대신 지정 경로의 파일에 쓰기 (Obsidian/GitHub 렌더링용)",
    )
    args = parser.parse_args(argv)

    root = _find_active_company_root()
    if root is None:
        sys.stderr.write(
            "활성 회사를 찾지 못했다. `LSKUN_VAULT` + `LSKUN_COMPANY` 환경변수 "
            "또는 `.company/` 디렉토리가 필요하다.\n"
        )
        return 2

    from lskun_kit import org

    adapter = _build_adapter(root)
    report = org.build(adapter, include_archived=args.include_archived)
    if args.domain:
        report = _filter_by_domain(report, args.domain)

    output = report.render(
        include_archived=args.include_archived,
        compact=not args.full,
    )

    if args.export:
        export_path = Path(args.export).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(output, encoding="utf-8")
        sys.stdout.write(f"org snapshot saved to: {export_path}\n")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
