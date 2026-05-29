"""external doctor 진단 — ADR-0021 (doctor [32]).

external/ 구조 정합성 + cross-project leak 검증. plugin core 는 외주 내용을
해석하지 않는다 — 구조/frontmatter 일관성만 본다 (ADR-0009 범위 내).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

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
                try:
                    text = md.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue  # 읽기 실패 — graceful skip (진단은 절대 크래시하지 않는다)
                m = _PROJECT_LINE.search(text)
                declared = m.group(1) if m else None
                if declared is not None and declared != project:
                    findings.issues.append(
                        f"[{project}] {md.name}: frontmatter project="
                        f"{declared!r} 가 디렉토리와 불일치 (cross-project leak 의심)"
                    )
    return findings


def diagnose_external_setup(company: str) -> ExternalFindings:
    """외주 setup marker (``.external-setup.json``) 의 stale / 손상 검출 (doctor [33], ADR-0022).

    - marker 부재 → clean.
    - 살아있는 marker (24h 이내, schema 통과) → clean (정상 진행 중).
    - stale (24h 초과) → 정리 권장 issue.
    - malformed / schema 위반 → 손상 issue.

    read-only 진단은 절대 크래시하지 않는다 — read 실패는 graceful 흡수.
    """
    from lskun_kit import external_setup_state as state

    findings = ExternalFindings()
    p = state.marker_path(company)
    if not p.exists():
        return findings  # clean

    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        s = state.ExternalSetupState.from_dict(raw)
    except (json.JSONDecodeError, ValueError, OSError) as e:
        findings.issues.append(
            f"외주 setup marker 손상 (.external-setup.json): {e}. "
            "정리하려면 /lskun-kit:external cancel 또는 직접 rm."
        )
        return findings

    if s.is_stale():
        findings.issues.append(
            f"외주 setup marker 가 오래됨 (started_at={s.started_at.isoformat()}, "
            f"project={s.project}) — 24h 초과 stale. "
            "정리: /lskun-kit:external cancel."
        )
    return findings


#: zshrc/bashrc 등에서 검사할 env var 이름 (escape hatch).
_ENV_NAME = "LSKUN_ALLOW_EXTERNAL_HALT"
_ENV_FILES = (".zshrc", ".bashrc", ".zshenv", ".profile", ".bash_profile")
_ENV_GREP_PAT = re.compile(rf"^\s*export\s+{_ENV_NAME}=", re.MULTILINE)


def diagnose_external_env_export() -> ExternalFindings:
    """``~/.zshrc`` 등에 ``LSKUN_ALLOW_EXTERNAL_HALT`` 영구 export 검출 (doctor [34], ADR-0022).

    escape hatch 는 세션 단위로만 써야 하는데 rc 파일에 영구 export 되면 외주
    setup turn 차단 가드가 상시 무력화된다. read-only grep, 진단은 크래시하지 않는다.
    """
    findings = ExternalFindings()
    home = Path.home()
    for fname in _ENV_FILES:
        p = home / fname
        if not p.exists():
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue  # 읽기 실패 — graceful skip
        if _ENV_GREP_PAT.search(txt):
            findings.issues.append(
                f"~/{fname} 에 {_ENV_NAME} 영구 export 가 박혀있음. "
                "외주 setup turn 차단 가드를 상시 무력화함 (ADR-0022). "
                "세션 단위 export 로만 사용 권장."
            )
    return findings


__all__ = [
    "ExternalFindings",
    "diagnose_external",
    "diagnose_external_setup",
    "diagnose_external_env_export",
]
