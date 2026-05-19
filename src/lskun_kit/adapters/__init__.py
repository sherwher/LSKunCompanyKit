"""Storage backend adapters.

ADR-0001 §4 의 추상화 계층. core 는 :class:`StorageAdapter` 만 의존하고
실제 구현은 모른다.

ADR-0009 — Plugin 은 self-contained 가 default. :class:`LocalAdapter` 만으로
완전 동작. :class:`VaultAdapter` 는 사용자가 ``LSKUN_VAULT`` env var 로 명시
opt-in 한 경우의 통합. 다른 외부 통합 (Notion 등) 의 추가는 별도 ADR + add-on
package 책임이며 본 core 는 외부 SDK / API 호출을 두지 않는다.
"""

from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.adapters.local import LocalAdapter
from lskun_kit.adapters.vault import (
    VaultAdapter,
    VaultCompanyNotFoundError,
    list_companies,
)

__all__ = [
    "StorageAdapter",
    "LocalAdapter",
    "VaultAdapter",
    "VaultCompanyNotFoundError",
    "list_companies",
]
