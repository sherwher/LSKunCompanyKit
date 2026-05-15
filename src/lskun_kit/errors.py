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
