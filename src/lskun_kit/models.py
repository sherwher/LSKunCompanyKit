"""LSKunCompanyKit 의 도메인 모델.

ADR-0001 §3 (Reflection) 와 §4 (Storage Backend 추상화) 에서 정의된
4-method interface 가 다루는 데이터 구조.

ADR-0003 — Worker frontmatter 필수 필드 4개 → 5개 (``domain`` 추가).
ADR-0004 §6 — Worker frontmatter 필수 5개 → 6개 (``display_name`` 추가),
              optional 1개 (``model``) 신설.
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

#: ADR-0004 §6 — optional frontmatter 필드.
OPTIONAL_WORKER_FIELDS = ("model",)

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


@dataclass(frozen=True)
class HistoryEntry:
    """Reflection 1줄. 워커의 ## Project History 섹션에 append 된다.

    포맷: ``- {date} / {project} / {topic} / {pattern} / first-pass {score}%``
    """

    date: date
    project: str
    topic: str
    pattern: str
    first_pass_score: int  # 0..100

    def render(self) -> str:
        return (
            f"- {self.date.isoformat()} / {self.project} / {self.topic} "
            f"/ {self.pattern} / first-pass {self.first_pass_score}%"
        )


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
    body: str = ""  # frontmatter 이후 markdown 본문 전체
    extra: dict = field(default_factory=dict)


@dataclass
class Company:
    """company.md 의 메타데이터."""

    name: str
    body: str = ""
    extra: dict = field(default_factory=dict)
