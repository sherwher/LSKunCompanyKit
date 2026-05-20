"""기본 워커 markdown 템플릿.

ADR-0002 §1~§2 — ``/lskun-kit:init`` 가 새 회사 셋업 시 자동 hire 하는 2명
(CPO, 인사팀장) 의 frontmatter + persona 본문을 한 곳에 정의한다.

stdlib 의 ``importlib.resources`` 로 읽기 — 외부 의존성 없음.
"""

from __future__ import annotations

from datetime import date as date_cls
from importlib import resources
from typing import Iterable

from lskun_kit.adapters import frontmatter
from lskun_kit.models import DEFAULT_WORKER_MODEL, META_DOMAIN

#: ``(worker_name, role, template_filename, default_model)`` 튜플 — init 가 순회.
#:
#: ADR-0003 §1 — CPO / HR Lead 는 ``domain="meta"`` 로 hire (도메인 무관).
#: ADR-0004 §4 — CPO 는 메인 세션이므로 frontmatter ``model`` 미설정 (None).
#:               HR Lead 는 ``"sonnet"`` 명시 (단순 채용/해고 작업).
DEFAULT_WORKERS: tuple[tuple[str, str, str, str | None], ...] = (
    ("cpo", "chief-product-officer", "cpo.md", None),
    ("hr-lead", "hr-lead", "hr-lead.md", "sonnet"),
)


def list_default_worker_names() -> list[str]:
    return [name for name, _role, _file, _model in DEFAULT_WORKERS]


def render_default_worker(
    name: str,
    role: str,
    template_filename: str,
    storage_backend: str,
    display_name: str,
    hired_at: date_cls | None = None,
    domain: str = META_DOMAIN,
    model: str | None = None,
    synced_from: str | None = None,
    keywords: str | None = None,
    body_override: str | None = None,
) -> str:
    """템플릿 파일을 읽어 frontmatter 6 필수 필드 (+ optional) 를 채워 반환한다.

    Args:
        name: 워커 이름 (파일명 stem 과 일치해야 함)
        role: 워커 역할
        template_filename: ``src/lskun_kit/templates/<filename>`` 의 본문 파일명.
                           ``body_override`` 가 주어지면 무시된다.
        storage_backend: ``"local"`` | ``"vault"``
        display_name: ADR-0004 §5 — 사람 이름 (자유 입력, 필수).
                      CPO/HR 의 경우 init 인터뷰에서 사용자가 직접 입력한 값을 받는다.
        hired_at: 채용일 (기본값: 오늘)
        domain: ADR-0003 — 회사 도메인 또는 예약값 ``"meta"`` (기본값 = ``"meta"``,
                CPO/HR Lead 등 도메인 무관 워커용).
        model: ADR-0004 §4 — ``"sonnet" | "opus"`` 또는 모델 ID. ``None`` 이면
               frontmatter 에 ``model`` 키를 emit 하지 않음 (= default 적용).
        keywords: P69 — 콤마 구분 키워드 문자열 (예: ``"API, DB 마이그레이션"``).
                  ``None`` 이면 frontmatter 에 ``keywords`` 키를 emit 하지 않음.
                  메타 워커 (CPO/HR Lead) 는 라우팅 후보가 아니므로 비워두는 것이 원칙.
        body_override: P70 (ADR-0011) — HR Lead 가 JD 기반으로 작성한 markdown
                       string. ``None`` 이면 ``template_filename`` 의 본문을 읽는다
                       (기존 동작 보존). 주어지면 그 string 을 그대로 body 로 사용
                       — plugin core 는 schema 검증을 하지 않는 단순 passthrough
                       (ADR-0009 + ADR-0011 §4).

    Returns:
        frontmatter + 본문이 결합된 markdown 문자열. 그대로
        ``hired/<name>.md`` 로 쓰면 된다.

    Raises:
        ValueError: ``display_name`` 이 빈 문자열일 때.
    """

    if not display_name or not display_name.strip():
        raise ValueError(
            "display_name is required (ADR-0004 §5 — CPO/HR 자동 생성 금지)"
        )

    fm: dict[str, str] = {
        "name": name,
        "role": role,
        "domain": domain,
        "hired_at": (hired_at or date_cls.today()).isoformat(),
        "storage_backend": storage_backend,
        "display_name": display_name,
    }
    if model is not None:
        fm["model"] = model
    # ADR-0010 — 메타 워커 (CPO/HR Lead) 의 hire 시점에 provenance 박제.
    if synced_from is not None:
        fm["persona_synced_from"] = synced_from
        fm["persona_synced_at"] = (hired_at or date_cls.today()).isoformat()
    # P69 — keywords 가 주어졌을 때만 frontmatter 에 박제.
    if keywords is not None and keywords.strip():
        fm["keywords"] = keywords.strip()
    # P70 (ADR-0011) — body_override 우선. plugin core 는 내용 검증 X (passthrough).
    body = body_override if body_override is not None else _read_template(template_filename)
    return frontmatter.dump(fm, body)


def iter_default_workers() -> Iterable[tuple[str, str, str, str | None]]:
    return iter(DEFAULT_WORKERS)


def _read_template(filename: str) -> str:
    return resources.files(__name__).joinpath(filename).read_text(encoding="utf-8")


__all__ = [
    "DEFAULT_WORKERS",
    "list_default_worker_names",
    "render_default_worker",
    "iter_default_workers",
]
