"""Reflection 인용율 추정 — ADR-0001 §검증 KPI 의 핵심 지표.

목표: "워커가 다음 작업에서 자기 history 를 의미있게 인용하는가" 를
정량화한다. v0.1 은 LLM-as-judge 대신 단순 keyword overlap 기반.

알고리즘 (v0.1):
    1. 워커 history 의 최근 N줄에서 pattern / topic 키워드를 추출
    2. 해당 워커의 응답 텍스트에서 키워드가 등장하는 줄 비율을 계산
    3. 키워드가 한 번이라도 등장하면 "인용" 으로 친다 (binary)
    4. citation_rate = (인용 발생 횟수) / (측정 윈도우 작업 수)

v1.0 에서는 LLM 이 의미 인용 여부를 판정하도록 교체 예정.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from lskun_kit.adapters.base import StorageAdapter
from lskun_kit.adapters._markdown_tree import HISTORY_HEADING

_STOPWORDS = {
    "the", "a", "an", "of", "in", "for", "to", "with", "by",
    "and", "or", "not", "is", "are", "was", "were", "be", "this", "that",
}
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9\-_]+")


@dataclass(frozen=True)
class CitationReport:
    worker: str
    sampled_responses: int
    cited_responses: int
    keywords: list[str]

    @property
    def rate(self) -> float:
        if self.sampled_responses == 0:
            return 0.0
        return self.cited_responses / self.sampled_responses


def extract_keywords(adapter: StorageAdapter, worker: str, recent: int = 10) -> list[str]:
    """워커 history 의 최근 N줄에서 pattern / topic 토큰을 추출한다."""

    body = adapter.read_worker(worker).body
    if HISTORY_HEADING not in body:
        return []

    keywords: list[str] = []
    seen: set[str] = set()
    after = body.split(HISTORY_HEADING, 1)[1]
    lines: list[str] = []
    for raw in after.splitlines():
        stripped = raw.strip()
        if stripped.startswith("## "):
            break
        if stripped.startswith("- "):
            lines.append(stripped)

    for line in lines[-recent:]:
        # 포맷: "- date / project / topic / pattern / first-pass N%"
        parts = [p.strip() for p in line[1:].split("/")]
        if len(parts) < 5:
            continue
        for cell in (parts[2], parts[3]):  # topic, pattern
            for token in _TOKEN_RE.findall(cell.lower()):
                if token in _STOPWORDS or len(token) < 3:
                    continue
                if token in seen:
                    continue
                seen.add(token)
                keywords.append(token)
    return keywords


def estimate_citation_rate(
    adapter: StorageAdapter,
    worker: str,
    responses: list[str],
    recent: int = 10,
) -> CitationReport:
    """주어진 응답 텍스트들에 대해 인용율을 추정한다.

    각 응답에서 워커 키워드가 한 번이라도 등장하면 "인용" 으로 친다.
    """

    keywords = extract_keywords(adapter, worker, recent=recent)
    if not keywords:
        return CitationReport(worker, len(responses), 0, keywords)

    cited = 0
    for response in responses:
        lowered = response.lower()
        if any(kw in lowered for kw in keywords):
            cited += 1

    return CitationReport(worker, len(responses), cited, keywords)
