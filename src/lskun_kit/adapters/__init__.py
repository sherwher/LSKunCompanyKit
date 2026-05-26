"""Storage backend adapters.

ADR-0001 §4 의 추상화 계층. core 는 :class:`StorageAdapter` 만 의존하고
실제 구현은 모른다.

ADR-0009 — Plugin 은 self-contained 가 default. :class:`LocalAdapter` 만으로
완전 동작.

ADR-0015 (2026-05-22) — Vault backend 폐기. plugin core 는 vault 를 직접
참조하지 않는다. 외부 mirror 와의 sync 는 ``/LSKunCompanyKit:sync-in`` /
``/LSKunCompanyKit:sync-out`` 명령 (파일시스템 복사) 로만 수행. ABC 자체는
유지 — 미래에 다른 backend (예: encrypted local store) 추가 가능성. 단
vault 직접 통합은 영원히 금지.
"""

from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.adapters.local import LocalAdapter

__all__ = [
    "StorageAdapter",
    "LocalAdapter",
]
