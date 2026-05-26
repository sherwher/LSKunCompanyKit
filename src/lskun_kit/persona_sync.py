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

    어느 쪽도 없으면 history_section 은 빈 문자열, pre_history 가 body 전체.
    둘 다 있는 비정상 케이스에는 먼저 등장하는 heading 을 기준으로 split
    (그 이후의 텍스트는 전부 history_section 에 포함되어 보존).
    """

    candidates = []
    for heading in (LEGACY_HISTORY_HEADING, ARCHIVED_HISTORY_HEADING):
        if heading in body:
            candidates.append(body.index(heading))
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


__all__ = [
    "META_WORKER_NAMES",
    "PROV_FROM",
    "PROV_AT",
    "PersonaSyncError",
    "WorkerSyncDelta",
    "SyncPlan",
    "SyncResult",
    "WorkerSyncResult",
    "plan",
    "execute",
    "diff_text_for",
]
