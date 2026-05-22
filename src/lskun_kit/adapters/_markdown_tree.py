"""Local / Vault 양쪽이 공유하는 markdown-tree 기반 storage 구현.

두 backend 모두 ``<root>/company.md`` + ``<root>/hired/<name>.md`` 레이아웃을 쓰며,
root 경로 결정 + SSOT guard 만 다르다. 따라서 본 기반 클래스가 4-method interface 의
공통 동작을 정의하고, 구체 adapter 는 ``__init__`` 에서 root 만 결정한다.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from lskun_kit.adapters import frontmatter
from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.errors import (
    InvalidWorkerSchemaError,
    SSOTContaminationError,
    WorkerNotFoundError,
)
from lskun_kit.models import (
    OPTIONAL_WORKER_FIELDS,
    REQUIRED_WORKER_FIELDS,
    Company,
    Worker,
)

# ADR-0014 (2026-05-22) — Reflection 폐기. 옛 history 섹션 heading 은
# migrate-schema 의 `## Project History` → `## Archived History (pre-0.18)`
# rename 로직에서만 참조됨 (사용자 자산 보존 정책).
LEGACY_HISTORY_HEADING = "## Project History"
ARCHIVED_HISTORY_HEADING = "## Archived History (pre-0.18)"

# ADR-0001 §5 — 개발자 SSOT 경로 단편. root 에 포함되면 거부.
DEVELOPER_SSOT_MARKERS = ("02_Projects/LSKunCompanyKit",)

# P39 (#5) — 워커 이름 허용 문자 allowlist. kebab-case + 숫자, 시작은 영문/숫자.
# null byte, backslash, dotted 경로, 유니코드 변종 등 path traversal 표면 차단.
_WORKER_NAME_PAT = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


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

    # --- ADR-0006: audit log ---

    @property
    def audit_path(self) -> Path:
        """``.audit/decisions.jsonl`` 절대 경로. 디렉토리 자동 생성 X (write 시점에)."""
        return self._root / ".audit" / "decisions.jsonl"

    def append_audit(self, json_line: str) -> Path:
        """``.audit/decisions.jsonl`` 에 1줄 append. 디렉토리 부재 시 자동 생성.

        ADR-0006 §6 — append-only. 기존 줄 수정·삭제 금지. 호출자는
        :func:`lskun_kit.audit.record` 를 통해 schema 검증 후 본 메서드 호출.
        """

        if "\n" in json_line:
            raise ValueError(
                "audit json_line must be single-line (no embedded newline)"
            )
        path = self.audit_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json_line + "\n")
        return path

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

        known_fields = REQUIRED_WORKER_FIELDS + OPTIONAL_WORKER_FIELDS
        return Worker(
            name=parsed.frontmatter["name"],
            role=parsed.frontmatter["role"],
            domain=parsed.frontmatter["domain"],
            hired_at=_parse_date(parsed.frontmatter["hired_at"]),
            storage_backend=parsed.frontmatter["storage_backend"],
            display_name=parsed.frontmatter["display_name"],
            model=parsed.frontmatter.get("model"),
            persona_synced_from=parsed.frontmatter.get("persona_synced_from"),
            persona_synced_at=parsed.frontmatter.get("persona_synced_at"),
            keywords=parsed.frontmatter.get("keywords"),
            body=parsed.body,
            extra={
                k: v
                for k, v in parsed.frontmatter.items()
                if k not in known_fields
            },
        )

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

    # --- P45: write-path 구현 ---

    def create_worker(
        self,
        name: str,
        frontmatter_dict: dict[str, str],
        body: str,
    ) -> None:
        """``hired/<name>.md`` 신규 박제. 존재하면 ``FileExistsError`` raise."""

        path = self._worker_path(name)  # allowlist 가드 통과
        if path.exists():
            raise FileExistsError(
                f"worker already exists: hired/{name}.md ({path})"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        text = frontmatter.dump(frontmatter_dict, body)
        path.write_text(text, encoding="utf-8")

    def archive_worker(self, name: str) -> None:
        """``hired/<name>.md`` → ``archived/<name>.md`` 이동. 삭제 금지."""

        path = self._worker_path(name)
        if not path.exists():
            raise WorkerNotFoundError(
                f"cannot archive: hired/{name}.md not found under {self._root}"
            )
        archive_dir = self._root / "archived"
        archive_dir.mkdir(parents=True, exist_ok=True)
        dest = archive_dir / f"{name}.md"
        if dest.exists():
            raise FileExistsError(
                f"archived worker already exists: {dest} "
                f"(이미 archive 된 동명 워커가 있음 — 수동 정리 필요)"
            )
        path.rename(dest)

    def _worker_path(self, name: str) -> Path:
        # P39 (#5) — allowlist 검증. 기존 deny-list (``/``, ``.``, ``..``) 만으로는
        # null byte / backslash / 유니코드 변종 / dotted path 를 못 잡았다.
        if not isinstance(name, str) or not _WORKER_NAME_PAT.match(name):
            raise ValueError(
                f"invalid worker name: {name!r} "
                f"(허용: ^[a-z0-9][a-z0-9_-]{{0,63}}$)"
            )
        candidate = self._hired_dir / f"{name}.md"
        # 추가 가드 — 정규식을 통과해도 resolve 결과가 hired/ 밖으로 새면 거부.
        try:
            resolved = candidate.resolve(strict=False)
            hired_resolved = self._hired_dir.resolve(strict=False)
            if not str(resolved).startswith(str(hired_resolved)):
                raise ValueError(
                    f"worker path escapes hired/: {resolved}"
                )
        except (OSError, RuntimeError) as e:
            raise ValueError(f"failed to resolve worker path: {name!r} ({e})")
        return candidate

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


