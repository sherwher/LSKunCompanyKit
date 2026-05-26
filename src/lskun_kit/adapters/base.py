"""StorageAdapter 추상 인터페이스.

ADR-0001 §4 — core 는 이 interface 만 알고 구현은 모른다.

ADR-0014 — Reflection 메커니즘 폐기. ``append_history`` 메서드 + ``HistoryEntry``
import 제거. 워커는 채용 시 완성형 (JD only) 이며 시간 흐름으로 진화하지 않는다.

P45 — write-path 확장:
    원래 3-method (read_worker / list_workers / read_company) + 옛 append_history.
    create_worker / archive_worker 를 ABC 에 추가하되, 기존 메서드와 달리
    ``@abstractmethod`` 가 아닌 default ``NotImplementedError`` raise 로 둔다.
    외부 구현자가 점진적으로 채택할 수 있다. ``MarkdownTreeAdapter`` 가 file
    기반 구현을 제공.

ADR-0009 — Plugin core 는 외부 시스템 (Notion 등) 의 SDK / API 호출을 두지
않는다. 본 ABC 가 정의하는 인터페이스는 file 기반 (Local / Vault) 외 다른
구현체를 core 에 박는 것을 허용하지 않으며, 외부 통합은 별도 add-on package
의 책임이다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from lskun_kit.models import Company, Worker


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

    def archive_worker(
        self,
        name: str,
        archived_at: str | None = None,
        archived_reason: str | None = None,
    ) -> None:
        """워커를 ``hired/`` 에서 ``archived/`` 로 이동 (해고).

        파일 삭제 금지 — JD 자산 보존 (ADR-0004 §3 + HR Lead persona).

        ADR-0015 결정 7-B — archive 시점에 frontmatter 에 ``archived_at`` +
        ``archived_reason`` 박제. 기존 ``display_name`` 은 그대로 보존 (역사 자산
        불변, 7-B 의 "자동 익명화 / rewrite 금지"). archived 워커는 routing /
        SessionStart hook 의 후보에서 제외됨 (결정 7-B/7-E).

        Args:
            name: 해고할 워커 이름.
            archived_at: 해고일 (ISO 문자열, 예: "2026-05-22"). ``None`` 이면
                ``date.today()`` 자동 사용. HR Lead 가 사용자 confirm 후 박제.
            archived_reason: 해고 사유 1~2 문장. ``None`` 이면 ``""``.

        하위 구현이 override 한다.
        """

        raise NotImplementedError(
            f"{type(self).__name__} does not implement archive_worker"
        )

    # --- ADR-0006: audit log (default NotImplementedError, override 권장) ---

    def append_audit(self, json_line: str):
        """``.audit/decisions.jsonl`` 에 1줄 append. 디렉토리 부재 시 자동 생성.

        ``json_line`` 은 :meth:`lskun_kit.audit.AuditEntry.to_json_line` 의 결과 —
        검증된 single-line JSON. 본 ABC 는 path 책임만 갖고 schema 검증은 위임한다.

        하위 구현이 override 한다. MarkdownTreeAdapter 가 file 기반 구현 제공.
        """

        raise NotImplementedError(
            f"{type(self).__name__} does not implement append_audit"
        )
