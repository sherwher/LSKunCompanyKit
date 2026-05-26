"""LSKunCompanyKit — Domain-expert AI workers, hired complete (ADR-0014).

ADR-0015 (2026-05-22) — Vault backend 폐기. 단일 SSOT 는 Local
(``~/.lskun-companies/<name>/``). Vault 통합은 sync 명령 (P90) 의 파일시스템
복사로만 제공. ``VaultAdapter`` 등 외부 노출 심볼 제거.
"""

from __future__ import annotations

import json
from pathlib import Path

from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.adapters.local import LocalAdapter
from lskun_kit.audit import (
    AuditEntry,
    AuditError,
    new_request_id,
)
from lskun_kit import org, persona_sync
from lskun_kit.errors import (
    InvalidWorkerSchemaError,
    LSKunKitError,
    SSOTContaminationError,
    WorkerNotFoundError,
)
from lskun_kit.models import Company, Worker


def _read_plugin_version() -> str:
    """plugin.json 에서 version 을 동적 산출 (ADR-0012 — 단일 SSOT).

    `src/lskun_kit/__init__.py` 기준 `../../.claude-plugin/plugin.json` 을 읽는다.
    parse 실패 시 `"0.0.0+unknown"` fallback (정상 환경에서는 발생 X).
    """
    candidate = (
        Path(__file__).resolve().parent.parent.parent
        / ".claude-plugin"
        / "plugin.json"
    )
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "0.0.0+unknown"
    v = data.get("version")
    return v if isinstance(v, str) and v else "0.0.0+unknown"


__version__ = _read_plugin_version()

__all__ = [
    "__version__",
    "StorageAdapter",
    "LocalAdapter",
    "Company",
    "Worker",
    "LSKunKitError",
    "SSOTContaminationError",
    "WorkerNotFoundError",
    "InvalidWorkerSchemaError",
    "AuditEntry",
    "AuditError",
    "new_request_id",
    "org",
    "persona_sync",
]
