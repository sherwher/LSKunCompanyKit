"""신규 회사 셋업 — ``/lskun-kit:init`` 의 백엔드 로직.

ADR-0002 §3 — 단일 진입점.

ADR-0015 (2026-05-22) — Vault backend 폐기, Local SSOT 단일화. 본 모듈은
P85 에서 vault 의존만 제거하여 P87 (멱등성 4행 명세) 까지 기존 local 동작을
유지한다. 신규 회사 root 의 ``~/.lskun-companies/<name>/`` 이전은 P86,
멱등성 분기 4행 (신규/joining/silent/confirm) 은 P87 에서 박제.

동작 순서 (현재 — P85 기준):
    1. backend = "local" 고정 (vault 분기 제거)
    2. 회사 루트 경로 결정 = ``<project-root>/.company/`` (P86 에서 이전 예정)
    3. ``company.md`` 박제 (이미 있으면 **덮어쓰지 않음**)
    4. ``hired/`` 디렉토리 생성 후 CPO + HR 자동 hire (둘 다 이미 있으면 skip)
    5. 진단 리포트 dataclass 반환 — caller (slash command) 가 사용자에게 출력
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date as date_cls
from pathlib import Path

from lskun_kit.adapters import frontmatter
from lskun_kit.persona_injection import inject as inject_cpo_persona
from lskun_kit.templates import iter_default_workers, render_default_worker

LOCAL_COMPANY_DIRNAME = ".company"


@dataclass
class InitResult:
    """``init.run()`` 의 결과 — slash command 가 사용자에게 출력할 진단."""

    backend: str  # ADR-0015 — "local" 고정 (vault 폐기)
    company_root: Path
    company_name: str
    company_md_created: bool
    company_md_path: Path
    workers_created: list[str] = field(default_factory=list)
    workers_skipped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    persona_action: str = "skipped"  # ADR-0004 §1 — "created" | "updated" | "unchanged" | "skipped"
    persona_path: Path | None = None

    def render(self) -> str:
        """사람이 읽는 진단 리포트."""

        lines = [
            f"LSKunCompanyKit init",
            f"================================================",
            f"backend       : {self.backend}",
            f"company       : {self.company_name}",
            f"company root  : {self.company_root}",
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
    project_root: Path | str,
    company_name: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[str, str, Path]:
    """회사 루트 디렉토리 경로 결정 (ADR-0015 — local 단일 backend).

    Args:
        project_root: 현재 프로젝트 루트. 회사 root = ``<project_root>/.company``.
        company_name: 명시 지정. ``None`` 이면 project root 디렉토리 이름.
        env: 환경변수 dict (테스트용 주입, P85 시점에는 사용 안 함).

    Returns:
        ``(backend, company_name, company_root_path)`` — backend 는 항상 ``"local"``.

    Note:
        P86 에서 회사 root 가 ``~/.lskun-companies/<name>/`` 로 이전 예정.
        P87 에서 멱등성 분기 4행 (신규/joining/silent/confirm) 박제 예정.
    """

    backend = "local"
    backend_root = Path(project_root).expanduser()
    resolved_company = (
        (company_name or "").strip()
        or Path(project_root).expanduser().resolve().name
    )
    if "/" in resolved_company or resolved_company in (".", ".."):
        raise ValueError(f"invalid company name: {resolved_company!r}")
    return backend, resolved_company, backend_root / LOCAL_COMPANY_DIRNAME


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
) -> InitResult:
    """회사 초기 셋업 실행.

    멱등 (idempotent) 동작:
        - 회사 디렉토리 이미 있으면 그대로 재사용
        - ``company.md`` 이미 있으면 절대 덮어쓰지 않음
        - 워커가 이미 hired 되어 있으면 skip

    Args:
        domain: ADR-0003 — 회사 도메인 (예: "의료 SaaS"). 자유 입력.
                ``company.md`` 의 ``domain:`` frontmatter 에 박제된다.
                빈 문자열이면 ``""`` 로 박제 (doctor 가 경고로 안내).
                CPO / HR Lead 는 본 값과 무관하게 항상 ``domain="meta"`` 로 hire.
        cpo_name: ADR-0004 §5 — CPO 의 ``display_name`` (사람 이름, 사용자가 직접 입력).
                  CPO 가 이미 hired 되어 있지 않은 상태에서는 필수. 빈 문자열이면 ``ValueError``.
                  이미 hired 인 경우는 무시.
        hr_name:  ADR-0004 §5 — HR Lead 의 ``display_name``. 동일 규칙.

    Raises:
        ValueError: 신규 CPO/HR hire 가 필요한데 ``cpo_name`` / ``hr_name`` 이 비어 있을 때.
    """

    env = env if env is not None else os.environ.copy()
    today = today or date_cls.today()

    backend, resolved_company, company_root = resolve_company_root(
        project_root, company_name=company_name, env=env
    )

    notes: list[str] = []

    company_root.mkdir(parents=True, exist_ok=True)
    hired_dir = company_root / "hired"
    hired_dir.mkdir(parents=True, exist_ok=True)

    # company.md — 이미 있으면 보존, 없으면 신규 박제
    company_md = company_root / "company.md"
    if company_md.exists():
        company_md_created = False
        notes.append("기존 company.md 보존 — 내용 변경 안 함")
    else:
        company_md.write_text(
            _render_company_md(resolved_company, today, one_liner, domain),
            encoding="utf-8",
        )
        company_md_created = True

    # CPO / HR auto-hire — ADR-0004 §5: display_name 은 사용자가 직접 입력.
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
        # ADR-0010 — CPO/HR Lead 는 메타 워커. 첫 hire 시점에 plugin 버전 provenance 박제.
        from lskun_kit import __version__ as _kit_version
        synced_from = f"lskun-kit@{_kit_version}" if worker_name in ("cpo", "hr-lead") else None
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

    # ADR-0004 §1 — CPO persona 를 사용자 프로젝트 root 의 CLAUDE.md 에 inline 박제.
    persona_action = "skipped"
    persona_path: Path | None = None
    if inject_persona:
        cpo_md = hired_dir / "cpo.md"
        if cpo_md.exists():
            parsed = frontmatter.parse(cpo_md.read_text(encoding="utf-8"))
            result = inject_cpo_persona(
                project_root=Path(project_root).expanduser(),
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
        company_root=company_root,
        company_name=resolved_company,
        company_md_created=company_md_created,
        company_md_path=company_md,
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
    "LOCAL_COMPANY_DIRNAME",
    "resolve_company_root",
    "run",
]
