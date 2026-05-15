"""LSKunCompanyKit — AI workers that remember their work."""

from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.adapters.local import LocalAdapter
from lskun_kit.errors import (
    LSKunKitError,
    SSOTContaminationError,
    WorkerNotFoundError,
    InvalidWorkerSchemaError,
)
from lskun_kit.models import Company, HistoryEntry, Worker

__version__ = "0.1.0-dev"

__all__ = [
    "__version__",
    "StorageAdapter",
    "LocalAdapter",
    "Company",
    "HistoryEntry",
    "Worker",
    "LSKunKitError",
    "SSOTContaminationError",
    "WorkerNotFoundError",
    "InvalidWorkerSchemaError",
]
