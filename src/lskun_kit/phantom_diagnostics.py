"""유령참조(Phantom Reference) 진단 helper (P122, ADR-0023 — doctor [35][36][37]).

진실원 = 파일명 stem. frontmatter name 은 파생. read-only 진단 — 자동 수정 X.

검출 3종:
    - name_mismatch  : 파일명 stem != frontmatter name (치명적 — dispatch 깨짐).
    - orphan_audit   : hired/.audit.jsonl 에 hire 기록 있으나 hired/<name>.md 부재.
    - file_only      : 파일은 있으나 audit 없음 (사용자 직접 hire — 정상, 정보용).
    - dangling_skills: 워커 skills 토큰이 가리키는 skills/<name>.md 부재.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lskun_kit import hire_audit
from lskun_kit.adapters._markdown_tree import MarkdownTreeAdapter
from lskun_kit.context import _split_skills
from lskun_kit.errors import LSKunKitError


@dataclass
class PhantomDiagnostics:
    """[35][36][37] 진단 결과. doctor.md 가 사람이 읽을 줄로 렌더한다."""

    #: (stem, frontmatter_name) — 파일명과 frontmatter name 불일치 (치명적).
    name_mismatch: list[tuple[str, str]] = field(default_factory=list)
    #: audit 엔 hire 기록 있으나 파일 부재 (고아 audit, 경고).
    orphan_audit: list[str] = field(default_factory=list)
    #: 파일은 있으나 audit 없음 (정상 — 사용자 직접 hire, 정보용).
    file_only: list[str] = field(default_factory=list)
    #: (worker, skill) — 선언됐으나 skills/<name>.md 부재 (경고).
    dangling_skills: list[tuple[str, str]] = field(default_factory=list)

    def has_critical(self) -> bool:
        return bool(self.name_mismatch)

    def has_warning(self) -> bool:
        return bool(self.orphan_audit or self.dangling_skills)


def diagnose_phantom(adapter: MarkdownTreeAdapter) -> PhantomDiagnostics:
    """파일명 stem ↔ frontmatter name ↔ 채용 audit ↔ skills 정합성 진단.

    read-only. 손상된 워커 / 부재 디렉토리는 graceful — 크래시하지 않는다.
    """

    result = PhantomDiagnostics()
    stems = adapter.list_workers()  # 파일명 stem 집합 (진실원)

    for stem in stems:
        # name_mismatch — read_worker 는 frontmatter name 을 반환하므로 비교.
        try:
            worker = adapter.read_worker(stem)
        except LSKunKitError:
            # 손상 워커 (frontmatter 누락 등) 는 doctor [5] 가 잡음. 여기선 skip.
            continue
        if worker.name != stem:
            result.name_mismatch.append((stem, worker.name))

        # dangling_skills — 선언 토큰이 가리키는 파일 존재 확인.
        skill_path = getattr(adapter, "skill_path", None)
        if skill_path is not None:
            for tok in _split_skills(getattr(worker, "skills", None)):
                try:
                    exists = skill_path(tok).exists()
                except ValueError:
                    # invalid 이름은 skills_diagnostics [31] 가 잡음. 여기선 skip.
                    continue
                if not exists:
                    result.dangling_skills.append((stem, tok))

    # orphan_audit / file_only — 채용 audit 의 name 집합 vs 파일 stem 집합 대조.
    stem_set = set(stems)
    audit_names = {ev.name for ev in hire_audit.read_events(adapter.root)}
    for name in sorted(audit_names - stem_set):
        result.orphan_audit.append(name)
    for stem in sorted(stem_set - audit_names):
        result.file_only.append(stem)

    return result


__all__ = ["PhantomDiagnostics", "diagnose_phantom"]
