"""skills/ 정합성 진단 helper (ADR-0020, P111 — doctor [31]).

doctor.md 의 [31] 항목이 호출하는 얇은 read-only helper. ADR-0006 정신 —
평가/점수/랭킹 0, 사실만 표시. core 는 skills 를 해석하지 않고 존재/이름
정합성만 본다.

검출 4종 (양방향, M4):
    - dangling : 워커가 선언했으나 skills/<name>.md 부재.
    - orphan   : skills/ 에 파일은 있으나 어느 워커도 선언 안 함 (죽은 자산).
    - invalid  : skill 이름이 allowlist 위반 (path traversal 표면).
    - meta     : 메타 워커 (cpo/hr-lead) 에 skills 가 박힘 (비워둠 권장).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from lskun_kit.adapters._markdown_tree import _SKILL_NAME_PAT, MarkdownTreeAdapter
from lskun_kit.context import _split_skills
from lskun_kit.models import META_DOMAIN

#: 메타 워커 이름 (skills 비워둠 권장 대상).
_META_WORKER_NAMES = frozenset({"cpo", "hr-lead"})


@dataclass
class SkillsDiagnostics:
    """[31] 진단 결과. doctor.md 가 사람이 읽을 줄로 렌더한다."""

    #: (worker, skill) — 선언됐으나 파일 부재.
    dangling: list[tuple[str, str]] = field(default_factory=list)
    #: skill 이름 — 파일은 있으나 선언 워커 0.
    orphan: list[str] = field(default_factory=list)
    #: (worker, skill) — 이름 allowlist 위반.
    invalid: list[tuple[str, str]] = field(default_factory=list)
    #: (worker, skill) — 메타 워커에 박힌 skills.
    meta_declared: list[tuple[str, str]] = field(default_factory=list)

    def is_clean(self) -> bool:
        return not (
            self.dangling or self.orphan or self.invalid or self.meta_declared
        )


def diagnose_skills(adapter: MarkdownTreeAdapter) -> SkillsDiagnostics:
    """모든 워커의 skills 선언과 skills/ 파일을 대조해 정합성 진단.

    Args:
        adapter: ``list_workers`` / ``read_worker`` / ``list_skills`` /
                 ``skill_path`` 를 제공하는 adapter (MarkdownTreeAdapter 계열).

    Returns:
        :class:`SkillsDiagnostics`. 부재 디렉토리 등은 빈 결과로 graceful.
    """

    result = SkillsDiagnostics()
    declared: set[str] = set()  # 유효 이름으로 선언된 skill (orphan 계산용)

    for worker_name in adapter.list_workers():
        worker = adapter.read_worker(worker_name)
        tokens = _split_skills(getattr(worker, "skills", None))
        if not tokens:
            continue

        # 메타 판정: domain == META_DOMAIN 가 정식 기준. 이름 frozenset 은
        # domain 미박제 레거시 워커 (구 schema) 방어용 OR 조건 (N-2).
        if worker_name in _META_WORKER_NAMES or worker.domain == META_DOMAIN:
            for tok in tokens:
                result.meta_declared.append((worker_name, tok))
            # 메타 워커 선언은 orphan/dangling 계산에 포함하지 않음.
            continue

        for tok in tokens:
            if not _SKILL_NAME_PAT.match(tok):
                result.invalid.append((worker_name, tok))
                continue
            # 정규식 통과해도 skill_path 의 2차 가드 (resolve-escape, symlink 등)
            # 가 ValueError 를 던질 수 있다. build_skills_block 과 동일하게
            # invalid 로 분류 — read-only 진단이 크래시하면 안 된다 (C-1).
            try:
                exists = adapter.skill_path(tok).exists()
            except ValueError:
                result.invalid.append((worker_name, tok))
                continue
            declared.add(tok)
            if not exists:
                result.dangling.append((worker_name, tok))

    # orphan — skills/ 파일 중 어느 워커도 선언 안 한 것.
    for skill_name in adapter.list_skills():
        if skill_name not in declared:
            result.orphan.append(skill_name)

    return result


__all__ = ["SkillsDiagnostics", "diagnose_skills"]
