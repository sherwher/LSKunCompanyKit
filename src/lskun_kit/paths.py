"""Local SSOT 경로 단일 진입점 — ADR-0015 결정 1-A.

ADR-0015 (2026-05-22) — Plugin core 가 회사 자원의 물리적 위치를 결정하는
유일한 모듈. 호출자 (init.py / hooks / cli_org / sync.py / permissions.py)
는 본 모듈만 import 하여 경로를 얻는다.

박제 사항 (ADR-0015 결정 1-A):
    - Local SSOT 단일 위치: ``~/.lskun-companies/<name>/``
    - ``<project>/.company/`` 의 모든 형태 금지 (SSOT / cache / mirror 무엇으로도)
    - ``$LSKUN_VAULT`` env var 의 plugin core 참조 금지 — sync 명령의 인자로만
    - Backup 통합 위치: ``~/.lskun-companies/.backups/<name>/<timestamp>/``
      (회사 SSOT 디렉토리 외부, 결정 5-E)

ADR-0009 정합:
    - 외부 SDK / API 호출 0건 (Python stdlib ``pathlib`` 만 사용)
    - 절대경로 expand 는 ``os.path.expanduser`` 가 아닌 ``Path.expanduser``
      로 수행 (cross-platform 안전)

호환성 (P86 기준):
    - P86 시점: 본 모듈 신규 박제. 호출자 전환은 아직 안 됨.
    - P87 시점: ``init.py`` 가 본 모듈로 전환.
    - P88 시점: ``hooks/session_start.py`` 가 본 모듈로 전환.
    - P90 시점: ``sync.py`` 가 본 모듈로 전환.
"""

from __future__ import annotations

import re
from pathlib import Path

#: Local SSOT 루트 디렉토리 이름 (홈 기준 상대). 변경 금지 — 외부 사용자가
#: 본 경로에 대한 settings.json 권한을 박제하므로 (ADR-0015 결정 4).
LSKUN_COMPANIES_DIRNAME = ".lskun-companies"

#: Backup 통합 위치 디렉토리 이름. 회사 SSOT 디렉토리와 같은 레벨에 별도.
#: (결정 5-E — 회사 SSOT 디렉토리 안에 backup 박제 금지)
BACKUPS_DIRNAME = ".backups"

#: 회사 이름 검증 패턴. OS filesystem 안전 + path traversal 차단.
#: ASCII 영문/숫자/`-`/`_`/`.` 만 허용, 시작은 영문/숫자.
#: dot-prefix 금지 (백업 디렉토리 ``.backups/`` 와 충돌 방지).
_COMPANY_NAME_PAT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def lskun_companies_root() -> Path:
    """Local SSOT 의 최상위 디렉토리 (``~/.lskun-companies/``).

    호출자는 본 함수 외 ``Path.home() / ".lskun-companies"`` 같은 hardcode
    금지. 본 함수가 단일 진입점.

    Returns:
        절대경로. 디렉토리 자체는 생성하지 않는다 (호출자 책임).
    """

    return Path.home() / LSKUN_COMPANIES_DIRNAME


def company_root(name: str) -> Path:
    """주어진 회사 이름에 대응하는 SSOT 루트 (``~/.lskun-companies/<name>/``).

    Args:
        name: 회사 이름. ``_COMPANY_NAME_PAT`` 검증 통과 필수.

    Returns:
        절대경로. 디렉토리 자체는 생성하지 않는다 (호출자 책임).

    Raises:
        ValueError: 회사 이름이 검증 패턴에 맞지 않거나 예약어 (``.backups``)
                    일 때.
    """

    validate_company_name(name)
    return lskun_companies_root() / name


def backup_root(name: str) -> Path:
    """주어진 회사의 백업 통합 위치 (``~/.lskun-companies/.backups/<name>/``).

    결정 5-E — sync-in / sync-out 의 백업은 회사 SSOT 디렉토리 외부의
    통합 위치에 적재. plugin 자동 삭제 / rotation 없음 (사용자 책임).

    Args:
        name: 회사 이름. ``_COMPANY_NAME_PAT`` 검증 통과 필수.

    Returns:
        절대경로 (``<name>`` 까지). timestamp 하위 디렉토리는 호출자가 생성.
    """

    validate_company_name(name)
    return lskun_companies_root() / BACKUPS_DIRNAME / name


#: 예약어 — 회사 이름으로 사용 금지. ``.backups`` 가 dot-prefix 라 regex 가
#: 이미 차단하지만 명시성 + 향후 다른 예약어 추가 대비. ``backups`` (no dot) 도
#: 안전 차단.
_RESERVED_COMPANY_NAMES = frozenset({".", "..", BACKUPS_DIRNAME, "backups"})


def validate_company_name(name: str) -> None:
    """회사 이름 검증. invalid 면 ``ValueError`` raise.

    검증 항목 (순서 중요):
        1. 예약어 (``.backups`` / ``backups`` / ``.`` / ``..``) 차단
        2. ``_COMPANY_NAME_PAT`` 매칭 (영문/숫자/_/-/. + 시작 영문/숫자, 최대 128자)

    Raises:
        ValueError: 검증 실패. 메시지에 ``reserved`` 또는 ``invalid`` 포함.
    """

    if isinstance(name, str) and name in _RESERVED_COMPANY_NAMES:
        raise ValueError(
            f"reserved company name: {name!r} (예약어 또는 path traversal)"
        )
    if not isinstance(name, str) or not _COMPANY_NAME_PAT.match(name):
        raise ValueError(
            f"invalid company name: {name!r} "
            f"(허용 패턴: ^[A-Za-z0-9][A-Za-z0-9_.-]{{0,127}}$)"
        )


def list_companies() -> list[str]:
    """``~/.lskun-companies/`` 의 직속 하위 디렉토리 목록 (정렬).

    제외:
        - ``.backups/`` (백업 통합 위치)
        - dot-prefix 디렉토리 (사용자가 직접 만든 메타 디렉토리)
        - 파일 (디렉토리만)

    Returns:
        회사 이름 목록. 루트가 부재면 빈 리스트.
    """

    root = lskun_companies_root()
    if not root.exists():
        return []
    return sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


__all__ = [
    "LSKUN_COMPANIES_DIRNAME",
    "BACKUPS_DIRNAME",
    "lskun_companies_root",
    "company_root",
    "backup_root",
    "validate_company_name",
    "list_companies",
]
