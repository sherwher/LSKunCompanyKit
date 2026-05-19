"""조직도 view — ADR-0010 §4.

회사의 ``hired/`` 디렉토리를 스캔해 표 형태 출력. **read-only** — 파일 수정 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lskun_kit.adapters import frontmatter as fm
from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.errors import LSKunKitError
from lskun_kit.models import REQUIRED_WORKER_FIELDS
from lskun_kit.persona_sync import META_WORKER_NAMES, PROV_AT, PROV_FROM


class OrgError(LSKunKitError):
    """조직도 조회 실패."""


@dataclass(frozen=True)
class OrgEntry:
    """조직도 한 줄."""

    name: str
    role: str
    display_name: str
    domain: str
    model: str | None
    history_count: int
    persona_synced_from: str | None
    persona_synced_at: str | None
    archived: bool = False

    @property
    def category(self) -> str:
        if self.name == "cpo":
            return "CPO"
        if self.name == "hr-lead":
            return "HR"
        return "Worker"


@dataclass
class OrgReport:
    backend: str
    company_root: Path
    company_name: str
    company_domain: str
    entries: list[OrgEntry] = field(default_factory=list)
    archived_entries: list[OrgEntry] = field(default_factory=list)

    def render(self, include_archived: bool = False) -> str:
        lines = [
            "LSKunCompanyKit org",
            "================================================",
            f"회사: {self.company_name} (domain={self.company_domain})",
            f"backend: {self.backend} → {self.company_root}",
            "",
        ]
        if not self.entries:
            lines.append("(hired 워커 0명)")
            return "\n".join(lines) + "\n"
        # 정렬: CPO → HR → Worker (이름 알파벳)
        order = {"CPO": 0, "HR": 1, "Worker": 2}
        sorted_entries = sorted(
            self.entries, key=lambda e: (order[e.category], e.name)
        )
        # 컬럼 폭 계산
        w_name = max(8, max(len(e.name) for e in sorted_entries))
        w_disp = max(6, max(len(e.display_name) for e in sorted_entries))
        w_role = max(8, max(len(e.role) for e in sorted_entries))
        for e in sorted_entries:
            model = e.model or "default"
            lines.append(
                f"[{e.category:<6}] {e.name:<{w_name}}  {e.display_name:<{w_disp}}  "
                f"({e.role:<{w_role}}, model={model:<8}, domain={e.domain}, "
                f"history={e.history_count})"
            )
        # 요약
        cpo_n = sum(1 for e in sorted_entries if e.category == "CPO")
        hr_n = sum(1 for e in sorted_entries if e.category == "HR")
        worker_n = sum(1 for e in sorted_entries if e.category == "Worker")
        domain_counts: dict[str, int] = {}
        for e in sorted_entries:
            domain_counts[e.domain] = domain_counts.get(e.domain, 0) + 1
        lines.append("")
        lines.append(
            f"총: {len(sorted_entries)}명 "
            f"(CPO {cpo_n}, HR {hr_n}, Worker {worker_n})"
        )
        domain_summary = ", ".join(
            f"{d} {c}" for d, c in sorted(domain_counts.items())
        )
        lines.append(f"도메인별: {domain_summary}")
        # Persona sync 요약
        sync_bits = []
        for e in sorted_entries:
            if e.name in META_WORKER_NAMES:
                src = e.persona_synced_from or "unsynced"
                at = e.persona_synced_at or "?"
                sync_bits.append(f"{e.name}={src} ({at})")
        if sync_bits:
            lines.append(f"Persona sync: {', '.join(sync_bits)}")
        if include_archived and self.archived_entries:
            lines.append("")
            lines.append("--- archived ---")
            for e in sorted(self.archived_entries, key=lambda e: e.name):
                model = e.model or "default"
                lines.append(
                    f"[archive] {e.name}  {e.display_name}  "
                    f"({e.role}, model={model}, domain={e.domain})"
                )
        return "\n".join(lines) + "\n"


def _count_history(body: str) -> int:
    """``- `` 로 시작하는 줄 수를 history entry 로 카운트."""
    if "## Project History" not in body:
        return 0
    section = body.split("## Project History", 1)[1]
    return sum(
        1 for line in section.splitlines()
        if line.lstrip().startswith("- ") and "first-pass" in line
    )


def _read_company_meta(company_md_path: Path) -> tuple[str, str]:
    """company.md 에서 name + domain 추출."""
    if not company_md_path.exists():
        return "(unknown)", "(unknown)"
    parsed = fm.parse(company_md_path.read_text(encoding="utf-8"))
    return (
        str(parsed.frontmatter.get("name", "(unknown)")),
        str(parsed.frontmatter.get("domain", "(unknown)")),
    )


def _read_entry(path: Path, archived: bool = False) -> OrgEntry | None:
    """단일 워커 파일을 OrgEntry 로. schema 위반 시 None (호출자가 warn 처리)."""
    if not path.is_file() or path.name.startswith("."):
        return None
    try:
        parsed = fm.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    f = parsed.frontmatter
    if any(k not in f for k in REQUIRED_WORKER_FIELDS):
        return None
    return OrgEntry(
        name=str(f["name"]),
        role=str(f["role"]),
        display_name=str(f["display_name"]),
        domain=str(f["domain"]),
        model=f.get("model"),
        history_count=_count_history(parsed.body),
        persona_synced_from=f.get(PROV_FROM),
        persona_synced_at=f.get(PROV_AT),
        archived=archived,
    )


def build(adapter: StorageAdapter, include_archived: bool = False) -> OrgReport:
    """조직도 데이터 빌드. **read-only**."""
    if not hasattr(adapter, "root"):
        raise OrgError(
            f"adapter {type(adapter).__name__} 는 root 경로를 노출하지 않아 "
            f"조직도 조회가 불가능하다."
        )
    company_root = Path(getattr(adapter, "root"))
    backend = "vault" if "03_Companies" in str(company_root) else "local"
    co_name, co_domain = _read_company_meta(company_root / "company.md")
    report = OrgReport(
        backend=backend,
        company_root=company_root,
        company_name=co_name,
        company_domain=co_domain,
    )
    hired_dir = company_root / "hired"
    if hired_dir.exists():
        for p in sorted(hired_dir.glob("*.md")):
            if p.suffix != ".md" or p.name.endswith(".bak"):
                continue
            entry = _read_entry(p)
            if entry is not None:
                report.entries.append(entry)
    if include_archived:
        archived_dir = company_root / "archived"
        if archived_dir.exists():
            for p in sorted(archived_dir.glob("*.md")):
                if p.suffix != ".md" or p.name.endswith(".bak"):
                    continue
                entry = _read_entry(p, archived=True)
                if entry is not None:
                    report.archived_entries.append(entry)
    return report


__all__ = ["OrgEntry", "OrgReport", "OrgError", "build"]
