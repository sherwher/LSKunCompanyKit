"""LSKunCompanyKit 의 도메인 모델.

ADR-0001 §3 (Reflection) 와 §4 (Storage Backend 추상화) 에서 정의된
4-method interface 가 다루는 데이터 구조.

ADR-0003 — Worker frontmatter 필수 필드 4개 → 5개 (``domain`` 추가).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


#: ADR-0003 — ``domain`` 은 회사 도메인 (예: "의료 SaaS") 또는 예약값 ``"meta"`` (CPO/HR).
REQUIRED_WORKER_FIELDS = ("name", "role", "domain", "hired_at", "storage_backend")

#: ADR-0003 §1 — CPO / HR Lead 등 도메인 무관 워커의 ``domain`` 예약값.
META_DOMAIN = "meta"


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
    """

    name: str
    role: str
    domain: str
    hired_at: date
    storage_backend: str
    body: str = ""  # frontmatter 이후 markdown 본문 전체
    extra: dict = field(default_factory=dict)


@dataclass
class Company:
    """company.md 의 메타데이터."""

    name: str
    body: str = ""
    extra: dict = field(default_factory=dict)
