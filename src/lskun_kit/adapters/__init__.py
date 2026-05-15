"""Storage backend adapters.

ADR-0001 §4 의 추상화 계층. core 는 :class:`StorageAdapter` 만 의존하고
실제 구현 (Local / Vault / future Notion 등) 은 모른다.
"""

from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.adapters.local import LocalAdapter

__all__ = ["StorageAdapter", "LocalAdapter"]
