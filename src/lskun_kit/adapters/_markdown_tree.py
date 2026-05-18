"""Local / Vault 양쪽이 공유하는 markdown-tree 기반 storage 구현.

두 backend 모두 ``<root>/company.md`` + ``<root>/hired/<name>.md`` 레이아웃을 쓰며,
root 경로 결정 + SSOT guard 만 다르다. 따라서 본 기반 클래스가 4-method interface 의
공통 동작을 정의하고, 구체 adapter 는 ``__init__`` 에서 root 만 결정한다.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from lskun_kit.adapters import frontmatter
from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.errors import (
    InvalidWorkerSchemaError,
    SSOTContaminationError,
    WorkerNotFoundError,
)
from lskun_kit.models import REQUIRED_WORKER_FIELDS, Company, HistoryEntry, Worker

HISTORY_HEADING = "## Project History"

# ADR-0001 §5 — 개발자 SSOT 경로 단편. root 에 포함되면 거부.
DEVELOPER_SSOT_MARKERS = ("02_Projects/LSKunCompanyKit",)


class MarkdownTreeAdapter(StorageAdapter):
    """공통 동작을 담은 기반 클래스. 직접 인스턴스화하지 말 것."""

    def __init__(self, root: Path | str) -> None:
        root_path = Path(root).expanduser()
        self._guard_against_developer_ssot(root_path)
        self._root = root_path
        self._hired_dir = self._root / "hired"
        self._company_file = self._root / "company.md"

    @property
    def root(self) -> Path:
        return self._root

    def read_worker(self, name: str) -> Worker:
        path = self._worker_path(name)
        if not path.exists():
            raise WorkerNotFoundError(f"hired/{name}.md not found under {self._root}")

        parsed = frontmatter.parse(path.read_text(encoding="utf-8"))
        missing = [f for f in REQUIRED_WORKER_FIELDS if f not in parsed.frontmatter]
        if missing:
            raise InvalidWorkerSchemaError(
                f"hired/{name}.md missing required fields: {', '.join(missing)}"
            )

        return Worker(
            name=parsed.frontmatter["name"],
            role=parsed.frontmatter["role"],
            domain=parsed.frontmatter["domain"],
            hired_at=_parse_date(parsed.frontmatter["hired_at"]),
            storage_backend=parsed.frontmatter["storage_backend"],
            body=parsed.body,
            extra={
                k: v
                for k, v in parsed.frontmatter.items()
                if k not in REQUIRED_WORKER_FIELDS
            },
        )

    def append_history(self, name: str, entry: HistoryEntry) -> None:
        path = self._worker_path(name)
        if not path.exists():
            raise WorkerNotFoundError(f"hired/{name}.md not found under {self._root}")

        text = path.read_text(encoding="utf-8")
        updated = _append_history_line(text, entry.render())
        path.write_text(updated, encoding="utf-8")

    def list_workers(self) -> list[str]:
        if not self._hired_dir.exists():
            return []
        return sorted(p.stem for p in self._hired_dir.glob("*.md") if p.is_file())

    def read_company(self) -> Company:
        if not self._company_file.exists():
            return Company(name="", body="", extra={})
        parsed = frontmatter.parse(self._company_file.read_text(encoding="utf-8"))
        return Company(
            name=parsed.frontmatter.get("name", ""),
            body=parsed.body,
            extra={k: v for k, v in parsed.frontmatter.items() if k != "name"},
        )

    def _worker_path(self, name: str) -> Path:
        if "/" in name or name in ("", ".", ".."):
            raise ValueError(f"invalid worker name: {name!r}")
        return self._hired_dir / f"{name}.md"

    @staticmethod
    def _guard_against_developer_ssot(root: Path) -> None:
        as_posix = root.as_posix()
        for marker in DEVELOPER_SSOT_MARKERS:
            if marker in as_posix:
                raise SSOTContaminationError(
                    f"refusing to use developer SSOT path as user SSOT root: {root} "
                    f"(matched marker: {marker!r}). See ADR-0001 §5."
                )


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _append_history_line(text: str, line: str) -> str:
    """``## Project History`` 섹션 끝에 1줄 append. 섹션 없으면 생성."""

    if HISTORY_HEADING not in text:
        suffix = "" if text.endswith("\n") else "\n"
        return f"{text}{suffix}\n{HISTORY_HEADING}\n\n{line}\n"

    lines = text.splitlines(keepends=False)
    out: list[str] = []
    inserted = False
    i = 0
    while i < len(lines):
        out.append(lines[i])
        if not inserted and lines[i].strip() == HISTORY_HEADING:
            j = i + 1
            section_lines: list[str] = []
            while j < len(lines) and not lines[j].lstrip().startswith("## "):
                section_lines.append(lines[j])
                j += 1
            while section_lines and section_lines[-1].strip() == "":
                section_lines.pop()
            out.extend(section_lines)
            out.append(line)
            i = j - 1
            inserted = True
        i += 1

    result = "\n".join(out)
    if not result.endswith("\n"):
        result += "\n"
    return result
