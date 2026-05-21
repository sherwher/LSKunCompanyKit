"""``/lskun-kit:org`` canonical entrypoint — ADR-0013 stable format.

`commands/org.md` 가 본 모듈 1개를 호출하도록 박제 (LLM 추론 우회 방지).
backend 결정은 ``hooks/session_start._find_active_company_root`` 와 동일 규칙.

사용::

    python3 -m lskun_kit.cli_org [--compact] [--include-archived]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lskun-kit:org",
        description="조직도 read-only view (ADR-0013 markdown table)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="컬럼 폭이 좁은 1줄 포맷 (name (display) — role · domain · model · h=N)",
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="archived/ 워커도 별도 섹션으로 표시",
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
    sys.stdout.write(
        report.render(include_archived=args.include_archived, compact=args.compact)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
