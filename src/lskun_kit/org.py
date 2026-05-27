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
    """조직도 한 줄.

    ADR-0014 (2026-05-22) — ``history_count`` 필드 제거. 워커 = 채용 시 완성형
    이므로 history 누적 개념 없음. hired_at (채용 시점) 으로 시간축 교체.
    """

    name: str
    role: str
    display_name: str
    domain: str
    model: str | None
    hired_at: str
    persona_synced_from: str | None
    persona_synced_at: str | None
    # ADR-0019 — archived 필드는 하위호환 위해 유지하되 항상 False.
    # 외부 호출자가 e.archived 접근 시 AttributeError 안 나도록.
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
    """ADR-0019 (2026-05-27) — archived_entries 필드 제거. archive 메커니즘 폐기.

    P109-A (2026-05-27) — ``usage_by_worker`` 필드 추가. ``--usage`` flag 일 때만
    audit_view 로 집계, 평소엔 ``None``. 평가 X / 점수 X / 단순 view (ADR-0006 정신).
    """

    backend: str
    company_root: Path
    company_name: str
    company_domain: str
    entries: list[OrgEntry] = field(default_factory=list)
    usage_by_worker: dict[str, "WorkerUsage"] | None = None  # type: ignore[name-defined]

    #: ADR-0013 — 조직도 stable format. 동적 padding 폐지, markdown table 단일 SSOT.
    #: ADR-0014 — History 컬럼 제거 → Hired (채용 시점) 로 교체.
    _TABLE_HEADER = "| Cat    | Name | Display | Role | Domain | Model | Hired |"
    _TABLE_SEP = "|--------|------|---------|------|--------|-------|-------|"

    def render(self, compact: bool = False, show_usage: bool = False) -> str:
        """조직도 출력. ``show_usage=True`` 시 audit 집계 컬럼 추가 (P109-A).

        - ``show_usage`` 가 True 인데 ``usage_by_worker`` 가 None 이면 ⚠️ note 1줄
        - compact format 은 1줄 끝에 ``· <N> dispatches · last=<YYYY-MM-DD>`` append
        - table format 은 컬럼 2개 (``Dispatches`` / ``Last seen``) 추가
        """

        usage_active = bool(show_usage and self.usage_by_worker is not None)
        lines = [
            "LSKunCompanyKit org",
            "================================================",
            f"회사: {self.company_name} (domain={self.company_domain})",
            f"backend: {self.backend} → {self.company_root}",
            "",
        ]
        if show_usage and self.usage_by_worker is None:
            lines.append(
                "(--usage 요청됐으나 audit_view 집계가 없음. org.build(with_usage=True) 로 빌드 필요)"
            )
            lines.append("")
        if not self.entries:
            lines.append("(hired 워커 0명)")
            return "\n".join(lines) + "\n"
        # 정렬: CPO → HR → Worker (이름 알파벳)
        order = {"CPO": 0, "HR": 1, "Worker": 2}
        sorted_entries = sorted(
            self.entries, key=lambda e: (order[e.category], e.name)
        )
        if compact:
            # ADR-0013 add-on — compact 1줄. role==name 인 경우 role 생략 (중복 제거).
            # ADR-0014 — h=N 제거, hired_at 로 교체.
            for e in sorted_entries:
                model = e.model or "default"
                role_part = "" if e.role == e.name else f" · {e.role}"
                line = (
                    f"[{e.category[0]}] {e.name} ({e.display_name})"
                    f"{role_part} · {e.domain} · {model} · hired={e.hired_at}"
                )
                if usage_active:
                    u = (self.usage_by_worker or {}).get(e.name)
                    if u is not None:
                        last = (u.last_seen or "?").split("T")[0]
                        line += f" · {u.dispatches} dispatches · last={last}"
                    else:
                        line += " · 0 dispatches · last=-"
                lines.append(line)
        else:
            # ADR-0013 — markdown table. 컬럼 폭 동적 계산 금지.
            if usage_active:
                lines.append(self._TABLE_HEADER.rstrip("|") + " Dispatches | Last seen |")
                lines.append(self._TABLE_SEP.rstrip("|") + "------------:|-----------|")
            else:
                lines.append(self._TABLE_HEADER)
                lines.append(self._TABLE_SEP)
            for e in sorted_entries:
                model = e.model or "default"
                row = (
                    f"| {e.category:<6} | {e.name} | {e.display_name} | "
                    f"{e.role} | {e.domain} | {model} | {e.hired_at} |"
                )
                if usage_active:
                    u = (self.usage_by_worker or {}).get(e.name)
                    if u is not None:
                        last = (u.last_seen or "?").split("T")[0]
                        row += f" {u.dispatches} | {last} |"
                    else:
                        row += " 0 | - |"
                lines.append(row)
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
        return "\n".join(lines) + "\n"


def _read_company_meta(company_md_path: Path) -> tuple[str, str]:
    """company.md 에서 name + domain 추출."""
    if not company_md_path.exists():
        return "(unknown)", "(unknown)"
    parsed = fm.parse(company_md_path.read_text(encoding="utf-8"))
    return (
        str(parsed.frontmatter.get("name", "(unknown)")),
        str(parsed.frontmatter.get("domain", "(unknown)")),
    )


def _read_entry(path: Path) -> OrgEntry | None:
    """단일 워커 파일을 OrgEntry 로. schema 위반 시 None (호출자가 warn 처리).

    ADR-0019 — archived 파라미터 제거 (archive 메커니즘 폐기).
    """
    if not path.is_file() or path.name.startswith("."):
        return None
    # ADR-0019 — sync 백업 부산물 자연 배제 (.lskun-pre-sync.bak)
    if ".lskun-pre-sync.bak" in path.name:
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
        hired_at=str(f.get("hired_at", "?")),
        persona_synced_from=f.get(PROV_FROM),
        persona_synced_at=f.get(PROV_AT),
        archived=False,
    )


def build(adapter: StorageAdapter, with_usage: bool = False) -> OrgReport:
    """조직도 데이터 빌드. **read-only**.

    ADR-0019 (2026-05-27) — Archive 메커니즘 폐기. ``include_archived`` 인자
    제거. hired/ 만 스캔, archived/ 디렉토리는 plugin core 가 참조하지 않음.

    P109-A (2026-05-27) — ``with_usage=True`` 일 때 audit_view 로 워커별
    dispatch count + last_seen 집계. 사용자 명시 옵션 (자동 호출 X).
    """
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
            entry = _read_entry(p)
            if entry is not None:
                report.entries.append(entry)
    if with_usage:
        from lskun_kit.audit_view import read_usage
        report.usage_by_worker = read_usage(company_root / ".audit")
    return report


__all__ = ["OrgEntry", "OrgReport", "OrgError", "build"]
