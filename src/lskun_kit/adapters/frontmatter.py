"""의존성 0 의 간이 YAML frontmatter 파서.

PyYAML 같은 외부 의존성을 들이지 않기 위해 LSKunCompanyKit 용으로 필요한
최소 문법만 지원한다:

- ``key: value`` 형태의 평탄한 매핑
- 값은 문자열로 읽고 호출자가 캐스팅
- ``# comment`` 라인 무시
- 따옴표 (``"..."`` / ``'...'``) 만 단순 제거

복합 YAML (블록 시퀀스 / nested / multiline) 은 의도적으로 지원하지 않는다.
워커 / 회사 frontmatter 는 평탄한 key-value 만 사용하기로 ADR-0001 §3 단계에서 합의.
"""

from __future__ import annotations

from typing import NamedTuple


class ParsedDocument(NamedTuple):
    frontmatter: dict[str, str]
    body: str


def parse(text: str) -> ParsedDocument:
    """``---`` 펜스로 둘러싸인 frontmatter 와 본문을 분리한다.

    frontmatter 가 없으면 빈 dict 와 원본 텍스트를 반환한다.
    """

    if not text.startswith("---"):
        return ParsedDocument({}, text)

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return ParsedDocument({}, text)

    end_index = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            end_index = i
            break

    if end_index is None:
        return ParsedDocument({}, text)

    fm_text = "".join(lines[1:end_index])
    body = "".join(lines[end_index + 1 :])
    return ParsedDocument(_parse_mapping(fm_text), body.lstrip("\n"))


def dump(frontmatter: dict[str, str], body: str) -> str:
    """frontmatter dict + 본문을 다시 markdown 문자열로 직렬화."""

    if not frontmatter:
        return body
    rendered = "---\n"
    for key, value in frontmatter.items():
        rendered += f"{key}: {value}\n"
    rendered += "---\n"
    if body and not body.startswith("\n"):
        rendered += "\n"
    rendered += body
    return rendered


def _parse_mapping(fm_text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_line in fm_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        result[key.strip()] = _strip_quotes(value.strip())
    return result


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value
