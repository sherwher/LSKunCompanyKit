"""신규 회사 셋업 — ``/lskun-kit:init`` 의 백엔드 로직.

ADR-0015 (2026-05-22) — Local SSOT 단일화 + ``/init`` 멱등성 4행 명세.

회사 root 결정:
    ``~/.lskun-companies/<name>/`` (``paths.company_root(name)`` 단일 진입점)
    이전의 ``<project-root>/.company/`` 는 결정 1-A 로 폐기.

멱등성 4행 명세 (결정 2-B):
    | row | ~/.lskun-companies/<name>/ | 현재 프로젝트 marker | 동작 |
    |-----|----------------------------|----------------------|------|
    |  1  | ❌ 신규 회사                | ❌ 부재                | 회사 창설 + CPO/HR hire + marker 박제 |
    |  2  | ✅ 기존 회사                | ❌ 부재 (joining)     | 회사 자원 skip (preserve) + marker 박제 |
    |  3  | ✅ 기존 회사                | ✅ 같은 회사           | silent skip (멱등) |
    |  4  | ✅ 기존 회사                | ✅ 다른 회사           | ConfirmRequired raise → caller 가 사용자 confirm 후 재호출 |

Confirm 패턴 (ADR-0015 결정 2-B + 3-A):
    Plugin core 는 stdin 을 잡지 않는다. row 4 에서 ``ConfirmRequired`` 를
    raise 하고, caller (slash command 의 LLM) 가 사용자에게 묻고
    ``confirmed_replace_marker=True`` 인자와 함께 재호출한다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date as date_cls
from pathlib import Path

from lskun_kit.adapters import frontmatter
from lskun_kit.errors import ConfirmRequired
from lskun_kit.paths import company_root, validate_company_name
from lskun_kit.persona_injection import (
    extract_company_name as _extract_marker_company,
    inject as inject_cpo_persona,
)
from lskun_kit.templates import iter_default_workers, render_default_worker


@dataclass
class InitResult:
    """``init.run()`` 의 결과 — slash command 가 사용자에게 출력할 진단."""

    backend: str  # ADR-0015 — "local" 고정
    company_root: Path
    company_name: str
    company_md_created: bool
    company_md_path: Path
    #: ADR-0015 결정 2-B 4행 중 어떤 행으로 분기됐는지.
    idempotency_row: str  # "founded" | "joined" | "silent" | "marker_replaced"
    workers_created: list[str] = field(default_factory=list)
    workers_skipped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    persona_action: str = "skipped"  # "created" | "updated" | "unchanged" | "skipped"
    persona_path: Path | None = None

    def render(self) -> str:
        """사람이 읽는 진단 리포트."""

        lines = [
            "LSKunCompanyKit init",
            "================================================",
            f"backend       : {self.backend}",
            f"company       : {self.company_name}",
            f"company root  : {self.company_root}",
            f"멱등 분기      : row={self.idempotency_row} (ADR-0015 결정 2-B)",
            f"company.md    : {'created' if self.company_md_created else 'preserved (already exists)'} → {self.company_md_path}",
            f"workers hired : {', '.join(self.workers_created) if self.workers_created else '(none)'}",
        ]
        if self.workers_skipped:
            lines.append(f"workers kept  : {', '.join(self.workers_skipped)}")
        if self.persona_path is not None:
            lines.append(
                f"CPO persona   : {self.persona_action} → {self.persona_path}"
            )
        else:
            lines.append(f"CPO persona   : {self.persona_action}")
        for note in self.notes:
            lines.append(f"note          : {note}")
        return "\n".join(lines) + "\n"


def resolve_company_root(
    company_name: str,
    env: dict[str, str] | None = None,
) -> tuple[str, str, Path]:
    """ADR-0015 — Local SSOT 단일 위치의 회사 root path 결정.

    Args:
        company_name: 회사 이름. ``paths.validate_company_name`` 으로 검증됨.
        env: 환경변수 dict (현재 미사용. legacy compatibility 만).

    Returns:
        ``(backend, company_name, company_root_path)`` —
        backend 는 항상 ``"local"``. path 는 ``~/.lskun-companies/<name>/``.

    Raises:
        ValueError: 회사 이름이 invalid.
    """

    validate_company_name(company_name)
    return "local", company_name, company_root(company_name)


def run(
    project_root: Path | str,
    company_name: str | None = None,
    one_liner: str = "",
    domain: str = "",
    cpo_name: str = "",
    hr_name: str = "",
    inject_persona: bool = True,
    env: dict[str, str] | None = None,
    today: date_cls | None = None,
    confirmed_replace_marker: bool = False,
) -> InitResult:
    """회사 초기 셋업 실행 (ADR-0015 결정 2-B 4행 멱등성).

    Args:
        project_root: 현재 프로젝트 루트. CLAUDE.md marker 박제 대상.
        company_name: 회사 이름. 생략 시 project root 디렉토리명 fallback.
        one_liner: 회사 한 줄 소개 (신규 창설 시 company.md 본문).
        domain: 회사 도메인 (예: "의료 SaaS"). 신규 창설 시 company.md frontmatter.
        cpo_name: CPO 의 ``display_name``. 신규 hire 가 필요한 경우 필수.
        hr_name: HR Lead 의 ``display_name``. 동일.
        inject_persona: ``False`` 면 CLAUDE.md marker 박제 skip (테스트용).
        env: 환경변수 dict (legacy compatibility).
        today: 날짜 주입 (테스트용).
        confirmed_replace_marker: row 4 (다른 회사 marker 재진입) 의 사용자
            confirm 완료 신호. ``False`` 인데 row 4 에 진입하면 ``ConfirmRequired``
            raise. ``True`` 면 marker 를 새 회사로 교체.

    Raises:
        ConfirmRequired: row 4 에 진입했고 ``confirmed_replace_marker=False`` 일 때.
        ValueError: company_name 검증 실패 또는 신규 hire 필요한데 이름 누락 시.
    """

    env = env if env is not None else os.environ.copy()
    today = today or date_cls.today()
    proj = Path(project_root).expanduser()

    resolved_company = (
        (company_name or "").strip()
        or proj.resolve().name
    )
    backend, resolved_company, co_root = resolve_company_root(
        resolved_company, env=env
    )

    # --- ADR-0015 결정 2-B 멱등성 4행 분기 ---
    marker_company = _extract_marker_company(proj) if inject_persona else None
    company_existed = (co_root / "company.md").exists()
    notes: list[str] = []

    if marker_company is not None and marker_company != resolved_company:
        # row 4 — 다른 회사 marker 재진입
        if not confirmed_replace_marker:
            raise ConfirmRequired(
                kind="marker_replace",
                prompt=(
                    f"기존 marker (회사 '{marker_company}') 를 "
                    f"(회사 '{resolved_company}') 로 교체하시겠습니까? [y/N]"
                ),
                context={
                    "current_marker_company": marker_company,
                    "new_company": resolved_company,
                    "project_root": str(proj),
                },
            )
        idempotency_row = "marker_replaced"
        notes.append(
            f"marker 교체: '{marker_company}' → '{resolved_company}' "
            f"(사용자 confirm 완료)"
        )
    elif marker_company == resolved_company and company_existed:
        # row 3 — 같은 회사 silent skip (멱등)
        idempotency_row = "silent"
    elif company_existed:
        # row 2 — 기존 회사 + 신규 프로젝트 (joining)
        idempotency_row = "joined"
        notes.append(
            f"joining 모드 — 기존 회사 '{resolved_company}' 의 자원은 preserve, "
            f"현재 프로젝트의 CLAUDE.md marker 만 박제"
        )
    else:
        # row 1 — 신규 회사 창설
        idempotency_row = "founded"

    # --- 회사 자원 박제 (joining / silent 시 skip) ---
    co_root.mkdir(parents=True, exist_ok=True)
    hired_dir = co_root / "hired"
    hired_dir.mkdir(parents=True, exist_ok=True)

    company_md = co_root / "company.md"
    if idempotency_row == "silent":
        # 완전 멱등 — 회사 자원 / 워커 / persona 모두 skip
        return InitResult(
            backend=backend,
            company_root=co_root,
            company_name=resolved_company,
            company_md_created=False,
            company_md_path=company_md,
            idempotency_row=idempotency_row,
            workers_created=[],
            workers_skipped=[],
            notes=["silent skip — 같은 회사 marker 가 이미 박제됨 (멱등)"],
            persona_action="unchanged",
            persona_path=proj / "CLAUDE.md",
        )

    # company.md — 이미 있으면 보존, 없으면 신규 박제
    if company_md.exists():
        company_md_created = False
        if idempotency_row in ("founded", "joined"):
            notes.append("기존 company.md 보존 — 내용 변경 안 함")
    else:
        company_md.write_text(
            _render_company_md(resolved_company, today, one_liner, domain),
            encoding="utf-8",
        )
        company_md_created = True

    # CPO / HR auto-hire (joining 시에도 부재면 hire — 회사 무결성 보장)
    display_name_by_worker = {"cpo": cpo_name, "hr-lead": hr_name}
    workers_created: list[str] = []
    workers_skipped: list[str] = []
    for worker_name, role, template_filename, default_model in iter_default_workers():
        worker_path = hired_dir / f"{worker_name}.md"
        if worker_path.exists():
            workers_skipped.append(worker_name)
            continue
        display_name = (display_name_by_worker.get(worker_name) or "").strip()
        if not display_name:
            raise ValueError(
                f"{worker_name} 의 display_name 이 비어 있다 "
                f"(ADR-0004 §5 — CPO/HR 이름은 사용자가 직접 입력). "
                f"`run(..., {'cpo_name' if worker_name == 'cpo' else 'hr_name'}='...')` 로 전달하라."
            )
        from lskun_kit import __version__ as _kit_version
        synced_from = (
            f"lskun-kit@{_kit_version}"
            if worker_name in ("cpo", "hr-lead") else None
        )
        worker_path.write_text(
            render_default_worker(
                name=worker_name,
                role=role,
                template_filename=template_filename,
                storage_backend=backend,
                display_name=display_name,
                hired_at=today,
                model=default_model,
                synced_from=synced_from,
            ),
            encoding="utf-8",
        )
        workers_created.append(worker_name)

    # CPO persona inline 박제 — joining / founded / marker_replaced 모두 박제
    persona_action = "skipped"
    persona_path: Path | None = None
    if inject_persona:
        cpo_md = hired_dir / "cpo.md"
        if cpo_md.exists():
            parsed = frontmatter.parse(cpo_md.read_text(encoding="utf-8"))
            result = inject_cpo_persona(
                project_root=proj,
                company_name=resolved_company,
                cpo_display_name=parsed.frontmatter.get("display_name", "CPO"),
                cpo_body=parsed.body,
            )
            persona_action = result.action
            persona_path = result.claude_md_path
        else:
            notes.append("CPO persona 박제 skip — hired/cpo.md 가 존재하지 않음")

    return InitResult(
        backend=backend,
        company_root=co_root,
        company_name=resolved_company,
        company_md_created=company_md_created,
        company_md_path=company_md,
        idempotency_row=idempotency_row,
        workers_created=workers_created,
        workers_skipped=workers_skipped,
        notes=notes,
        persona_action=persona_action,
        persona_path=persona_path,
    )


def _render_company_md(
    name: str, founded: date_cls, one_liner: str, domain: str
) -> str:
    body_intro = one_liner.strip() if one_liner else "(회사 한 줄 소개)"
    body = f"# {name}\n\n{body_intro}\n"
    return frontmatter.dump(
        {
            "name": name,
            "founded": founded.isoformat(),
            "domain": domain,
        },
        body,
    )


__all__ = [
    "InitResult",
    "resolve_company_root",
    "run",
]
