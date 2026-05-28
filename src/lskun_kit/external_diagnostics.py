"""external doctor 진단 — ADR-0021 (doctor [32]).

external/ 구조 정합성 + cross-project leak 검증. plugin core 는 외주 내용을
해석하지 않는다 — 구조/frontmatter 일관성만 본다 (ADR-0009 범위 내).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lskun_kit import external, paths

#: frontmatter 에서 project 값 추출 (단순 라인 매칭 — 본문 해석 X).
_PROJECT_LINE = re.compile(r"^project:\s*(.+?)\s*$", re.MULTILINE)


@dataclass
class ExternalFindings:
    """external 진단 결과. doctor.md 가 사람이 읽을 줄로 렌더한다."""

    has_external: bool = False
    issues: list[str] = field(default_factory=list)

    def is_clean(self) -> bool:
        return not self.issues


def diagnose_external(company: str) -> ExternalFindings:
    """회사의 external/ 디렉토리 정합성 진단.

    검사:
        - external/ 부재 → clean (외주 미구성, opt-in)
        - 각 <project>/ 에 brief.md 존재 여부
        - 페르소나 frontmatter 의 project 가 디렉토리 이름과 일치 (cross-project leak)

    plugin core 는 외주 내용을 해석하지 않는다 — 구조/frontmatter 라인
    매칭만 (ADR-0009). read-only 진단이 크래시하면 안 되므로 read 실패는
    graceful 하게 흡수한다.
    """
    findings = ExternalFindings()
    ext_dir = paths.company_root(company) / external.EXTERNAL_DIRNAME
    if not ext_dir.exists():
        return findings  # clean, has_external=False

    findings.has_external = True
    for proj_dir in sorted(p for p in ext_dir.iterdir() if p.is_dir()):
        project = proj_dir.name
        if not (proj_dir / "brief.md").exists():
            findings.issues.append(f"[{project}] brief.md 누락")
        for kind_dir in (external.REDTEAM_DIRNAME, external.CUSTOMERS_DIRNAME):
            kd = proj_dir / kind_dir
            if not kd.exists():
                continue
            for md in sorted(kd.glob("*.md")):
                text = md.read_text(encoding="utf-8", errors="replace")
                m = _PROJECT_LINE.search(text)
                declared = m.group(1) if m else None
                if declared is not None and declared != project:
                    findings.issues.append(
                        f"[{project}] {md.name}: frontmatter project="
                        f"{declared!r} 가 디렉토리와 불일치 (cross-project leak 의심)"
                    )
    return findings


__all__ = ["ExternalFindings", "diagnose_external"]
