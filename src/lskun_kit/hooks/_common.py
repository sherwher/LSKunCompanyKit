"""hook 공통 헬퍼 (ADR-0022, P121 Task 3).

``post_tool_use_external`` 과 ``stop_external`` 두 hook 가 동일한 "활성 회사
root 검출" 로직을 쓰므로 본 모듈로 추출한다. ``pre_tool_use.py`` 의 원래
로직과 동치 — 의도적 회귀 없음.

ADR-0009 정합: stdlib only (os / pathlib).
"""

from __future__ import annotations

import os
from pathlib import Path

#: 활성 회사 SSOT root 를 O(1) 로 알려주는 env var (hooks 가 1순위로 참조).
ENV_SSOT_ROOT = "LSKUN_SSOT_ROOT"


def detect_company_root() -> "Path | None":
    """활성 회사 root 검출.

    1순위: ``LSKUN_SSOT_ROOT`` env var (O(1)). 경로가 실재하면 그 Path,
           아니면 ``None``.
    2순위: cwd 상위 CLAUDE.md marker 직접 검출 (session_start 재사용).
           ``session_start`` import 실패 시 ``None``.
    """

    env_root = os.environ.get(ENV_SSOT_ROOT, "").strip()
    if env_root:
        path = Path(env_root)
        return path if path.exists() else None

    try:
        from lskun_kit.hooks.session_start import _find_active_company_root  # type: ignore[attr-defined]
    except ImportError:
        return None
    return _find_active_company_root()


__all__ = ["ENV_SSOT_ROOT", "detect_company_root"]
