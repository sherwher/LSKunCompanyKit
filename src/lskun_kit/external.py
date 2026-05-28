"""외주 (레드팀 / 고객) 경로 단일 진입점 — ADR-0021.

회사 SSOT 하위 ``external/<project>/`` 에 외주 자산을 둔다. paths.py 의
``company_root`` 위에 조립하여 단일 루트를 유지한다 (3번째 SSOT 금지, ADR-0008).

ADR-0009 정합: 외부 SDK / 네트워크 0건. stdlib pathlib / re 만.
"""

from __future__ import annotations

import re
from pathlib import Path

from lskun_kit import paths

#: 외주 디렉토리 이름 (회사 SSOT 하위, hired/ 와 형제).
EXTERNAL_DIRNAME = "external"

#: 외주 유형 디렉토리.
REDTEAM_DIRNAME = "redteam"
CUSTOMERS_DIRNAME = "customers"

#: 프로젝트 이름 검증 — company 패턴보다 엄격 (dot 전면 금지: a..b 차단).
#: ASCII 영문/숫자/`-`/`_` 만, 시작은 영문/숫자, 최대 64자.
_PROJECT_NAME_PAT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def validate_project_name(name: str) -> None:
    """프로젝트 이름 검증. invalid 면 ValueError.

    company 검증보다 엄격하게 dot 을 전면 금지한다 (``a..b`` 같은 traversal
    표면 제거 — security C1).
    """
    if not isinstance(name, str) or not _PROJECT_NAME_PAT.match(name):
        raise ValueError(
            f"invalid project name: {name!r} "
            f"(허용: ^[A-Za-z0-9][A-Za-z0-9_-]{{0,63}}$)"
        )


def external_root(company: str, project: str) -> Path:
    """``~/.lskun-companies/<company>/external/<project>/`` 절대경로.

    company 검증은 paths.company_root 가, project 검증은 본 함수가 수행.
    디렉토리 생성은 호출자 책임.
    """
    co_root = paths.company_root(company)  # company 검증 포함
    validate_project_name(project)
    return co_root / EXTERNAL_DIRNAME / project


#: 페르소나 파일 이름 검증 — 워커와 동일 allowlist (lowercase).
_PERSONA_NAME_PAT = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

#: persona_path 의 kind 인자는 디렉토리 이름(redteam/customers) 또는 단수형(redteam/customer)
#: 둘 다 수용 — 호출자 편의. 내부에서 정규화.
_KIND_DIR_ALIASES = {
    "redteam": REDTEAM_DIRNAME,
    "customers": CUSTOMERS_DIRNAME,
    "customer": CUSTOMERS_DIRNAME,
}


def _resolve_kind_dir(kind: str) -> str:
    if not isinstance(kind, str) or kind not in _KIND_DIR_ALIASES:
        raise ValueError(
            f"invalid external kind: {kind!r} (허용: redteam | customer[s])"
        )
    return _KIND_DIR_ALIASES[kind]


def persona_path(company: str, project: str, kind: str, name: str) -> Path:
    """외주 페르소나 파일 경로. 이름 검증 + traversal 격리.

    Raises:
        ValueError: kind / name invalid 또는 external_root 밖으로 escape.
    """
    root = external_root(company, project)
    kind_dir = _resolve_kind_dir(kind)
    if not isinstance(name, str) or not _PERSONA_NAME_PAT.match(name):
        raise ValueError(
            f"invalid persona name: {name!r} "
            f"(허용: ^[a-z0-9][a-z0-9_-]{{0,63}}$)"
        )
    candidate = root / kind_dir / f"{name}.md"
    try:
        resolved = candidate.resolve(strict=False)
        root_resolved = root.resolve(strict=False)
        if not resolved.is_relative_to(root_resolved):
            raise ValueError(f"persona path escapes external root: {resolved}")
    except (OSError, RuntimeError) as e:
        raise ValueError(f"failed to resolve persona path: {name!r} ({e})")
    return candidate


def brief_path(company: str, project: str) -> Path:
    """프로젝트 brief.md 경로 (외주들이 공유하는 SSOT 1개)."""
    return external_root(company, project) / "brief.md"


def list_external_personas(company: str, project: str, kind: str) -> list[str]:
    """주어진 kind 디렉토리의 ``*.md`` 페르소나 이름 (정렬). 부재 시 빈 리스트."""
    kind_dir = _resolve_kind_dir(kind)
    d = external_root(company, project) / kind_dir
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.md") if p.is_file())


def external_templates_dir() -> Path:
    """외주 template (redteam.md, customer.md) 의 plugin repo root 위치.

    메타 워커 template (``src/lskun_kit/templates/``) 과 분리된 위치 — 저장소
    root 의 ``templates/``. SSOT 분리 (plugin 자산 vs 외주 페르소나) 의도
    (ADR-0021, Task 7).

    Raises:
        RuntimeError: external.py 가 이동되어 ``parents[2]`` 가 plugin repo
            root 가 아닌 곳을 가리키게 된 경우 (silent breakage 방지).
    """
    # external.py 는 src/lskun_kit/external.py 이므로 parents[2] = 저장소 root.
    d = Path(__file__).resolve().parents[2] / "templates"
    # Sanity: plugin repo root 에는 반드시 src/ 가 형제로 존재.
    if not (d.parent / "src").is_dir():
        raise RuntimeError(
            f"external_templates_dir miscalculated: {d} "
            "(external.py 가 이동되었을 수 있음 — parents[2] 가정 위반)"
        )
    return d


def external_template_path(kind: str) -> Path:
    """``redteam`` 또는 ``customer`` 의 template 파일 경로.

    Raises:
        ValueError: kind 가 redteam / customer[s] 외인 경우.
    """
    kind_dir = _resolve_kind_dir(kind)
    # kind_dir 은 "redteam" / "customers" (복수). template 파일명은 단수형.
    fname = "redteam.md" if kind_dir == REDTEAM_DIRNAME else "customer.md"
    return external_templates_dir() / fname


__all__ = [
    "EXTERNAL_DIRNAME",
    "REDTEAM_DIRNAME",
    "CUSTOMERS_DIRNAME",
    "validate_project_name",
    "external_root",
    "persona_path",
    "brief_path",
    "list_external_personas",
    "external_templates_dir",
    "external_template_path",
]
