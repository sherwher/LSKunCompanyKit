"""LSKunCompanyKit 의 도메인 모델.

ADR-0001 §4 (Storage Backend 추상화) 의 interface 가 다루는 데이터 구조.

ADR-0003 — Worker frontmatter 필수 필드 4개 → 5개 (``domain`` 추가).
ADR-0004 §6 — Worker frontmatter 필수 5개 → 6개 (``display_name`` 추가),
              optional 1개 (``model``) 신설.
ADR-0014 — Reflection 메커니즘 폐기. ``HistoryEntry`` / ``HISTORY_FIELD_MAX_LEN`` 제거.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


#: ADR-0003 + ADR-0004 §6 — 필수 frontmatter 필드.
REQUIRED_WORKER_FIELDS = (
    "name",
    "role",
    "domain",
    "hired_at",
    "storage_backend",
    "display_name",
)

#: ADR-0004 §6 + ADR-0010 + P69 — optional frontmatter 필드.
#: ``keywords`` 는 콤마 구분 문자열 (예: ``"API, DB 마이그레이션, 결제 webhook"``).
#: ``frontmatter.py`` 가 list 를 지원하지 않으므로 의도적으로 단일 string.
#: plugin core 는 keywords 를 매칭/정렬에 사용하지 않는다 (raw display 만).
#: CPO LLM 이 routing context 에 노출된 keywords 를 보고 자유 해석한다.
OPTIONAL_WORKER_FIELDS = (
    "model",
    "persona_synced_from",
    "persona_synced_at",
    "keywords",
)

#: ADR-0003 §1 — CPO / HR Lead 등 도메인 무관 워커의 ``domain`` 예약값.
META_DOMAIN = "meta"

#: ADR-0004 §4 — ``model`` 미지정 시 워커 기본 모델 (CPO 는 메인 세션의 사용자 ``/model`` 설정).
DEFAULT_WORKER_MODEL = "sonnet"

#: ADR-0004 §4 — alias → 모델 ID (2026-05-18 기준 최신 Claude).
#: hire/work 의 ``--model`` 옵션이 받는 alias 를 표준화. 모델 ID 직접 입력도 그대로 허용.
MODEL_ALIASES: dict[str, str] = {
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-7",
    "haiku": "claude-haiku-4-5-20251001",
}


def resolve_model(value: str | None) -> str | None:
    """alias → 모델 ID. 이미 ID 면 그대로 반환. ``None`` 이면 ``None``.

    Examples:
        >>> resolve_model("opus")
        'claude-opus-4-7'
        >>> resolve_model("claude-opus-4-7")
        'claude-opus-4-7'
        >>> resolve_model(None) is None
        True
    """

    if value is None:
        return None
    return MODEL_ALIASES.get(value, value)


@dataclass
class Worker:
    """hired/<name>.md 를 메모리에 표현한 객체.

    ADR-0003 — ``domain`` 은 회사 도메인 (예: "의료 SaaS") 을 상속하거나
    예약값 ``"meta"`` (CPO/HR Lead 등 도메인 무관 워커) 를 가진다.

    ADR-0004 §6 — ``display_name`` 은 사람 이름 자유 입력 (필수).
    ``model`` 은 ``"sonnet" | "opus"`` 또는 모델 ID. ``None`` 이면
    ``DEFAULT_WORKER_MODEL`` 을 적용 (frontmatter 에 ``model`` 키가 아예 없는 경우).
    """

    name: str
    role: str
    domain: str
    hired_at: date
    storage_backend: str
    display_name: str
    model: str | None = None
    #: ADR-0010 — persona body 가 sync 된 plugin 버전. 메타 워커 (cpo/hr-lead) 에만 박힘.
    persona_synced_from: str | None = None
    #: ADR-0010 — persona body sync 시각 (ISO date). 메타 워커에만 박힘.
    persona_synced_at: str | None = None
    #: P69 — 워커 자기 책임/도메인 키워드 (콤마 구분). CPO 라우팅 정확도 보강용.
    #: 메타 워커 (CPO/HR Lead) 는 비워둔다 — 라우팅 후보가 아니라서 무의미.
    keywords: str | None = None
    body: str = ""  # frontmatter 이후 markdown 본문 전체
    extra: dict = field(default_factory=dict)


@dataclass
class Company:
    """company.md 의 메타데이터."""

    name: str
    body: str = ""
    extra: dict = field(default_factory=dict)
