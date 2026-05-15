"""Vault storage backend — ``<vault>/03_Companies/<company>/``.

ADR-0001 §4 의 두 번째 backend. Obsidian / Logseq 같은 사용자 vault 안에
회사 운영 데이터를 두고 OS file sync 로 멀티 PC 동기화한다.

레이아웃 (한 vault 가 N개 회사를 가질 수 있음)::

    <vault>/
        03_Companies/
            <company-a>/
                company.md
                hired/...
            <company-b>/
                ...

따라서 :class:`VaultAdapter` 는 단일 회사를 지정해야 인스턴스화된다.
멀티 회사 탐색은 :func:`list_companies` 헬퍼가 담당한다.
"""

from __future__ import annotations

from pathlib import Path

from lskun_kit.adapters._markdown_tree import MarkdownTreeAdapter
from lskun_kit.errors import LSKunKitError

COMPANIES_DIRNAME = "03_Companies"


class VaultCompanyNotFoundError(LSKunKitError):
    """지정한 vault 안에 해당 company 디렉토리가 없을 때 발생."""


class VaultAdapter(MarkdownTreeAdapter):
    """``<vault>/03_Companies/<company>/`` 를 사용자 SSOT 로 쓰는 adapter."""

    def __init__(self, vault: Path | str, company: str) -> None:
        if not company or "/" in company or company in (".", ".."):
            raise ValueError(f"invalid company name: {company!r}")

        vault_path = Path(vault).expanduser()
        root = vault_path / COMPANIES_DIRNAME / company

        if not (vault_path / COMPANIES_DIRNAME).exists():
            raise VaultCompanyNotFoundError(
                f"vault has no '{COMPANIES_DIRNAME}/' directory: {vault_path}"
            )
        if not root.exists():
            raise VaultCompanyNotFoundError(
                f"company '{company}' not found under {vault_path / COMPANIES_DIRNAME}. "
                f"available: {sorted(list_companies(vault_path))}"
            )

        super().__init__(root)
        self._vault = vault_path
        self._company = company

    @property
    def vault(self) -> Path:
        return self._vault

    @property
    def company(self) -> str:
        return self._company


def list_companies(vault: Path | str) -> list[str]:
    """vault 안의 ``03_Companies/`` 하위 회사 이름 정렬 목록.

    디렉토리가 없으면 빈 리스트. 점-prefix (``.obsidian`` 등) 는 제외.
    """

    companies_dir = Path(vault).expanduser() / COMPANIES_DIRNAME
    if not companies_dir.exists():
        return []
    return sorted(
        p.name
        for p in companies_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )
