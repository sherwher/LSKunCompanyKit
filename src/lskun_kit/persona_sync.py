"""Persona body sync — ADR-0010.

메타 워커 (CPO / HR Lead) 의 ``hired/<name>.md`` body 본문을 plugin 의 최신
``templates/<name>.md`` 본문으로 sync. frontmatter (사용자 personalize) 와
``## Project History`` (자동 누적 reflection) 는 **절대 보존**.

원칙 (불변):
    - history 한 줄도 변경 금지
    - frontmatter 기존 키 절대 덮어쓰기 금지
    - 변경 전 ``<file>.lskun-pre-sync.bak`` 자동 백업 (이미 있으면 timestamp 추가)
    - ``persona_synced_from`` / ``persona_synced_at`` 박제는 변경 발생 시점에만 갱신
    - dry-run 가능 (plan only)
    - idempotent — 이미 sync 된 상태에서 재실행해도 안전 (body 동일 시 백업 skip + provenance 만 갱신)
"""

from __future__ import annotations

import difflib
import shutil
import time
from dataclasses import dataclass, field
from datetime import date as date_cls
from pathlib import Path
from typing import Iterable

from lskun_kit.adapters import frontmatter as fm
from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.errors import LSKunKitError

#: ADR-0010 §1 — sync 대상 메타 워커. 일반 워커는 sync 대상이 아님.
META_WORKER_NAMES = ("cpo", "hr-lead")

#: legacy heading — ADR-0014 이전 사용자 자산. migrate-schema 가 ARCHIVED_HEADING
#: 로 rename. sync-persona 는 양쪽 모두 보존 대상으로 인식한다.
LEGACY_HISTORY_HEADING = "## Project History"
ARCHIVED_HISTORY_HEADING = "## Archived History (pre-0.18)"
#: 호환성 alias — 기존 코드 / 외부 참조용. 신규 코드는 ``LEGACY_HISTORY_HEADING`` 사용.
HISTORY_HEADING = LEGACY_HISTORY_HEADING

BACKUP_SUFFIX = ".lskun-pre-sync.bak"

#: ADR-0010 §3 — provenance 필드 키.
PROV_FROM = "persona_synced_from"
PROV_AT = "persona_synced_at"


class PersonaSyncError(LSKunKitError):
    """Persona sync 실패."""


def _templates_dir() -> Path:
    """본 패키지의 ``templates/`` 절대 경로."""
    return Path(__file__).resolve().parent / "templates"


def _split_body_history(body: str) -> tuple[str, str]:
    """body 를 (pre_history, history_section) 으로 분리.

    ADR-0014 (2026-05-22) — 두 heading 모두 보존 대상으로 인식한다:
        - ``## Project History`` (legacy, 0.17.0 이전)
        - ``## Archived History (pre-0.18)`` (migrate-schema 가 rename 한 결과)

    매칭 규칙 (substring 오탐 방지, hr-lead.md 손상 사건 2026-05-26 시정):
        - heading 은 **줄 시작 (`^## ...$`)** 으로만 인식.
        - **fenced code block** (```` ``` ```` / ``` ~~~ ```) 내부의 줄은 무시.
        - inline backtick 안의 ``"## Project History"`` 같은 인용은 줄 시작이
          아니므로 자연 배제 (코드 인용은 항상 inline backtick 또는 fenced block 안).

    어느 쪽도 없으면 history_section 은 빈 문자열, pre_history 가 body 전체.
    둘 다 있는 비정상 케이스에는 먼저 등장하는 heading 을 기준으로 split.
    """

    candidates: list[int] = []
    in_fence = False
    fence_marker: str | None = None
    char_pos = 0  # 줄 시작 시점의 char index

    for line in body.splitlines(keepends=True):
        stripped = line.lstrip()
        # fenced code block 진입/탈출 (``` 또는 ~~~ 3개 이상).
        if not in_fence:
            for marker in ("```", "~~~"):
                if stripped.startswith(marker):
                    in_fence = True
                    fence_marker = marker
                    break
        else:
            if fence_marker is not None and stripped.startswith(fence_marker):
                in_fence = False
                fence_marker = None

        if not in_fence:
            # 본 줄이 heading 줄 자체인지 확인 (## 다음에 정확히 heading 텍스트).
            line_no_nl = line.rstrip("\n").rstrip("\r")
            for heading in (LEGACY_HISTORY_HEADING, ARCHIVED_HISTORY_HEADING):
                if line_no_nl == heading or line_no_nl.startswith(heading + " "):
                    candidates.append(char_pos)
                    break

        char_pos += len(line)

    if not candidates:
        return body, ""
    idx = min(candidates)
    return body[:idx], body[idx:]


def _read_template_body(name: str) -> str:
    """plugin 의 templates/<name>.md 의 body (frontmatter 제외, history 제외) 반환."""
    tpl_path = _templates_dir() / f"{name}.md"
    if not tpl_path.exists():
        raise PersonaSyncError(
            f"plugin template not found: {tpl_path}. "
            f"sync 대상은 {list(META_WORKER_NAMES)} 만 지원한다."
        )
    parsed = fm.parse(tpl_path.read_text(encoding="utf-8"))
    pre_history, _ = _split_body_history(parsed.body)
    return pre_history.rstrip() + "\n"


def _read_worker_parts(path: Path) -> tuple[dict[str, str], str, str]:
    """워커 파일을 (frontmatter, pre_history_body, history_section) 으로 반환."""
    parsed = fm.parse(path.read_text(encoding="utf-8"))
    pre_history, history = _split_body_history(parsed.body)
    return dict(parsed.frontmatter), pre_history.rstrip() + "\n", history


@dataclass(frozen=True)
class WorkerSyncDelta:
    """단일 메타 워커의 sync 상태."""

    name: str
    path: Path
    body_in_sync: bool  # 현재 body 가 template 와 동일한가
    provenance_in_sync: bool  # persona_synced_from 가 현재 plugin 버전인가
    current_synced_from: str | None
    current_synced_at: str | None
    target_synced_from: str  # "lskun-kit@<version>"

    @property
    def needs_action(self) -> bool:
        return not (self.body_in_sync and self.provenance_in_sync)

    def diff_text(self, current_body: str, target_body: str) -> str:
        """body 의 unified diff. ``--plan`` 출력용."""
        return "".join(difflib.unified_diff(
            current_body.splitlines(keepends=True),
            target_body.splitlines(keepends=True),
            fromfile=f"a/{self.name}.md (current)",
            tofile=f"b/{self.name}.md (template)",
        ))


@dataclass
class SyncPlan:
    """``/lskun-kit:sync-persona`` 의 실행 전 계획."""

    backend: str
    company_root: Path
    plugin_version: str
    deltas: list[WorkerSyncDelta] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def is_no_op(self) -> bool:
        return all(not d.needs_action for d in self.deltas)

    def render(self) -> str:
        lines = [
            "Persona Sync Plan",
            "================================================",
            f"backend          : {self.backend}",
            f"company root     : {self.company_root}",
            f"plugin version   : {self.plugin_version}",
            "",
        ]
        for d in self.deltas:
            lines.append(f"[{d.name}] {d.path}")
            lines.append(f"  body          : {'OK' if d.body_in_sync else 'STALE — needs sync'}")
            lines.append(
                f"  provenance    : "
                + ("OK" if d.provenance_in_sync
                   else f"missing/stale (current={d.current_synced_from!r}, target={d.target_synced_from!r})")
            )
            lines.append(f"  action        : {'no-op' if not d.needs_action else 'sync'}")
        for n in self.notes:
            lines.append(f"note             : {n}")
        if self.is_no_op:
            lines.append("")
            lines.append("결과: sync 불필요 — 모든 메타 워커가 현재 plugin 버전과 일치.")
        return "\n".join(lines) + "\n"


@dataclass
class WorkerSyncResult:
    name: str
    path: Path
    body_updated: bool
    provenance_updated: bool
    backup_path: Path | None


@dataclass
class SyncResult:
    plan: SyncPlan
    per_worker: list[WorkerSyncResult] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            "Persona Sync Result",
            "================================================",
        ]
        for r in self.per_worker:
            action_parts = []
            if r.body_updated:
                action_parts.append("body")
            if r.provenance_updated:
                action_parts.append("provenance")
            action = ", ".join(action_parts) if action_parts else "no-op"
            lines.append(f"[{r.name}] {action}")
            if r.backup_path is not None:
                lines.append(f"  backup        : {r.backup_path}")
        return "\n".join(lines) + "\n"


def _target_version_string(plugin_version: str) -> str:
    return f"lskun-kit@{plugin_version}"


def _backup_file(path: Path) -> Path:
    bak = path.with_suffix(path.suffix + BACKUP_SUFFIX)
    if bak.exists():
        bak = path.with_suffix(path.suffix + f"{BACKUP_SUFFIX}.{int(time.time())}")
    shutil.copy2(path, bak)
    return bak


def plan(
    adapter: StorageAdapter,
    plugin_version: str,
    worker_names: Iterable[str] | None = None,
) -> SyncPlan:
    """sync 계획 작성. 어떤 파일도 변경하지 않는다.

    Args:
        adapter: 활성 backend adapter
        plugin_version: 현재 plugin 버전 (예: "0.8.0-dev")
        worker_names: 대상 워커 이름 (default = META_WORKER_NAMES)
    """
    names = tuple(worker_names) if worker_names else META_WORKER_NAMES
    target = _target_version_string(plugin_version)
    # adapter 가 MarkdownTreeAdapter 면 root 가 있음. 아니면 path 추적이 어려우니 raise.
    if not hasattr(adapter, "root"):
        raise PersonaSyncError(
            f"adapter {type(adapter).__name__} 는 root 경로를 노출하지 않아 "
            f"sync 가 불가능하다."
        )
    company_root = Path(getattr(adapter, "root"))
    backend = "vault" if "03_Companies" in str(company_root) else "local"

    deltas: list[WorkerSyncDelta] = []
    notes: list[str] = []
    for name in names:
        if name not in META_WORKER_NAMES:
            notes.append(f"warn: {name!r} 는 메타 워커가 아니어서 sync 대상이 아님. skip.")
            continue
        worker_path = company_root / "hired" / f"{name}.md"
        if not worker_path.exists():
            notes.append(f"warn: {worker_path} 가 존재하지 않음. /lskun-kit:init 권장. skip.")
            continue
        target_body = _read_template_body(name)
        co_fm, co_pre, _co_hist = _read_worker_parts(worker_path)
        body_in_sync = co_pre.rstrip() == target_body.rstrip()
        current_from = co_fm.get(PROV_FROM)
        current_at = co_fm.get(PROV_AT)
        provenance_in_sync = current_from == target
        deltas.append(WorkerSyncDelta(
            name=name,
            path=worker_path,
            body_in_sync=body_in_sync,
            provenance_in_sync=provenance_in_sync,
            current_synced_from=current_from if isinstance(current_from, str) else None,
            current_synced_at=current_at if isinstance(current_at, str) else None,
            target_synced_from=target,
        ))
    return SyncPlan(
        backend=backend,
        company_root=company_root,
        plugin_version=plugin_version,
        deltas=deltas,
        notes=notes,
    )


def diff_text_for(p: SyncPlan, name: str) -> str:
    """plan 의 특정 워커의 body diff (사용자에게 표시용)."""
    delta = next((d for d in p.deltas if d.name == name), None)
    if delta is None:
        return ""
    target_body = _read_template_body(name)
    _co_fm, co_pre, _co_hist = _read_worker_parts(delta.path)
    return delta.diff_text(co_pre, target_body)


def execute(
    adapter: StorageAdapter,
    p: SyncPlan,
    today: date_cls | None = None,
) -> SyncResult:
    """실제 sync 수행. plan 의 각 delta 를 처리."""
    result = SyncResult(plan=p)
    if p.is_no_op:
        return result
    today_str = (today or date_cls.today()).isoformat()
    for delta in p.deltas:
        if not delta.needs_action:
            result.per_worker.append(WorkerSyncResult(
                name=delta.name, path=delta.path,
                body_updated=False, provenance_updated=False, backup_path=None,
            ))
            continue
        target_body = _read_template_body(delta.name)
        co_fm, co_pre, co_hist = _read_worker_parts(delta.path)
        body_will_change = co_pre.rstrip() != target_body.rstrip()
        provenance_will_change = (
            co_fm.get(PROV_FROM) != delta.target_synced_from
            or PROV_AT not in co_fm
        )
        if not (body_will_change or provenance_will_change):
            result.per_worker.append(WorkerSyncResult(
                name=delta.name, path=delta.path,
                body_updated=False, provenance_updated=False, backup_path=None,
            ))
            continue
        # 변경 발생 — 백업
        bak = _backup_file(delta.path)
        # body 재구성. ADR-0014 — reflection 폐기로 빈 history fallback 박제하지 않음.
        # co_hist 는 두 heading (legacy / archived) 모두 양쪽 포착 (위 _split_body_history 참고).
        new_pre = target_body.rstrip() + "\n\n"
        if co_hist:
            new_body = new_pre + co_hist
        else:
            new_body = target_body.rstrip() + "\n"
        # frontmatter 갱신 (provenance 만)
        new_fm = dict(co_fm)
        new_fm[PROV_FROM] = delta.target_synced_from
        new_fm[PROV_AT] = today_str
        new_text = fm.dump(new_fm, new_body)
        delta.path.write_text(new_text, encoding="utf-8")
        result.per_worker.append(WorkerSyncResult(
            name=delta.name, path=delta.path,
            body_updated=body_will_change,
            provenance_updated=provenance_will_change,
            backup_path=bak,
        ))
    return result


# --- P107 (ADR-0018 후보): 백업 청소 (사용자 명시 옵션) ---


@dataclass(frozen=True)
class BackupCleanupPlan:
    """단일 메타 워커의 백업 청소 계획 (dry-run + execute 공통).

    P107 — 누적 백업 파일 (``<name>.md.lskun-pre-sync.bak[.timestamp]``) 을
    keep 개수만큼 최신순으로 남기고 나머지 삭제. 사용자 명시 옵션이며 자동
    청소 X (역사 자산 불변 원칙, ADR-0015 정신).
    """

    name: str
    kept: list[Path]
    deleted: list[Path]

    @property
    def has_action(self) -> bool:
        return bool(self.deleted)


def _list_backup_files(hired_dir: Path, name: str) -> list[Path]:
    """``hired/<name>.md.lskun-pre-sync.bak*`` 목록을 최신순 (mtime desc) 반환.

    suffix 없는 ``.bak`` 도 timestamp 무한대 (== 가장 최근) 로 간주하지 않고
    파일시스템 mtime 으로 정렬. atomic 순서가 깨지더라도 사용자가 만든 마지막
    수동 백업이 의도치 않게 삭제되는 사고 방지.
    """

    pattern = f"{name}.md{BACKUP_SUFFIX}"
    candidates: list[Path] = []
    if not hired_dir.exists():
        return candidates
    for p in hired_dir.iterdir():
        if not p.is_file():
            continue
        if p.name == pattern or p.name.startswith(pattern + "."):
            candidates.append(p)
    # 최신순 (mtime desc)
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates


def plan_cleanup_backups(
    adapter: StorageAdapter,
    keep: int = 3,
    worker_names: Iterable[str] | None = None,
) -> list[BackupCleanupPlan]:
    """백업 파일 청소 계획 작성. 어떤 파일도 변경하지 않는다.

    Args:
        adapter: 활성 backend adapter (root 노출 필수)
        keep: 메타 워커별 보존 개수 (기본 3, 최소 0)
        worker_names: 대상 워커 (default = META_WORKER_NAMES)

    Returns:
        메타 워커별 청소 계획 리스트.
    """

    if keep < 0:
        raise PersonaSyncError(f"keep must be >= 0, got {keep}")
    if not hasattr(adapter, "root"):
        raise PersonaSyncError(
            f"adapter {type(adapter).__name__} 는 root 경로를 노출하지 않아 "
            f"백업 청소가 불가능하다."
        )
    company_root = Path(getattr(adapter, "root"))
    hired_dir = company_root / "hired"
    names = tuple(worker_names) if worker_names else META_WORKER_NAMES

    plans: list[BackupCleanupPlan] = []
    for name in names:
        if name not in META_WORKER_NAMES:
            continue
        backups = _list_backup_files(hired_dir, name)
        kept = backups[:keep]
        deleted = backups[keep:]
        plans.append(BackupCleanupPlan(name=name, kept=kept, deleted=deleted))
    return plans


def execute_cleanup_backups(plans: list[BackupCleanupPlan]) -> list[BackupCleanupPlan]:
    """plan 의 ``deleted`` 항목을 실제 unlink.

    원자성 보장 X — 중간 실패 시 일부 삭제된 상태로 남음. 사용자 명시 명령이며
    재실행 가능 (idempotent: 두 번째 실행 시 이미 사라진 파일은 plan 에 안 들어옴).
    """

    for p in plans:
        for path in p.deleted:
            try:
                path.unlink()
            except FileNotFoundError:
                # 동시성으로 이미 사라진 경우 — 무시 (idempotent)
                pass
    return plans


def render_cleanup_report(plans: list[BackupCleanupPlan], dry_run: bool) -> str:
    lines = [
        "Persona Backup Cleanup " + ("Plan" if dry_run else "Result"),
        "================================================",
    ]
    total_deleted = 0
    for p in plans:
        lines.append(f"[{p.name}]")
        lines.append(f"  kept    : {len(p.kept)}")
        for k in p.kept:
            lines.append(f"    - {k.name}")
        lines.append(f"  deleted : {len(p.deleted)}")
        for d in p.deleted:
            lines.append(f"    - {d.name}")
        total_deleted += len(p.deleted)
    lines.append("")
    if dry_run:
        lines.append(f"총 삭제 예정: {total_deleted}개. --execute 로 실제 삭제.")
    else:
        lines.append(f"총 삭제 완료: {total_deleted}개.")
    return "\n".join(lines) + "\n"


__all__ = [
    "META_WORKER_NAMES",
    "PROV_FROM",
    "PROV_AT",
    "BACKUP_SUFFIX",
    "PersonaSyncError",
    "WorkerSyncDelta",
    "SyncPlan",
    "SyncResult",
    "WorkerSyncResult",
    "BackupCleanupPlan",
    "plan",
    "execute",
    "diff_text_for",
    "plan_cleanup_backups",
    "execute_cleanup_backups",
    "render_cleanup_report",
]
