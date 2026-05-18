"""StorageAdapter 추상 인터페이스.

ADR-0001 §4 — core 는 이 interface 만 알고 구현은 모른다.

P45 — write-path 확장:
    원래 4-method (read_worker / append_history / list_workers / read_company) 만
    있었고 hire/archive 는 slash command 가 파일을 직접 썼다. 미래 backend
    (Notion API 등) 가 파일 쓰기가 아닌 호출이 필요하면 hire/fire 로직을
    다시 작성해야 하는 abstraction 누수가 있었다.

    create_worker / archive_worker 를 ABC 에 추가하되, 기존 4-method 와 달리
    ``@abstractmethod`` 가 아닌 default ``NotImplementedError`` raise 로 둔다.
    외부 구현자가 점진적으로 채택할 수 있다. ``MarkdownTreeAdapter`` 가 file
    기반 구현을 제공.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from lskun_kit.models import Company, HistoryEntry, Worker


class StorageAdapter(ABC):
    """모든 storage backend 가 구현해야 하는 read-path 인터페이스."""

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

    # --- P45: write-path (default NotImplementedError, override 권장) ---

    def create_worker(
        self,
        name: str,
        frontmatter: dict[str, str],
        body: str,
    ) -> None:
        """신규 워커를 박제. 이미 존재하면 ``FileExistsError`` 류 raise.

        하위 구현이 override 한다. MarkdownTreeAdapter 가 file 기반 구현 제공.
        """

        raise NotImplementedError(
            f"{type(self).__name__} does not implement create_worker"
        )

    def archive_worker(self, name: str) -> None:
        """워커를 ``hired/`` 에서 ``archived/`` 로 이동 (해고).

        파일 삭제 금지 — history 보존 (ADR-0004 §3 + HR Lead persona). 하위 구현이
        override 한다.
        """

        raise NotImplementedError(
            f"{type(self).__name__} does not implement archive_worker"
        )
