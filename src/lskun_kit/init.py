"""신규 회사 셋업 — ``/lskun-kit:init`` 의 백엔드 로직.

ADR-0002 §3 — 단일 진입점.

동작 순서:
    1. 활성 backend 결정 (``LSKUN_VAULT`` 환경변수 우선, 없으면 Local)
    2. 회사 루트 경로 결정 + 디렉토리 생성 (사용자의 기존 회사 디렉토리 보존)
    3. ``company.md`` 박제 (이미 있으면 **덮어쓰지 않음** — ADR-0002 §3 보존 정책)
    4. ``hired/`` 디렉토리 생성 후 CPO + HR 자동 hire (둘 다 이미 있으면 skip)
    5. 진단 리포트 dataclass 반환 — caller (slash command) 가 사용자에게 출력
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date as date_cls
from pathlib import Path

from lskun_kit.adapters import frontmatter
from lskun_kit.adapters.vault import COMPANIES_DIRNAME
from lskun_kit.persona_injection import inject as inject_cpo_persona
from lskun_kit import project_link as _pl
from lskun_kit.templates import iter_default_workers, render_default_worker

#: ``$LSKUN_VAULT`` 환경변수 키 — Vault backend 선택 trigger.
ENV_VAULT = "LSKUN_VAULT"
#: ``$LSKUN_COMPANY`` 환경변수 키 — Vault 안 회사 이름. CLI 인자가 우선.
ENV_COMPANY = "LSKUN_COMPANY"

LOCAL_COMPANY_DIRNAME = ".company"


@dataclass
class InitResult:
    """``init.run()`` 의 결과 — slash command 가 사용자에게 출력할 진단."""

    backend: str  # "local" | "vault"
    company_root: Path
    company_name: str
    company_md_created: bool
    company_md_path: Path
    workers_created: list[str] = field(default_factory=list)
    workers_skipped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    persona_action: str = "skipped"  # ADR-0004 §1 — "created" | "updated" | "unchanged" | "skipped"
    persona_path: Path | None = None
    link_action: str = "skipped"  # ADR-0007 §3 — "created" | "preserved" | "skipped"
    link_path: Path | None = None

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
        if self.link_path is not None:
            lines.append(
                f"project link  : {self.link_action} → {self.link_path}"
            )
        else:
            lines.append(f"project link  : {self.link_action}")
        for note in self.notes:
            lines.append(f"note          : {note}")
        return "\n".join(lines) + "\n"


def detect_backend(
    project_root: Path | str,
    env: dict[str, str] | None = None,
) -> tuple[str, Path]:
    """``LSKUN_VAULT`` 가 있으면 Vault, 없으면 Local.

    Returns:
        ``(backend, backend_root)`` —
        Vault: ``(vault_path, ...)`` 에서 vault path 반환
        Local: project root 자체 반환
    """

    env = env if env is not None else os.environ.copy()
    vault = env.get(ENV_VAULT, "").strip()
    if vault:
        return "vault", Path(vault).expanduser()
    return "local", Path(project_root).expanduser()


def detect_dual_backend(
    project_root: Path | str,
    env: dict[str, str] | None = None,
) -> tuple[Path, Path] | None:
    """P33 — Local + Vault 양쪽에 회사 데이터가 동시에 존재하는지 감지.

    Returns:
        ``(local_company_root, vault_company_root)`` 둘 다 ``company.md`` 를
        포함하고 있으면 두 경로 반환. 아니면 ``None``.

    감지 의도: ``LSKUN_VAULT`` 가 설정돼 Vault backend 가 선택되더라도,
    예전에 만든 Local ``.company/`` 가 남아있으면 사용자가 모르는 사이에
    history 박제가 한쪽에만 누적될 수 있다. doctor / init 가 본 함수로
    경고를 emit 한다 (자동 마이그레이션은 하지 않음 — ADR-0001 §5 SSOT 정책).
    """

    env = env if env is not None else os.environ.copy()
    proj = Path(project_root).expanduser()
    local_co = proj / LOCAL_COMPANY_DIRNAME
    if not (local_co / "company.md").exists():
        return None

    vault = env.get(ENV_VAULT, "").strip()
    if not vault:
        return None
    company = env.get(ENV_COMPANY, "").strip()
    if not company:
        return None
    vault_co = Path(vault).expanduser() / COMPANIES_DIRNAME / company
    if not (vault_co / "company.md").exists():
        return None

    return local_co, vault_co


def resolve_company_root(
    project_root: Path | str,
    company_name: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[str, str, Path]:
    """backend + 회사명을 받아 회사 루트 디렉토리 경로 결정.

    Args:
        project_root: 현재 프로젝트 루트 (Local backend 시 ``<root>/.company``)
        company_name: 명시 지정. Vault 에서만 의미 있음. ``None`` 이면 ``$LSKUN_COMPANY``
        env: 환경변수 dict (테스트용 주입)

    Returns:
        ``(backend, company_name, company_root_path)``

    Raises:
        ValueError: Vault backend 인데 회사명이 결정되지 않을 때.
    """

    env = env if env is not None else os.environ.copy()
    backend, backend_root = detect_backend(project_root, env=env)

    if backend == "local":
        # Local backend 는 회사명을 굳이 받지 않는다 — project root 1개 = 1 회사.
        # company.md 의 name 만 의미를 가지므로, 명시 안 됐으면 디렉토리 이름을 쓴다.
        resolved_company = (company_name or env.get(ENV_COMPANY, "").strip()
                            or Path(project_root).expanduser().resolve().name)
        return backend, resolved_company, backend_root / LOCAL_COMPANY_DIRNAME

    # vault
    resolved_company = (company_name or env.get(ENV_COMPANY, "").strip()).strip()
    if not resolved_company:
        raise ValueError(
            f"Vault backend 가 선택됐지만 회사명이 비어 있다. "
            f"`{ENV_COMPANY}` 환경변수를 설정하거나 init 인자로 회사명을 넘겨라."
        )
    if "/" in resolved_company or resolved_company in (".", ".."):
        raise ValueError(f"invalid company name: {resolved_company!r}")
    return backend, resolved_company, backend_root / COMPANIES_DIRNAME / resolved_company


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

    # P33 — dual-backend 경고 (자동 마이그레이션은 ADR-0001 §5 위반이므로 금지).
    dual = detect_dual_backend(project_root, env=env)
    if dual is not None:
        local_co, vault_co = dual
        notes.append(
            f"dual-backend 감지: Local({local_co}) + Vault({vault_co}) 둘 다 "
            f"company.md 보유. 활성 backend={backend} 만 갱신된다. "
            f"양쪽 동기화가 필요하면 `/lskun-kit:migrate` 사용."
        )

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
        worker_path.write_text(
            render_default_worker(
                name=worker_name,
                role=role,
                template_filename=template_filename,
                storage_backend=backend,
                display_name=display_name,
                hired_at=today,
                model=default_model,
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

    # ADR-0007 §3 — 사용자 프로젝트 root 의 .claude/lskun-kit.json 박제
    link_action = "skipped"
    link_file_path: Path | None = None
    project_root_path = Path(project_root).expanduser()
    if not project_root_path.exists():
        notes.append(
            f"project link 박제 skip — project_root={project_root_path} 가 존재하지 않음"
        )
    else:
        existing = _pl.read(project_root_path)
        desired = _pl.ProjectLink(company=resolved_company, backend=backend)
        if existing is None:
            link_file_path = _pl.write(project_root_path, desired)
            link_action = "created"
        elif existing == desired:
            link_file_path = _pl.link_path(project_root_path)
            link_action = "preserved"
        else:
            link_file_path = _pl.link_path(project_root_path)
            link_action = "skipped"
            notes.append(
                f".claude/lskun-kit.json 가 이미 {existing.company!r} 를 가리킴 — "
                f"덮어쓰지 않음. /lskun-kit:role-init 으로 명시 갱신 필요."
            )

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
        link_action=link_action,
        link_path=link_file_path,
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
    "ENV_VAULT",
    "ENV_COMPANY",
    "LOCAL_COMPANY_DIRNAME",
    "detect_backend",
    "detect_dual_backend",
    "resolve_company_root",
    "run",
]
