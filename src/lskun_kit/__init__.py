"""LSKunCompanyKit — AI workers that remember their work."""

from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.adapters.local import LocalAdapter
from lskun_kit.adapters.vault import (
    VaultAdapter,
    VaultCompanyNotFoundError,
    list_companies,
)
from lskun_kit.audit import (
    AuditEntry,
    AuditError,
    new_request_id,
)
from lskun_kit.project_link import (
    ProjectLink,
    ProjectLinkError,
)
from lskun_kit.errors import (
    InvalidWorkerSchemaError,
    LSKunKitError,
    SSOTContaminationError,
    WorkerNotFoundError,
)
from lskun_kit.models import Company, HistoryEntry, Worker

__version__ = "0.6.0-dev"

__all__ = [
    "__version__",
    "StorageAdapter",
    "LocalAdapter",
    "VaultAdapter",
    "VaultCompanyNotFoundError",
    "list_companies",
    "Company",
    "HistoryEntry",
    "Worker",
    "LSKunKitError",
    "SSOTContaminationError",
    "WorkerNotFoundError",
    "InvalidWorkerSchemaError",
    "AuditEntry",
    "AuditError",
    "new_request_id",
    "ProjectLink",
    "ProjectLinkError",
]
