"""Stop hook — Claude Code 가 작업을 종료할 때 호출되는 reflection 자동화.

세션 상태에 활성 워커가 있고, 환경변수로 reflection 필드가 채워져 있으면
:func:`lskun_kit.reflection.record` 를 호출해 history 1줄을 append 한다.

세션 상태가 없거나 필수 필드가 누락되면 silent no-op — 사용자가 본 hook 을
의도적으로 사용하지 않는 워크플로 (직접 ``/lskun-kit:reflect`` 호출) 도 지원하기 위함.

환경변수 입력:
    LSKUN_SSOT_ROOT     사용자 SSOT root (Local: <proj>/.company, Vault: <vault>/03_Companies/<co>)
    LSKUN_PROJECT       프로젝트명 (필수)
    LSKUN_TOPIC         이번 작업 주제 (필수)
    LSKUN_PATTERN       적용한 핵심 패턴 (필수)
    LSKUN_FIRST_PASS    1차 통과율 0..100 (필수)
    LSKUN_OUTCOME       "success" (default) | "aborted" — P30 진실성 가드.
                        "aborted" 면 history 박제 skip 후 세션만 정리.

종료 코드:
    0  reflection 기록됨 또는 의도적 no-op (조용히 종료)
    2  필드는 일부 채워졌으나 검증 실패 — Claude Code 에 stderr 로 알린다
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    root = os.environ.get("LSKUN_SSOT_ROOT")
    if not root:
        return 0  # plugin 비활성 환경 — no-op

    from lskun_kit import session  # 지연 import
    from lskun_kit.adapters.local import LocalAdapter
    from lskun_kit.adapters.vault import VaultAdapter
    from lskun_kit.reflection import (
        OUTCOME_ABORTED,
        OUTCOME_SUCCESS,
        ReflectionSkipped,
        record,
    )

    sess = session.read(root)
    if sess is None:
        return 0  # 활성 워커 없음

    outcome = (os.environ.get("LSKUN_OUTCOME") or OUTCOME_SUCCESS).strip().lower()
    if outcome == OUTCOME_ABORTED:
        # P30 — 진실성 가드: 작업 중단·실패시 박제 skip 하고 세션만 정리.
        session.clear(root)
        return 0

    project = os.environ.get("LSKUN_PROJECT")
    topic = os.environ.get("LSKUN_TOPIC")
    pattern = os.environ.get("LSKUN_PATTERN")
    score_raw = os.environ.get("LSKUN_FIRST_PASS")

    if not all([project, topic, pattern, score_raw]):
        # 사용자가 환경변수로 reflection 을 제공하지 않은 경우 — 의도적 silent.
        # 명시 reflection 워크플로 (/lskun-kit:reflect) 만 쓰는 사용자도 있다.
        return 0

    try:
        score = int(score_raw)
    except ValueError:
        print(f"lskun-kit: invalid LSKUN_FIRST_PASS={score_raw!r}", file=sys.stderr)
        return 2

    adapter = _make_adapter(Path(root))
    try:
        record(
            adapter, sess.active_worker, project, topic, pattern, score,
            outcome=outcome,
        )
    except ReflectionSkipped:
        # outcome 검증을 위 if 에서 처리하므로 정상 흐름상 도달 불가.
        # 방어적 가드만 유지 — 세션 정리하고 silent exit.
        pass
    except Exception as exc:
        print(f"lskun-kit: reflection failed: {exc}", file=sys.stderr)
        return 2

    session.clear(root)
    return 0


def _make_adapter(root: Path):
    """root 가 ``03_Companies/<co>`` 모양이면 VaultAdapter, 아니면 LocalAdapter."""

    from lskun_kit.adapters.local import LocalAdapter
    from lskun_kit.adapters.vault import COMPANIES_DIRNAME, VaultAdapter

    parent = root.parent
    if parent.name == COMPANIES_DIRNAME and parent.parent.exists():
        return VaultAdapter(parent.parent, root.name)
    return LocalAdapter(root)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
