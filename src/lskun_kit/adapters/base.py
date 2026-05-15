"""StorageAdapter 추상 인터페이스.

ADR-0001 §4 — core 는 이 4-method interface 만 알고 구현은 모른다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from lskun_kit.models import Company, HistoryEntry, Worker


class StorageAdapter(ABC):
    """모든 storage backend 가 구현해야 하는 4-method interface."""

    @abstractmethod
    def read_worker(self, name: str) -> Worker:
        """워커 markdown 을 읽어 :class:`Worker` 로 반환.

        Raises:
            WorkerNotFoundError: 워커가 존재하지 않을 때.
            InvalidWorkerSchemaError: frontmatter 필수 필드 누락 시.
        """

    @abstractmethod
    def append_history(self, name: str, entry: HistoryEntry) -> None:
        """워커의 ``## Project History`` 섹션에 1줄을 append.

        섹션이 없으면 생성한다. 중복 라인은 검사하지 않는다 — 호출자 책임.
        """

    @abstractmethod
    def list_workers(self) -> list[str]:
        """hired/ 디렉토리에 존재하는 워커 이름 목록을 정렬해서 반환."""

    @abstractmethod
    def read_company(self) -> Company:
        """company.md 의 메타데이터를 반환."""
