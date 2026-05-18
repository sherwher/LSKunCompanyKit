"""프로젝트 → 회사 link — ADR-0007.

축 C (사용자 프로젝트) 가 축 B (회사 SSOT) 를 가리키는 ``.claude/lskun-kit.json``
의 read / write / schema 검증.

진실원 순서 (ADR-0007 §4):
    1. ``<project>/.claude/lskun-kit.json`` 의 ``company``
    2. 회사 SSOT (``<vault>/03_Companies/<company>/`` 또는 ``<project>/.company/``)
    3. CLAUDE.md marker (캐시 fallback)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from lskun_kit.errors import LSKunKitError

LINK_DIRNAME = ".claude"
LINK_FILENAME = "lskun-kit.json"

#: ADR-0007 §3 — backend enum
BACKEND_VAULT = "vault"
BACKEND_LOCAL = "local"
_VALID_BACKENDS = frozenset({BACKEND_VAULT, BACKEND_LOCAL})


class ProjectLinkError(LSKunKitError):
    """``.claude/lskun-kit.json`` schema 위반 또는 IO 실패."""


@dataclass(frozen=True)
class ProjectLink:
    """``.claude/lskun-kit.json`` 1건. ADR-0007 §3 schema."""

    company: str
    backend: str | None = None  # "vault" | "local" | None (auto)
    backend_root: str | None = None  # optional abs path override

    def __post_init__(self) -> None:
        if not self.company or not self.company.strip():
            raise ProjectLinkError("company is required and must be non-empty")
        if "/" in self.company or self.company in (".", ".."):
            raise ProjectLinkError(f"invalid company name: {self.company!r}")
        if self.backend is not None and self.backend not in _VALID_BACKENDS:
            raise ProjectLinkError(
                f"backend must be one of {sorted(_VALID_BACKENDS)} or None, "
                f"got {self.backend!r}"
            )
        if self.backend_root is not None:
            if not self.backend_root.strip():
                raise ProjectLinkError("backend_root must be non-empty if provided")
            if not Path(self.backend_root).is_absolute():
                raise ProjectLinkError(
                    f"backend_root must be absolute path, got {self.backend_root!r}"
                )

    def to_dict(self) -> dict[str, str]:
        out: dict[str, str] = {"company": self.company}
        if self.backend is not None:
            out["backend"] = self.backend
        if self.backend_root is not None:
            out["backend_root"] = self.backend_root
        return out


def link_path(project_root: Path | str) -> Path:
    """``<project>/.claude/lskun-kit.json`` 절대 경로."""
    return Path(project_root).expanduser() / LINK_DIRNAME / LINK_FILENAME


def read(project_root: Path | str) -> ProjectLink | None:
    """link 파일을 읽어 :class:`ProjectLink` 반환. 부재 시 ``None``.

    Raises:
        ProjectLinkError: 파일 존재 but JSON parse 실패 / schema 위반.
    """

    p = link_path(project_root)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ProjectLinkError(f"failed to parse {p}: {e}") from e
    if not isinstance(data, dict):
        raise ProjectLinkError(f"{p} must be a JSON object, got {type(data).__name__}")
    company = data.get("company")
    if not isinstance(company, str):
        raise ProjectLinkError(
            f"{p}: 'company' must be string, got {type(company).__name__}"
        )
    backend = data.get("backend")
    if backend is not None and not isinstance(backend, str):
        raise ProjectLinkError(
            f"{p}: 'backend' must be string or absent, got {type(backend).__name__}"
        )
    backend_root = data.get("backend_root")
    if backend_root is not None and not isinstance(backend_root, str):
        raise ProjectLinkError(
            f"{p}: 'backend_root' must be string or absent, "
            f"got {type(backend_root).__name__}"
        )
    return ProjectLink(company=company, backend=backend, backend_root=backend_root)


def write(project_root: Path | str, link: ProjectLink, *, overwrite: bool = False) -> Path:
    """link 파일을 박제. 기본은 idempotent (동일 내용이면 noop, 다르면 raise).

    ``overwrite=True`` 면 기존 내용을 무조건 덮어쓴다.

    Returns:
        Path: 박제된 파일 경로.
    """

    p = link_path(project_root)
    p.parent.mkdir(parents=True, exist_ok=True)

    new_text = json.dumps(link.to_dict(), ensure_ascii=False, indent=2) + "\n"
    if p.exists() and not overwrite:
        existing = p.read_text(encoding="utf-8")
        if existing == new_text:
            return p  # idempotent
        existing_link = read(project_root)
        if existing_link == link:
            return p  # 동일 의미, format 만 다름 → noop
        raise ProjectLinkError(
            f"{p} already exists with different content. "
            f"existing.company={existing_link.company if existing_link else '?'}, "
            f"new.company={link.company}. use overwrite=True to replace."
        )
    p.write_text(new_text, encoding="utf-8")
    return p


__all__ = [
    "LINK_DIRNAME",
    "LINK_FILENAME",
    "BACKEND_VAULT",
    "BACKEND_LOCAL",
    "ProjectLink",
    "ProjectLinkError",
    "link_path",
    "read",
    "write",
]
