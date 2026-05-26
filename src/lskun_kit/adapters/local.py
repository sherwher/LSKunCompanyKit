"""Local storage backend.

ADR-0001 §4 의 기본값 backend.

ADR-0015 (2026-05-22) — Local SSOT 단일화. 회사 자원의 물리적 위치는
``~/.lskun-companies/<name>/`` (``paths.py`` 가 단일 진입점). 이전의
``<project-root>/.company/`` 는 결정 1-A 로 폐기되었다 — SSOT / cache / mirror
무엇으로도 도입 금지.

레이아웃::

    ~/.lskun-companies/<name>/
        company.md
        hired/
            <worker>.md
            ...
        archived/    # ADR-0015 결정 7 — 해고된 워커 (frontmatter 보존)
        .audit/      # ADR-0006 — CPO 결재 audit log

호환성 (P86 기준):
    ``LocalAdapter`` 의 기존 인터페이스 (``LocalAdapter(root: Path)``) 는
    그대로 유지. P86 은 ``from_company_name(name)`` classmethod 만 추가하여
    호출자가 점진 전환할 수 있게 한다. ``init.py`` 의 root 결정 책임은 P87,
    ``hooks/session_start.py`` 는 P88 에서 본 classmethod 로 전환 예정.
"""

from __future__ import annotations

from pathlib import Path

from lskun_kit.adapters._markdown_tree import MarkdownTreeAdapter
from lskun_kit.paths import company_root


class LocalAdapter(MarkdownTreeAdapter):
    """``~/.lskun-companies/<name>/`` 또는 명시 절대경로를 root 로 쓰는 adapter.

    공통 동작은 :class:`MarkdownTreeAdapter` 에 위임한다. Local backend 는
    멀티 PC 동기화 / 외부 path resolution 같은 추가 동작이 없다.

    인스턴스화 방법:
        - 절대경로 명시: ``LocalAdapter(Path("/abs/path/to/company-root"))``
        - 회사 이름 (ADR-0015 권장): ``LocalAdapter.from_company_name("LSKun")``
    """

    @classmethod
    def from_company_name(cls, name: str) -> "LocalAdapter":
        """회사 이름으로 ``~/.lskun-companies/<name>/`` adapter 생성.

        ADR-0015 결정 1-A 의 단일 SSOT 진입점. 호출자는 회사 이름만 알면 되고
        물리적 위치는 ``paths.company_root(name)`` 이 단일 진실원.

        Args:
            name: 회사 이름. ``paths.validate_company_name`` 으로 검증됨.

        Returns:
            ``LocalAdapter`` 인스턴스. 디렉토리 자체는 자동 생성하지 않는다
            (생성 책임은 ``init.py`` — P87).

        Raises:
            ValueError: 회사 이름이 invalid (``paths.validate_company_name`` 위반).
        """

        return cls(company_root(name))
