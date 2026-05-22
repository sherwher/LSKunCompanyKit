"""Local storage backend — ``<project-root>/.company/``.

ADR-0001 §4 의 기본값 backend. Vault 의존성 없이 단일 프로젝트 단위로
워커 history 를 누적한다.

레이아웃::

    <root>/
        company.md
        hired/
            <worker>.md
            ...
"""

from __future__ import annotations

from lskun_kit.adapters._markdown_tree import MarkdownTreeAdapter


class LocalAdapter(MarkdownTreeAdapter):
    """``<root>/.company/`` 디렉토리에 회사 운영 데이터를 보관하는 adapter.

    공통 동작은 :class:`MarkdownTreeAdapter` 에 위임한다. Local backend 는
    추가 동작 (멀티 PC 동기화, 외부 path resolution) 이 없으므로 선언만 한다.
    """
