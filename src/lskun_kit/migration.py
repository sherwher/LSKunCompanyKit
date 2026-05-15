"""Migration tool — Local ↔ Vault backend 간 무결성 보장 이동.

ADR-0001 §검증 KPI 의 "Migration 무결성: 데이터 손실 0" 을 보장하기 위한 모듈.

흐름::

    1. plan(source, target) → MigrationPlan (워커 목록 / company.md 존재 여부)
    2. (dry_run=True 면 여기서 종료)
    3. 임시 디렉토리 ``<target_root>/_migrating-<unix>/`` 에 복사
    4. SHA-256 체크섬을 source / 임시 복사본 양쪽 계산해 일치 확인
    5. 워커 frontmatter 의 ``storage_backend`` 를 target backend 로 갱신
    6. target 의 정식 자리로 rename (atomic-ish swap)
    7. 실패 시 임시 디렉토리 정리 후 예외 전파

단방향 이동만 지원. 부분 / 점진 마이그레이션은 v0.2+.
"""

from __future__ import annotations

import hashlib
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from lskun_kit.adapters import frontmatter
from lskun_kit.adapters._markdown_tree import MarkdownTreeAdapter
from lskun_kit.errors import LSKunKitError


class MigrationError(LSKunKitError):
    """마이그레이션 실패. 메시지에 어느 단계에서 실패했는지 포함."""


@dataclass
class MigrationPlan:
    source_root: Path
    target_root: Path
    workers: list[str]
    has_company_file: bool
    source_backend: str
    target_backend: str
    files_total: int = 0
    bytes_total: int = 0

    def render(self) -> str:
        lines = [
            f"Migration plan: {self.source_backend} → {self.target_backend}",
            f"  source: {self.source_root}",
            f"  target: {self.target_root}",
            f"  workers: {len(self.workers)} ({', '.join(self.workers) or '-'})",
            f"  company.md: {'yes' if self.has_company_file else 'no'}",
            f"  files: {self.files_total}, bytes: {self.bytes_total}",
        ]
        return "\n".join(lines)


@dataclass
class MigrationResult:
    plan: MigrationPlan
    checksums_verified: int = 0
    rewritten_workers: list[str] = field(default_factory=list)


def plan(source: MarkdownTreeAdapter, target_root: Path | str, target_backend: str) -> MigrationPlan:
    """source 의 내용을 훑어 plan 을 만든다 — 디스크는 건드리지 않는다."""

    source_root = source.root
    target_root_path = Path(target_root).expanduser()

    workers = source.list_workers()
    has_company = (source_root / "company.md").exists()

    files_total = (1 if has_company else 0) + len(workers)
    bytes_total = 0
    if has_company:
        bytes_total += (source_root / "company.md").stat().st_size
    for w in workers:
        bytes_total += (source_root / "hired" / f"{w}.md").stat().st_size

    return MigrationPlan(
        source_root=source_root,
        target_root=target_root_path,
        workers=workers,
        has_company_file=has_company,
        source_backend=_infer_backend(source),
        target_backend=target_backend,
        files_total=files_total,
        bytes_total=bytes_total,
    )


def execute(
    source: MarkdownTreeAdapter,
    target_root: Path | str,
    target_backend: str,
    *,
    dry_run: bool = False,
) -> MigrationResult:
    """plan + 실제 이동. ``dry_run=True`` 면 plan 만 반환."""

    p = plan(source, target_root, target_backend)
    result = MigrationResult(plan=p)
    if dry_run:
        return result

    target_root_path = p.target_root
    if target_root_path.exists() and any(target_root_path.iterdir()):
        raise MigrationError(
            f"target root is not empty: {target_root_path}. "
            "remove it first or pick a different target."
        )
    target_root_path.mkdir(parents=True, exist_ok=True)

    staging = target_root_path.parent / f"_migrating-{int(time.time())}-{target_root_path.name}"
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "hired").mkdir(parents=True)

    try:
        # 1. company.md (있으면)
        if p.has_company_file:
            src = p.source_root / "company.md"
            dst = staging / "company.md"
            shutil.copy2(src, dst)
            _verify_checksum(src, dst)
            result.checksums_verified += 1

        # 2. 각 워커
        for name in p.workers:
            src = p.source_root / "hired" / f"{name}.md"
            dst = staging / "hired" / f"{name}.md"
            shutil.copy2(src, dst)
            _verify_checksum(src, dst)
            result.checksums_verified += 1

            # 3. frontmatter 의 storage_backend 갱신
            text = dst.read_text(encoding="utf-8")
            parsed = frontmatter.parse(text)
            if parsed.frontmatter.get("storage_backend") != target_backend:
                parsed.frontmatter["storage_backend"] = target_backend
                dst.write_text(
                    frontmatter.dump(parsed.frontmatter, parsed.body),
                    encoding="utf-8",
                )
                result.rewritten_workers.append(name)

        # 4. atomic-ish swap — staging 의 내용물을 target_root 로 이동
        _swap_into(staging, target_root_path)

    except Exception:
        # 실패 시 staging 정리. target_root 는 빈 채로 남는다.
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise

    return result


def _infer_backend(source: MarkdownTreeAdapter) -> str:
    # VaultAdapter 는 03_Companies/<co>/ 모양, LocalAdapter 는 그 외 (.company/ 관례)
    from lskun_kit.adapters.vault import COMPANIES_DIRNAME, VaultAdapter

    if isinstance(source, VaultAdapter):
        return "vault"
    if source.root.parent.name == COMPANIES_DIRNAME:
        return "vault"
    return "local"


def _verify_checksum(a: Path, b: Path) -> None:
    h_a = _sha256_of(a)
    h_b = _sha256_of(b)
    if h_a != h_b:
        raise MigrationError(
            f"checksum mismatch: {a} ({h_a[:12]}…) vs {b} ({h_b[:12]}…)"
        )


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _swap_into(staging: Path, target: Path) -> None:
    """staging 의 내용물을 target 안으로 옮긴다.

    target 은 plan 단계에서 빈 디렉토리임이 확인됨. rename 으로 옮긴다.
    """

    for item in staging.iterdir():
        dest = target / item.name
        if dest.exists():
            raise MigrationError(f"target slot already exists: {dest}")
        item.rename(dest)
    staging.rmdir()
