"""LSKunCompanyKit 의 모든 예외는 LSKunKitError 를 상속한다."""


class LSKunKitError(Exception):
    """모든 LSKunCompanyKit 예외의 base."""


class SSOTContaminationError(LSKunKitError):
    """개발자 SSOT 위치를 사용자 SSOT 로 사용하려 할 때 발생.

    ADR-0001 §5 의 SSOT 분리 정책을 강제하기 위한 가드.
    """


class WorkerNotFoundError(LSKunKitError):
    """hired/<name>.md 가 존재하지 않을 때 발생."""


class InvalidWorkerSchemaError(LSKunKitError):
    """워커 frontmatter 가 필수 필드 (name/role/hired_at/storage_backend) 를 빠뜨릴 때 발생."""


class WorkerArchivedError(LSKunKitError):
    """워커가 ``archived/`` 에만 존재하고 ``hired/`` 에는 없을 때 발생.

    ADR-0015 결정 7-E — dispatch 가드. archived 워커는 라우팅 후보에서 제외되고
    dispatch 시도도 거부. 재채용은 ``/lskun-kit:work hr-lead "<role> 재채용"`` 으로.

    속성:
        - worker_name: 시도된 워커 이름
        - archived_at: archived 파일의 frontmatter 에서 추출한 해고일 (ISO 문자열)
                       또는 ``None`` (frontmatter 부재 시)
        - hint: 사용자에게 보여줄 1줄 안내
    """

    def __init__(
        self, worker_name: str, archived_at: str | None = None,
    ) -> None:
        date_part = (
            f" ({archived_at} 해고됨)" if archived_at else " (해고됨)"
        )
        msg = (
            f"worker '{worker_name}' is archived{date_part}. "
            f"재채용은 `/lskun-kit:work hr-lead \"{worker_name} 재채용\"` 으로 진행하세요."
        )
        super().__init__(msg)
        self.worker_name = worker_name
        self.archived_at = archived_at
        self.hint = msg


class ConfirmRequired(LSKunKitError):
    """사용자 confirm 이 필요한 작업이 confirm 없이 호출됐을 때 발생.

    ADR-0015 결정 2-B + 3-A — Plugin core 는 stdin 을 잡지 않는다. confirm 이
    필요한 분기에서는 본 예외를 raise 하고, caller (slash command 의 LLM) 가
    사용자에게 묻고 ``confirmed_*=True`` 인자와 함께 재호출한다.

    속성 (caller 가 prompt 메시지를 구성하는 데 사용):
        - kind: "marker_replace" | "permissions" | "sync_overwrite" 등 (확장 가능)
        - prompt: 사용자에게 보여줄 1줄 질문 (Korean)
        - context: caller 가 추가 표시할 수 있는 dict (예: 회사 이름)
    """

    def __init__(self, kind: str, prompt: str, context: dict | None = None) -> None:
        super().__init__(prompt)
        self.kind = kind
        self.prompt = prompt
        self.context = context or {}
