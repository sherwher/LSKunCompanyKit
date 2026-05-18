"""Schema 마이그레이션 — ADR-0005.

기존에 v0.2 (4 필수 필드) 또는 v0.3 (5 필수 필드) 으로 생성된 회사를 v0.4 schema
(6 필수 필드 + CLAUDE.md marker 박제) 로 끌어올린다. history 는 한 줄도 건드리지
않으며, frontmatter 의 누락 필드만 보강한다.

원칙 (불변):
    - history 절대 보존 (Project History 섹션 read-only)
    - frontmatter 기존 키 덮어쓰기 금지 — 누락된 키만 추가
    - 변경 전 ``<file>.lskun-pre-migrate.bak`` 자동 백업
    - dry-run 으로 사전 확인 가능
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import date as date_cls
from pathlib import Path

from lskun_kit.adapters import frontmatter as fm
from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.errors import LSKunKitError
from lskun_kit.models import REQUIRED_WORKER_FIELDS
from lskun_kit.persona_injection import detect as detect_persona

BACKUP_SUFFIX = ".lskun-pre-migrate.bak"

#: v0.2 schema — ADR-0001 시점의 4 필드 (name, role, hired_at, storage_backend)
SCHEMA_V0_2_FIELDS = ("name", "role", "hired_at", "storage_backend")
#: v0.3 schema — ADR-0003 추가 (domain)
SCHEMA_V0_3_FIELDS = SCHEMA_V0_2_FIELDS + ("domain",)
#: v0.4 schema — ADR-0004 §6 추가 (display_name)
SCHEMA_V0_4_FIELDS = REQUIRED_WORKER_FIELDS  # 6개


class SchemaMigrationError(LSKunKitError):
    """Schema 마이그레이션 실패."""


@dataclass(frozen=True)
class WorkerSchemaGap:
    """단일 워커의 schema 누락 정보."""

    name: str
    path: Path
    missing_fields: tuple[str, ...]
    detected_schema: str  # "v0.2" | "v0.3" | "v0.4"


@dataclass
class MigrationPlan:
    """``/lskun-kit:migrate-schema`` 가 실행 전 사용자에게 보여줄 변환 계획."""

    backend: str
    company_root: Path
    company_md_path: Path
    company_missing_fields: tuple[str, ...]  # company.md frontmatter 의 누락 필드
    company_detected_schema: str
    worker_gaps: list[WorkerSchemaGap] = field(default_factory=list)
    claude_md_path: Path | None = None
    claude_md_marker_missing: bool = False

    @property
    def is_no_op(self) -> bool:
        return (
            not self.company_missing_fields
            and not self.worker_gaps
            and not self.claude_md_marker_missing
        )

    def render(self) -> str:
        lines = [
            "Migration Plan",
            "================================================",
            f"backend       : {self.backend}",
            f"company root  : {self.company_root}",
            f"company.md    : detected schema={self.company_detected_schema}, "
            + (f"missing={list(self.company_missing_fields)}"
               if self.company_missing_fields else "OK"),
        ]
        if self.worker_gaps:
            lines.append("workers:")
            for g in self.worker_gaps:
                lines.append(
                    f"  - {g.name}: schema={g.detected_schema}, "
                    f"missing={list(g.missing_fields)}"
                )
        else:
            lines.append("workers       : 모든 워커가 v0.4 schema 통과")
        if self.claude_md_path is not None:
            lines.append(
                f"CLAUDE.md     : {self.claude_md_path} "
                + ("(marker 부재 — 박제 필요)" if self.claude_md_marker_missing else "(marker 정상)")
            )
        if self.is_no_op:
            lines.append("")
            lines.append("결과: migration 불필요 — 이미 v0.4 schema.")
        return "\n".join(lines) + "\n"


@dataclass
class MigrationAnswers:
    """사용자 인터뷰 응답."""

    company_domain: str = ""  # company.md 에 박제할 도메인
    worker_display_names: dict[str, str] = field(default_factory=dict)  # name → display_name
    worker_domains: dict[str, str] = field(default_factory=dict)  # name → domain (v0.2 → 워커별 박제)
    # CLAUDE.md marker 박제용 — CPO display_name 은 자동으로 worker_display_names["cpo"] 사용


@dataclass
class MigrationResult:
    """실행 후 사용자에게 표시할 결과."""

    plan: MigrationPlan
    company_md_updated: bool = False
    workers_updated: list[str] = field(default_factory=list)
    backups_created: list[Path] = field(default_factory=list)
    claude_md_action: str = "skipped"  # "created" | "updated" | "skipped" | "unchanged"
    notes: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            "Migration Result",
            "================================================",
            f"company.md    : {'updated' if self.company_md_updated else 'unchanged'}",
            f"workers       : {', '.join(self.workers_updated) if self.workers_updated else '(none)'}",
            f"CLAUDE.md     : {self.claude_md_action}",
            f"backups       : {len(self.backups_created)} files",
        ]
        for b in self.backups_created:
            lines.append(f"  - {b}")
        for n in self.notes:
            lines.append(f"note          : {n}")
        return "\n".join(lines) + "\n"


# ---- Detection ----

def detect_worker_schema(worker_fm: dict) -> tuple[str, tuple[str, ...]]:
    """워커 frontmatter dict 에서 schema 버전 + 누락 필드 반환."""

    missing = tuple(f for f in SCHEMA_V0_4_FIELDS if f not in worker_fm)
    if not missing:
        return "v0.4", ()
    if "display_name" in missing and "domain" not in missing:
        return "v0.3", missing
    return "v0.2", missing


def detect_company_schema(company_fm: dict) -> tuple[str, tuple[str, ...]]:
    """company.md frontmatter 가 ADR-0003 의 domain 필드를 가지는지."""

    if "domain" in company_fm and company_fm["domain"]:
        return "v0.3+", ()
    return "v0.2", ("domain",)


# ---- Plan ----

def plan(
    adapter: StorageAdapter,
    company_root: Path,
    backend: str,
    project_root: Path | None = None,
) -> MigrationPlan:
    """변환 계획 작성. 어떤 변경도 하지 않는다."""

    company_md_path = company_root / "company.md"
    company_fm: dict = {}
    if company_md_path.exists():
        parsed = fm.parse(company_md_path.read_text(encoding="utf-8"))
        company_fm = dict(parsed.frontmatter)
    company_schema, company_missing = detect_company_schema(company_fm)

    gaps: list[WorkerSchemaGap] = []
    hired_dir = company_root / "hired"
    if hired_dir.exists():
        for p in sorted(hired_dir.glob("*.md")):
            if not p.is_file() or p.name.startswith("."):
                continue
            parsed_w = fm.parse(p.read_text(encoding="utf-8"))
            schema, missing = detect_worker_schema(dict(parsed_w.frontmatter))
            if missing:
                gaps.append(WorkerSchemaGap(
                    name=p.stem, path=p,
                    missing_fields=missing, detected_schema=schema,
                ))

    claude_md_path: Path | None = None
    marker_missing = False
    if project_root is not None and project_root.exists():
        claude_md_path = project_root / "CLAUDE.md"
        marker_missing = not detect_persona(project_root)

    return MigrationPlan(
        backend=backend,
        company_root=company_root,
        company_md_path=company_md_path,
        company_missing_fields=company_missing,
        company_detected_schema=company_schema,
        worker_gaps=gaps,
        claude_md_path=claude_md_path,
        claude_md_marker_missing=marker_missing,
    )


# ---- Execute ----

def _backup_file(path: Path) -> Path:
    """``<path>.lskun-pre-migrate.bak`` 으로 백업. 이미 있으면 timestamp 부여."""

    backup = path.with_suffix(path.suffix + BACKUP_SUFFIX)
    if backup.exists():
        i = 1
        while True:
            candidate = path.with_suffix(path.suffix + f"{BACKUP_SUFFIX}.{i}")
            if not candidate.exists():
                backup = candidate
                break
            i += 1
    shutil.copy2(path, backup)
    return backup


def _merge_frontmatter(
    existing_text: str, additions: dict[str, str]
) -> str:
    """existing frontmatter 에 누락된 필드만 추가. 기존 값은 절대 덮어쓰지 않음.

    body 는 한 글자도 건드리지 않는다.
    """

    parsed = fm.parse(existing_text)
    new_fm = dict(parsed.frontmatter)
    for key, value in additions.items():
        if key not in new_fm:
            new_fm[key] = value
    return fm.dump(new_fm, parsed.body)


def execute(
    adapter: StorageAdapter,
    plan: MigrationPlan,
    answers: MigrationAnswers,
    inject_persona_fn=None,  # P34 의 persona_injection.inject 주입 (테스트용)
    cpo_body_provider=None,  # cpo body 를 가져오는 callable (adapter 경유 가능)
) -> MigrationResult:
    """실제 변환 수행. plan 의 모든 누락을 answers 로 보강."""

    if plan.is_no_op:
        return MigrationResult(plan=plan, notes=["no-op — 이미 v0.4 schema"])

    result = MigrationResult(plan=plan)

    # 1) company.md domain 보강
    if plan.company_missing_fields and plan.company_md_path.exists():
        if "domain" in plan.company_missing_fields:
            if not answers.company_domain.strip():
                raise SchemaMigrationError(
                    "company.md 의 domain 보강이 필요한데 answers.company_domain 이 비어 있다."
                )
        bak = _backup_file(plan.company_md_path)
        result.backups_created.append(bak)

        additions = {}
        if "domain" in plan.company_missing_fields:
            additions["domain"] = answers.company_domain.strip()
        new_text = _merge_frontmatter(
            plan.company_md_path.read_text(encoding="utf-8"), additions,
        )
        plan.company_md_path.write_text(new_text, encoding="utf-8")
        result.company_md_updated = True

    # 2) 각 워커 보강
    for gap in plan.worker_gaps:
        bak = _backup_file(gap.path)
        result.backups_created.append(bak)

        additions: dict[str, str] = {}
        if "domain" in gap.missing_fields:
            # CPO/HR 은 meta, 그 외는 사용자 응답
            if gap.name in ("cpo", "hr-lead"):
                additions["domain"] = "meta"
            else:
                d = answers.worker_domains.get(gap.name, "").strip()
                if not d:
                    raise SchemaMigrationError(
                        f"워커 {gap.name!r} 의 domain 보강 필요 — "
                        f"answers.worker_domains[{gap.name!r}] 가 비어 있다."
                    )
                additions["domain"] = d
        if "display_name" in gap.missing_fields:
            display = answers.worker_display_names.get(gap.name, "").strip()
            if not display:
                raise SchemaMigrationError(
                    f"워커 {gap.name!r} 의 display_name 보강 필요 — "
                    f"answers.worker_display_names[{gap.name!r}] 가 비어 있다."
                )
            additions["display_name"] = display
        # v0.2 가 storage_backend / hired_at 누락 케이스 — 안전 default
        if "storage_backend" in gap.missing_fields:
            additions["storage_backend"] = plan.backend
        if "hired_at" in gap.missing_fields:
            additions["hired_at"] = date_cls.today().isoformat()

        new_text = _merge_frontmatter(
            gap.path.read_text(encoding="utf-8"), additions,
        )
        gap.path.write_text(new_text, encoding="utf-8")
        result.workers_updated.append(gap.name)

    # 3) CLAUDE.md marker 박제
    if plan.claude_md_marker_missing and plan.claude_md_path is not None:
        if inject_persona_fn is None:
            from lskun_kit.persona_injection import inject as inject_persona_fn  # type: ignore[assignment]
        if cpo_body_provider is None:
            try:
                cpo_worker = adapter.read_worker("cpo")
                cpo_body = cpo_worker.body
                cpo_display = cpo_worker.display_name
            except Exception:
                cpo_body = "# cpo\n\n(persona body unavailable)\n"
                cpo_display = answers.worker_display_names.get("cpo", "CPO")
        else:
            cpo_body, cpo_display = cpo_body_provider()
        company_name = ""
        if plan.company_md_path.exists():
            parsed_c = fm.parse(plan.company_md_path.read_text(encoding="utf-8"))
            company_name = parsed_c.frontmatter.get("name", "")
        inj = inject_persona_fn(
            project_root=plan.claude_md_path.parent,
            company_name=company_name or "(unnamed)",
            cpo_display_name=cpo_display,
            cpo_body=cpo_body,
        )
        result.claude_md_action = inj.action
        if inj.backup_path is not None:
            result.backups_created.append(inj.backup_path)

    return result


__all__ = [
    "BACKUP_SUFFIX",
    "SCHEMA_V0_2_FIELDS",
    "SCHEMA_V0_3_FIELDS",
    "SCHEMA_V0_4_FIELDS",
    "SchemaMigrationError",
    "WorkerSchemaGap",
    "MigrationPlan",
    "MigrationAnswers",
    "MigrationResult",
    "detect_worker_schema",
    "detect_company_schema",
    "plan",
    "execute",
]
