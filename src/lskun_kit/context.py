"""워커 컨텍스트 빌더 (ADR-0014, 2026-05-22 / ADR-0020, 2026-05-27).

ADR-0001 §3 의 Reflection 메커니즘 폐기 (ADR-0014). 워커는 채용 시점에 JD
(persona body) 로 완성형이며, history 누적은 워커 state 가 아니다. 따라서
워커 dispatch 컨텍스트는 JD only — 옛 ``## Past Patterns`` 섹션 주입 제거.

ADR-0020 (P111) — 워커 전문 도구 (skills) 주입. ``build_skills_block`` 이
공통 헬퍼이며, 두 dispatch 경로가 모두 호출한다 (C1 — 단일 주입점):
    - 직통 경로 (work.md): ``build_worker_context`` 가 내부에서 append.
    - CPO 라우팅 (cpo.md): ``context = worker.body + build_skills_block(...)``.
core 는 skills 를 해석/실행하지 않는다 — split + 이름 검증 + 경로 조합 + 존재
확인만 (ADR-0009 self-contained 범위 내). 스킬 내용은 워커가 Read 한다.
"""

from __future__ import annotations

from lskun_kit.adapters.base import StorageAdapter


def _split_skills(raw: str | None) -> list[str]:
    """skills frontmatter 값 (콤마 구분 string) → strip + 빈 토큰 제거된 리스트.

    ``None`` / 빈 문자열 / 공백만 → 빈 리스트. ``"a,,b"`` → ``["a", "b"]``.
    """

    if not raw:
        return []
    return [tok.strip() for tok in raw.split(",") if tok.strip()]


def build_skills_block(
    adapter: StorageAdapter, name: str, worker=None
) -> str:
    """워커의 전문 도구 (skills) 블록을 반환 (ADR-0020).

    두 dispatch 경로의 단일 주입점 (C1). skills 가 비면 빈 문자열 반환
    (블록 생략 — 메타 워커 등). 각 skill 토큰은 이름 검증 (M1) 후 경로 조합 +
    존재 확인되며, 위반/누락은 워커에게 사실 표시된다.

    Args:
        adapter: storage adapter (``skill_path`` 를 제공해야 함; 없으면 빈 블록).
        name: 워커 이름.
        worker: 이미 읽은 워커 객체 (N-1 — 중복 read_worker 회피). None 이면 읽는다.

    Returns:
        ``## 전문 도구`` 섹션 문자열 (선행/끝 개행 포함) 또는 빈 문자열.
    """

    if worker is None:
        worker = adapter.read_worker(name)
    tokens = _split_skills(getattr(worker, "skills", None))
    if not tokens:
        return ""

    # skill_path 가 없는 adapter (외부 add-on 등) 는 graceful 하게 블록 생략.
    # 현재 구현체 (MarkdownTreeAdapter 계열) 는 모두 보유 — 미래 확장 방어.
    skill_path = getattr(adapter, "skill_path", None)
    if skill_path is None:
        return ""

    lines: list[str] = []
    for tok in tokens:
        try:
            path = skill_path(tok)
        except ValueError:
            lines.append(f"- {tok}  ⚠️ invalid skill name (무시됨)")
            continue
        marker = "" if path.exists() else "  ⚠️ 파일 없음"
        lines.append(f"- {tok} → {path}{marker}")

    # 선행 "\n\n" — 앞 콘텐츠 (CPO 경로의 worker.body / 직통 경로의 meta) 가
    # trailing newline 없이 끝나도 heading 이 붙지 않게 빈 줄로 분리 (C-2).
    return (
        "\n\n## 전문 도구 (Specialized Skills)\n"
        "당신의 채용 시 박제된 전문 도구입니다. "
        "**작업 시작 전 반드시 Read 로 읽고 따르세요.**\n"
        "또한 작업 보고 시 \"읽은 전문 도구: <이름들>\" 1줄을 포함하세요.\n"
        + "\n".join(lines)
        + "\n"
    )


def build_worker_context(
    adapter: StorageAdapter, name: str, recent: int = 0
) -> str:
    """워커 메타 정보 + 전문 도구 블록을 컨텍스트 문자열로 반환.

    Claude Code 가 워커 Task dispatch 시 system prompt 또는 첫 user 메시지
    앞에 prepend. ADR-0014 이후 history 섹션 주입은 제거되었다 — JD 본문이
    persona body 로 별도 주입되므로 본 함수는 메타 정보 + skills 블록 담당.

    ADR-0020 (P111, C1) — skills 블록을 ``build_skills_block`` 으로 append.
    직통 경로 (work.md) 의 단일 주입점. CPO 라우팅 경로 (cpo.md) 는 worker.body
    조립 시 ``build_skills_block`` 을 별도 호출한다 (양 경로 정합).

    Args:
        adapter: storage adapter
        name: 워커 이름
        recent: ADR-0014 이전 호환을 위해 인자 유지. 값은 무시.
    """

    worker = adapter.read_worker(name)
    meta = (
        f"# Worker: {worker.name} ({worker.role})\n"
        f"Hired: {worker.hired_at.isoformat()} · Backend: {worker.storage_backend}\n"
    )
    # build_skills_block 이 선행 "\n\n" 를 포함하므로 직접 concat (C-2).
    # skills 비면 "" 반환 → meta 만. worker 재사용으로 read_worker 1회 (N-1).
    return meta + build_skills_block(adapter, name, worker=worker)
