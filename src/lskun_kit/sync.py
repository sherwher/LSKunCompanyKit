"""Sync — Local SSOT ↔ 외부 mirror 파일시스템 복사 (ADR-0015 결정 5).

ADR-0015 (2026-05-22) — Vault 통합은 plugin core 가 직접 참조하지 않고
``/LSKunCompanyKit:sync-in`` / ``/LSKunCompanyKit:sync-out`` 명령의 파일시스템
복사로만 수행한다. Vault 가 Obsidian / Notion local cache / Dropbox / 외장
디스크 / git submodule 무엇이든 plugin 은 모름 — 단지 경로 1개에 read/write
가능하면 됨.

방향:
    sync-in:  <source>           → ~/.lskun-companies/<name>/  (local 백업 생성)
    sync-out: ~/.lskun-companies/<name>/ → <target>            (target 백업 생성)

충돌 정책 (결정 5-B):
    - target/local 덮어쓰기 (양방향 merge 미도입)
    - 사용자 confirm 강제 (ConfirmRequired — 옵션 B 패턴)
    - 백업 자동 생성 (결정 5-E)

백업 위치 (결정 5-E):
    ~/.lskun-companies/.backups/<name>/<timestamp>/
    - timestamp 포맷: YYYYMMDD-HHMMSS
    - 회사 SSOT 디렉토리 외부 통합 위치
    - plugin 자동 삭제 / rotation 없음 (사용자 책임)

ADR-0009 정합: ``shutil.copytree`` / ``shutil.copy2`` 만 사용, 외부 SDK 0건.
ADR-0015 폐기 목록:
    - 양방향 자동 merge ❌
    - 자동 스케줄링 (cron / hook 자동) ❌
    - 회사 SSOT 의 git 자동 commit ❌
    - 백업 자동 삭제 / rotation ❌
    - 회사 SSOT 디렉토리 안에 backup 박제 ❌
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from lskun_kit.errors import ConfirmRequired
from lskun_kit.paths import backup_root, company_root, validate_company_name


@dataclass
class SyncResult:
    """sync-in / sync-out 결과 — slash command 가 사용자에게 출력할 진단."""

    direction: str  # "in" | "out"
    company_name: str
    source: Path
    target: Path
    backup_path: Path | None
    files_copied: int
    bytes_copied: int
    notes: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            f"LSKunCompanyKit sync-{self.direction}",
            "================================================",
            f"company       : {self.company_name}",
            f"source        : {self.source}",
            f"target        : {self.target}",
            f"backup        : {self.backup_path if self.backup_path else '(none)'}",
            f"files copied  : {self.files_copied}",
            f"bytes copied  : {self.bytes_copied}",
        ]
        for note in self.notes:
            lines.append(f"note          : {note}")
        return "\n".join(lines) + "\n"


def _make_timestamp() -> str:
    """결정 5-E — ``YYYYMMDD-HHMMSS`` 정렬 가능 timestamp."""
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _walk_size(root: Path) -> tuple[int, int]:
    """root 의 파일 수 + 총 byte. 디렉토리는 카운트 안 함."""
    files = 0
    total = 0
    if not root.exists():
        return 0, 0
    for p in root.rglob("*"):
        if p.is_file():
            files += 1
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return files, total


def _render_confirm_prompt(
    direction: str, company_name: str, source: Path, target: Path,
    backup_path: Path, target_exists: bool,
) -> str:
    """ADR-0015 결정 5-B 의 사용자 confirm 메시지."""

    if direction == "in":
        action = "외부 mirror → Local SSOT"
    else:
        action = "Local SSOT → 외부 mirror"
    lines = [
        f"sync-{direction}: {action}",
        f"  company : {company_name}",
        f"  source  : {source}",
        f"  target  : {target}",
    ]
    if target_exists:
        lines.append(
            f"  ⚠️ target 기존 내용은 덮어쓰여집니다 (백업: {backup_path})"
        )
    else:
        lines.append("  (target 신규 생성)")
    lines.append("")
    lines.append("진행하시겠습니까? [y/N]")
    return "\n".join(lines)


def _backup_target(target: Path, backup_dest: Path) -> None:
    """target 디렉토리를 backup_dest 로 통째 복사 (sync 전 안전망)."""

    backup_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(target, backup_dest)


def _copy_tree(source: Path, target: Path) -> tuple[int, int]:
    """source → target 통째 복사. target 부재 가정 (호출 전 정리됨).

    Returns:
        (files_copied, bytes_copied).
    """

    if not source.exists():
        raise ValueError(f"sync source does not exist: {source}")
    if not source.is_dir():
        raise ValueError(f"sync source is not a directory: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    return _walk_size(target)


def sync_in(
    company_name: str,
    source: Path | str,
    *,
    confirmed: bool = False,
    today_stamp: str | None = None,
) -> SyncResult:
    """외부 mirror → ``~/.lskun-companies/<name>/`` 복사.

    Args:
        company_name: 회사 이름. ``paths.validate_company_name`` 검증.
        source: 외부 mirror 경로 (예: ``~/vault/03_Companies/LSKun``).
        confirmed: 사용자 confirm 완료 신호.
        today_stamp: 테스트용 timestamp 주입.

    Raises:
        ConfirmRequired: confirmed=False 일 때 (옵션 B).
        ValueError: source 부재 / invalid name.
    """

    validate_company_name(company_name)
    src = Path(source).expanduser().resolve()
    if not src.exists():
        raise ValueError(f"sync-in source does not exist: {src}")
    if not src.is_dir():
        raise ValueError(f"sync-in source is not a directory: {src}")

    co_root = company_root(company_name)
    stamp = today_stamp or _make_timestamp()
    backup_dest = backup_root(company_name) / stamp
    target_exists = co_root.exists()

    if not confirmed:
        raise ConfirmRequired(
            kind="sync_overwrite",
            prompt=_render_confirm_prompt(
                "in", company_name, src, co_root, backup_dest, target_exists,
            ),
            context={
                "direction": "in",
                "company_name": company_name,
                "source": str(src),
                "target": str(co_root),
                "backup_path": str(backup_dest) if target_exists else None,
                "target_exists": target_exists,
            },
        )

    backup_path: Path | None = None
    if target_exists:
        _backup_target(co_root, backup_dest)
        backup_path = backup_dest
        shutil.rmtree(co_root)

    files, total = _copy_tree(src, co_root)

    return SyncResult(
        direction="in",
        company_name=company_name,
        source=src,
        target=co_root,
        backup_path=backup_path,
        files_copied=files,
        bytes_copied=total,
        notes=(
            [f"기존 local 백업: {backup_path}"] if backup_path else
            ["target 신규 생성 (이전 local 없음)"]
        ),
    )


def sync_out(
    company_name: str,
    target: Path | str,
    *,
    confirmed: bool = False,
    target_backup_root: Path | str | None = None,
    today_stamp: str | None = None,
) -> SyncResult:
    """``~/.lskun-companies/<name>/`` → 외부 mirror 복사.

    Args:
        company_name: 회사 이름.
        target: 외부 mirror 경로.
        confirmed: 사용자 confirm 완료 신호.
        target_backup_root: target 백업 위치 override (기본: target 의 sibling
            ``<target>.backup-<timestamp>/``). target 측에 별도 저장 (결정 5-B).
        today_stamp: 테스트용 timestamp 주입.

    Raises:
        ConfirmRequired: confirmed=False 일 때.
        ValueError: source (local SSOT) 부재 / invalid name.
    """

    validate_company_name(company_name)
    co_root = company_root(company_name)
    if not co_root.exists():
        raise ValueError(
            f"sync-out source does not exist: {co_root} "
            f"(회사가 local SSOT 에 없음. /lskun-kit:init 먼저 실행)"
        )

    tgt = Path(target).expanduser().resolve()
    stamp = today_stamp or _make_timestamp()
    target_exists = tgt.exists()

    # target 백업은 target 측 sibling 에 (결정 5-B — target 측 별도 위치)
    if target_backup_root is None:
        backup_dest = tgt.parent / f"{tgt.name}.lskun-backup-{stamp}"
    else:
        backup_dest = Path(target_backup_root).expanduser() / stamp

    if not confirmed:
        raise ConfirmRequired(
            kind="sync_overwrite",
            prompt=_render_confirm_prompt(
                "out", company_name, co_root, tgt, backup_dest, target_exists,
            ),
            context={
                "direction": "out",
                "company_name": company_name,
                "source": str(co_root),
                "target": str(tgt),
                "backup_path": str(backup_dest) if target_exists else None,
                "target_exists": target_exists,
            },
        )

    backup_path: Path | None = None
    if target_exists:
        _backup_target(tgt, backup_dest)
        backup_path = backup_dest
        shutil.rmtree(tgt)

    files, total = _copy_tree(co_root, tgt)

    return SyncResult(
        direction="out",
        company_name=company_name,
        source=co_root,
        target=tgt,
        backup_path=backup_path,
        files_copied=files,
        bytes_copied=total,
        notes=(
            [f"기존 target 백업: {backup_path}"] if backup_path else
            ["target 신규 생성 (이전 target 없음)"]
        ),
    )


__all__ = [
    "SyncResult",
    "sync_in",
    "sync_out",
]
