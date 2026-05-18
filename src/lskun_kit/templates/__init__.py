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

#: ``(worker_name, role, template_filename)`` 튜플 — init 가 순회.
DEFAULT_WORKERS: tuple[tuple[str, str, str], ...] = (
    ("cpo", "chief-product-officer", "cpo.md"),
    ("hr-lead", "hr-lead", "hr-lead.md"),
)


def list_default_worker_names() -> list[str]:
    return [name for name, _role, _file in DEFAULT_WORKERS]


def render_default_worker(
    name: str,
    role: str,
    template_filename: str,
    storage_backend: str,
    hired_at: date_cls | None = None,
) -> str:
    """템플릿 파일을 읽어 frontmatter 4 필수 필드를 채워 반환한다.

    Args:
        name: 워커 이름 (파일명 stem 과 일치해야 함)
        role: 워커 역할
        template_filename: ``src/lskun_kit/templates/<filename>`` 의 본문 파일명
        storage_backend: ``"local"`` | ``"vault"``
        hired_at: 채용일 (기본값: 오늘)

    Returns:
        frontmatter + 본문이 결합된 markdown 문자열. 그대로
        ``hired/<name>.md`` 로 쓰면 된다.
    """

    body = _read_template(template_filename)
    fm = {
        "name": name,
        "role": role,
        "hired_at": (hired_at or date_cls.today()).isoformat(),
        "storage_backend": storage_backend,
    }
    return frontmatter.dump(fm, body)


def iter_default_workers() -> Iterable[tuple[str, str, str]]:
    return iter(DEFAULT_WORKERS)


def _read_template(filename: str) -> str:
    return resources.files(__name__).joinpath(filename).read_text(encoding="utf-8")


__all__ = [
    "DEFAULT_WORKERS",
    "list_default_worker_names",
    "render_default_worker",
    "iter_default_workers",
]
