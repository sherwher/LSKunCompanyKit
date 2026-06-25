# 유령참조(Phantom Reference) 검증 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 채용 시 "frontmatter name ↔ 파일명 stem 불일치"로 인한 유령참조를 예방·탐지·복구하는 3층 방어를 추가한다.

**Architecture:** (1) `create_worker()` 에 name==stem 불변식(예방). (2) 신규 `phantom_diagnostics.py` + doctor [35][36][37](탐지, read-only). (3) `schema_migration.py` 에 name→stem 보정(복구, dry-run+백업). 진실원 = 파일명 stem.

**Tech Stack:** Python 3 stdlib only (외부 의존성 0), stdlib `unittest`. markdown frontmatter (`lskun_kit.adapters.frontmatter`).

## Global Constraints

- stdlib only — 외부 라이브러리 import 금지 (ADR-0009 self-contained).
- 진실원 = **파일명 stem**. frontmatter `name` 은 파생값 (ADR-0023).
- doctor 는 **read-only** — 자동 수정 절대 금지 (수정 방법만 제시).
- 채용 순서 = **① create_worker → ② record_hire** (파일 먼저).
- doctor 심각도: name↔stem 불일치 = ❌, 고아 audit·dangling skill = ⚠️, file-only(audit없음) = ℹ️.
- 코드 식별자 영어, 주석/문서 한국어 허용. 커밋 Conventional Commits. Co-Authored-By trailer 부착.
- 테스트 컨벤션: `ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT/"src"))` 후 import. `tempfile.TemporaryDirectory()` + `setUp/tearDown`.
- 모든 테스트 실행: `python3 -m unittest <module> -v` (repo 루트에서).

---

### Task 1: 예방 — `create_worker()` name==stem 불변식

**Files:**
- Modify: `src/lskun_kit/adapters/_markdown_tree.py:145-160` (`create_worker`)
- Test: `tests/test_local_adapter.py` (신규 테스트 메서드 추가)

**Interfaces:**
- Consumes: `InvalidWorkerSchemaError` (`lskun_kit.errors`, 이미 import 됨 `_markdown_tree.py:16-20`).
- Produces: `create_worker(name, frontmatter_dict, body)` — `frontmatter_dict["name"] != name` 이면 `InvalidWorkerSchemaError` raise (파일 쓰기 전).

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_local_adapter.py` 의 `LocalAdapterTests` 클래스 안에 추가:

```python
    def test_create_worker_rejects_name_stem_mismatch(self) -> None:
        # ADR-0023 — frontmatter name 이 파일명 인자와 다르면 거부 (유령참조 예방).
        from lskun_kit.errors import InvalidWorkerSchemaError
        with self.assertRaises(InvalidWorkerSchemaError):
            self.adapter.create_worker(
                name="harin",
                frontmatter_dict={
                    "name": "harlin",  # ← stem(harin) 과 불일치
                    "role": "engineer",
                    "domain": "medical",
                    "hired_at": "2026-06-25",
                    "storage_backend": "local",
                    "display_name": "하린",
                },
                body="# harin\n\nJD\n",
            )
        # 파일이 생성되지 않았는지 확인 (예방이므로 디스크에 안 박혀야 함).
        self.assertFalse((self.root / "hired" / "harin.md").exists())
        self.assertFalse((self.root / "hired" / "harlin.md").exists())

    def test_create_worker_accepts_name_stem_match(self) -> None:
        # 회귀 — 일치하면 정상 생성.
        self.adapter.create_worker(
            name="harin",
            frontmatter_dict={
                "name": "harin",
                "role": "engineer",
                "domain": "medical",
                "hired_at": "2026-06-25",
                "storage_backend": "local",
                "display_name": "하린",
            },
            body="# harin\n\nJD\n",
        )
        self.assertTrue((self.root / "hired" / "harin.md").exists())
        self.assertEqual(self.adapter.read_worker("harin").name, "harin")
```

> 주의: `self.adapter` / `self.root` 는 기존 `setUp` 에 있는지 확인. 없으면 `LocalAdapter(self.root)` 로 인스턴스 생성하는 줄을 setUp 또는 테스트 안에 추가. (`test_local_adapter.py:65-77` setUp 확인)

- [ ] **Step 2: 테스트 실패 확인**

Run: `python3 -m unittest tests.test_local_adapter.LocalAdapterTests.test_create_worker_rejects_name_stem_mismatch -v`
Expected: FAIL — 현재는 불변식이 없어 파일이 생성되고 assertRaises 가 안 터짐.

- [ ] **Step 3: 불변식 구현**

`src/lskun_kit/adapters/_markdown_tree.py` 의 `create_worker` 를 수정. `path = self._worker_path(name)` 직후, `if path.exists()` 앞에 추가:

```python
    def create_worker(
        self,
        name: str,
        frontmatter_dict: dict[str, str],
        body: str,
    ) -> None:
        """``hired/<name>.md`` 신규 박제. 존재하면 ``FileExistsError`` raise."""

        path = self._worker_path(name)  # allowlist 가드 통과
        # ADR-0023 — 진실원=파일명. frontmatter name 이 파일명 인자와 다르면 거부.
        # list_workers 는 파일명 stem, read_worker 는 frontmatter name 을 반환하므로
        # 둘이 어긋나면 routing/dispatch 가 깨진다 (유령참조 예방).
        fm_name = frontmatter_dict.get("name")
        if fm_name != name:
            raise InvalidWorkerSchemaError(
                f"frontmatter name={fm_name!r} != 파일명 {name!r} "
                f"(ADR-0023: 파일명이 진실원). 유령참조 방지."
            )
        if path.exists():
            raise FileExistsError(
                f"worker already exists: hired/{name}.md ({path})"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        text = frontmatter.dump(frontmatter_dict, body)
        path.write_text(text, encoding="utf-8")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python3 -m unittest tests.test_local_adapter.LocalAdapterTests.test_create_worker_rejects_name_stem_mismatch tests.test_local_adapter.LocalAdapterTests.test_create_worker_accepts_name_stem_match -v`
Expected: PASS (둘 다).

- [ ] **Step 5: 전체 local adapter 테스트 회귀 확인**

Run: `python3 -m unittest tests.test_local_adapter -v`
Expected: 기존 테스트 전부 PASS (불변식이 정상 흐름을 안 깨뜨림).

- [ ] **Step 6: 커밋**

```bash
git add src/lskun_kit/adapters/_markdown_tree.py tests/test_local_adapter.py
git commit -m "feat(P122): create_worker name==stem 불변식 — 유령참조 예방 (ADR-0023)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 탐지 — `phantom_diagnostics.py` 신규 모듈

**Files:**
- Create: `src/lskun_kit/phantom_diagnostics.py`
- Test: `tests/test_phantom_diagnostics.py`

**Interfaces:**
- Consumes: `MarkdownTreeAdapter` (`list_workers`, `read_worker`, `skill_path`, `root`). `hire_audit.read_events(company_root)`. `context._split_skills`.
- Produces:
  - `@dataclass PhantomDiagnostics` 필드: `name_mismatch: list[tuple[str, str]]` (stem, fm_name), `orphan_audit: list[str]` (audit엔 있고 파일 없는 name), `file_only: list[str]` (파일만, audit 없음 — 정상), `dangling_skills: list[tuple[str, str]]` (worker, skill).
  - `PhantomDiagnostics.has_critical() -> bool` (= `bool(self.name_mismatch)`).
  - `PhantomDiagnostics.has_warning() -> bool` (= `bool(self.orphan_audit or self.dangling_skills)`).
  - `diagnose_phantom(adapter) -> PhantomDiagnostics`.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_phantom_diagnostics.py` 생성:

```python
"""유령참조 진단 테스트 (P122, ADR-0023). stdlib unittest 만 사용."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lskun_kit import LocalAdapter  # noqa: E402
from lskun_kit.phantom_diagnostics import diagnose_phantom  # noqa: E402


def _worker_md(name: str, *, fm_name: str | None = None,
               domain: str = "medical", skills: str | None = None) -> str:
    # fm_name 으로 frontmatter name 을 stem 과 다르게 만들 수 있다 (불일치 fixture).
    actual = fm_name if fm_name is not None else name
    fm = dedent(
        f"""\
        ---
        name: {actual}
        role: {name}
        domain: {domain}
        hired_at: 2026-06-25
        storage_backend: local
        display_name: Test {name}
        """
    )
    if skills is not None:
        fm += f"skills: {skills}\n"
    fm += "---\nJD body\n"
    return fm


class PhantomDiagnosticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / ".company"
        (self.root / "hired").mkdir(parents=True)
        self.adapter = LocalAdapter(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_worker(self, filename_stem: str, **kw) -> None:
        (self.root / "hired" / f"{filename_stem}.md").write_text(
            _worker_md(filename_stem, **kw), encoding="utf-8"
        )

    def test_detects_name_stem_mismatch(self) -> None:
        # 파일명 harin.md 인데 frontmatter name=harlin → 불일치 (치명적).
        self._write_worker("harin", fm_name="harlin")
        result = diagnose_phantom(self.adapter)
        self.assertIn(("harin", "harlin"), result.name_mismatch)
        self.assertTrue(result.has_critical())

    def test_clean_company_no_mismatch(self) -> None:
        self._write_worker("alice")
        result = diagnose_phantom(self.adapter)
        self.assertEqual(result.name_mismatch, [])
        self.assertFalse(result.has_critical())

    def test_detects_orphan_audit(self) -> None:
        # audit 에 hire 기록은 있으나 hired/ 파일 부재 → 고아 audit (경고).
        from lskun_kit import hire_audit
        hire_audit.record_hire(
            self.root, actor="hr-lead", name="ghost",
            role="engineer", domain="medical",
        )
        # ghost.md 는 만들지 않음.
        result = diagnose_phantom(self.adapter)
        self.assertIn("ghost", result.orphan_audit)
        self.assertTrue(result.has_warning())

    def test_file_only_is_info_not_warning(self) -> None:
        # 파일은 있으나 audit 없음 → 정상 (사용자 직접 hire). 경고 아님.
        self._write_worker("alice")
        result = diagnose_phantom(self.adapter)
        self.assertIn("alice", result.file_only)
        self.assertNotIn("alice", result.orphan_audit)

    def test_detects_dangling_skill(self) -> None:
        # skills 선언 토큰이 가리키는 skills/<name>.md 부재 → dangling (경고).
        self._write_worker("alice", skills="hipaa-x")
        # skills/hipaa-x.md 는 만들지 않음.
        result = diagnose_phantom(self.adapter)
        self.assertIn(("alice", "hipaa-x"), result.dangling_skills)
        self.assertTrue(result.has_warning())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python3 -m unittest tests.test_phantom_diagnostics -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lskun_kit.phantom_diagnostics'`.

- [ ] **Step 3: 모듈 구현**

`src/lskun_kit/phantom_diagnostics.py` 생성:

```python
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
```

> 주의: `hire_audit.read_events` 는 `company_root` (= `<root>`) 를 받아 `<root>/hired/.audit.jsonl` 을 읽는다 (`hire_audit.py:116-117`). `adapter.root` 가 company_root 다 (`_markdown_tree.py:58-60`).

- [ ] **Step 4: 테스트 통과 확인**

Run: `python3 -m unittest tests.test_phantom_diagnostics -v`
Expected: 5개 전부 PASS.

- [ ] **Step 5: 커밋**

```bash
git add src/lskun_kit/phantom_diagnostics.py tests/test_phantom_diagnostics.py
git commit -m "feat(P122): phantom_diagnostics 모듈 — name↔stem·고아 audit·dangling skill 탐지 (ADR-0023)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 복구 — `schema_migration.py` name→stem 보정

**Files:**
- Modify: `src/lskun_kit/schema_migration.py` (`MigrationPlan`, `plan()`, `execute()`)
- Test: `tests/test_schema_migration.py`

**Interfaces:**
- Consumes: `frontmatter.parse/dump`, `_backup_file`, `MarkdownTreeAdapter.list_workers`.
- Produces:
  - `MigrationPlan.name_mismatches: list[tuple[str, str]]` 필드 추가 (stem, fm_name). default `field(default_factory=list)`.
  - `plan()` 이 hired/*.md 순회 중 frontmatter name != stem 이면 `name_mismatches` 에 append.
  - `MigrationPlan.is_no_op` 에 `not self.name_mismatches` 조건 추가.
  - `execute()` 가 각 mismatch 워커의 frontmatter `name` 을 stem 으로 **덮어쓴다** (백업 후). `MigrationResult.workers_updated` 에 추가.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_schema_migration.py` 에 추가 (기존 import/헬퍼 재사용; 없으면 아래 self-contained 버전 사용):

```python
    def test_plan_detects_name_stem_mismatch(self) -> None:
        # 파일명 harin.md, frontmatter name=harlin → plan 이 mismatch 포착.
        from lskun_kit import schema_migration as sm
        hired = self.root / "hired"
        hired.mkdir(parents=True, exist_ok=True)
        (hired / "harin.md").write_text(
            "---\nname: harlin\nrole: eng\ndomain: medical\n"
            "hired_at: 2026-06-25\nstorage_backend: local\n"
            "display_name: 하린\n---\nJD\n",
            encoding="utf-8",
        )
        p = sm.plan(self.adapter, self.root, backend="local")
        self.assertIn(("harin", "harlin"), p.name_mismatches)
        self.assertFalse(p.is_no_op)

    def test_execute_fixes_name_to_stem(self) -> None:
        # 보정 후 frontmatter name 이 stem(harin) 이 되고, 백업이 생기고,
        # 그 외 필드는 보존된다.
        from lskun_kit import schema_migration as sm
        from lskun_kit.adapters import frontmatter as fm
        hired = self.root / "hired"
        hired.mkdir(parents=True, exist_ok=True)
        target = hired / "harin.md"
        target.write_text(
            "---\nname: harlin\nrole: eng\ndomain: medical\n"
            "hired_at: 2026-06-25\nstorage_backend: local\n"
            "display_name: 하린\n---\nJD body 보존\n",
            encoding="utf-8",
        )
        p = sm.plan(self.adapter, self.root, backend="local")
        result = sm.execute(self.adapter, p, sm.MigrationAnswers())
        parsed = fm.parse(target.read_text(encoding="utf-8"))
        self.assertEqual(parsed.frontmatter["name"], "harin")  # stem 으로 보정
        self.assertEqual(parsed.frontmatter["role"], "eng")     # 그외 보존
        self.assertIn("JD body 보존", parsed.body)              # body 보존
        self.assertIn("harin", result.workers_updated)
        self.assertTrue(any(b.name.startswith("harin.md") for b in result.backups_created))
```

> setUp 에 `self.adapter = LocalAdapter(self.root)` / `self.root = Path(tmp)/".company"` 가 있는지 확인. 없으면 추가. 기존 `test_schema_migration.py` 의 setUp 패턴을 따른다.

- [ ] **Step 2: 테스트 실패 확인**

Run: `python3 -m unittest tests.test_schema_migration.<TestClass>.test_plan_detects_name_stem_mismatch -v`
Expected: FAIL — `MigrationPlan` 에 `name_mismatches` 속성 없음 (AttributeError).

- [ ] **Step 3-a: `MigrationPlan` 필드 추가**

`schema_migration.py:58-80` `MigrationPlan` dataclass 에 필드 추가 (`legacy_history_workers` 아래):

```python
    #: ADR-0023 (P122) — 파일명 stem != frontmatter name 인 워커 (stem, fm_name).
    #: 진실원=stem 이므로 execute 가 frontmatter name 을 stem 으로 덮어쓴다.
    name_mismatches: list[tuple[str, str]] = field(default_factory=list)
```

`is_no_op` 프로퍼티(`:73-80`)에 조건 추가:

```python
    @property
    def is_no_op(self) -> bool:
        return (
            not self.company_missing_fields
            and not self.worker_gaps
            and not self.claude_md_marker_missing
            and not self.legacy_history_workers
            and not self.name_mismatches
        )
```

`render()` (`:82-114`)에 표시 줄 추가 (`legacy_history` 블록 뒤, `is_no_op` 체크 앞):

```python
        if self.name_mismatches:
            lines.append(
                f"name 불일치 : {len(self.name_mismatches)} 워커 "
                f"(ADR-0023 — frontmatter name 을 파일명 stem 으로 보정 예정)"
            )
            for stem, fm_name in self.name_mismatches:
                lines.append(f"  - {stem}.md: name='{fm_name}' → '{stem}'")
```

- [ ] **Step 3-b: `plan()` 에서 mismatch 포착**

`plan()` 의 hired 순회 루프 (`:195-212`) 안, `legacy_history` 감지 뒤에 추가:

```python
            # ADR-0023 (P122) — frontmatter name != 파일명 stem 포착 (유령참조).
            fm_name = parsed_w.frontmatter.get("name")
            if fm_name is not None and fm_name != p.stem:
                name_mismatches.append((p.stem, fm_name))
```

루프 앞 (`gaps`/`legacy_history` 초기화 옆, `:192-193`)에 `name_mismatches: list[tuple[str, str]] = []` 추가하고, `return MigrationPlan(...)` 에 `name_mismatches=name_mismatches,` 인자 추가.

- [ ] **Step 3-c: `execute()` 에서 보정**

`execute()` 의 "2b) legacy history rename" 블록 (`:363-377`) 뒤에 신규 블록 추가:

```python
    # 2c) ADR-0023 (P122) — frontmatter name 을 파일명 stem 으로 보정 (진실원=stem).
    workers_updated = set(result.workers_updated)
    for stem, _fm_name in plan.name_mismatches:
        worker_path = plan.company_root / "hired" / f"{stem}.md"
        if not worker_path.exists():
            continue
        bak = _backup_file(worker_path)
        result.backups_created.append(bak)
        parsed = fm.parse(worker_path.read_text(encoding="utf-8"))
        new_fm = dict(parsed.frontmatter)
        new_fm["name"] = stem  # 덮어쓰기 — _merge_frontmatter(누락만 추가) 와 다름
        worker_path.write_text(fm.dump(new_fm, parsed.body), encoding="utf-8")
        if stem not in workers_updated:
            result.workers_updated.append(stem)
            workers_updated.add(stem)
```

> 주의: `is_no_op` early-return (`:298-299`) 때문에 mismatch 만 있어도 통과해야 한다. Step 3-a 의 `is_no_op` 갱신으로 이미 보장됨.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python3 -m unittest tests.test_schema_migration -v`
Expected: 신규 2개 PASS + 기존 전부 PASS.

- [ ] **Step 5: 커밋**

```bash
git add src/lskun_kit/schema_migration.py tests/test_schema_migration.py
git commit -m "feat(P122): migrate-schema name→stem 보정 — 유령참조 복구 (ADR-0023)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: doctor.md [35][36][37] 항목 + 항목 수 정정

**Files:**
- Modify: `commands/doctor.md` (신규 섹션 + 출력 예시 + frontmatter description 항목 수)
- Modify: `CLAUDE.md` (doctor 줄 항목 수 [34]→[37])

**Interfaces:**
- Consumes: `phantom_diagnostics.diagnose_phantom(adapter)` (Task 2).
- Produces: 없음 (문서). doctor 는 LLM 이 md 지침대로 실행하므로 코드 호출은 md 안에 박제.

- [ ] **Step 1: doctor.md 에 진단 섹션 추가**

`commands/doctor.md` 의 [34] 항목(외주 setup 관련) 정의 섹션 **뒤**, 출력 예시 표 **앞**에 추가:

```markdown
### 35. name ↔ 파일명 정합 (ADR-0023, 유령참조)

`phantom_diagnostics.diagnose_phantom(adapter)` 의 `name_mismatch`:

- 각 `hired/<stem>.md` 의 frontmatter `name` 이 파일명 stem 과 일치하는지 검증
- 불일치 시 **❌** `"<stem>.md: name='<fm_name>' ≠ '<stem>' → 유령참조 위험 (dispatch 깨짐). /lskun-kit:migrate-schema 로 보정"`
- 전부 일치 → ✅

### 36. 채용 audit ↔ 파일 정합 (ADR-0023)

`diagnose_phantom` 의 `orphan_audit` / `file_only`:

- `hired/.audit.jsonl` 의 hire `name` 집합 vs `hired/*.md` stem 집합 대조
- audit엔 있고 파일 없음 → **⚠️** `"채용 기록 있으나 hired/<name>.md 없음 (고아 audit). 채용이 파일 생성 전에 중단됐을 수 있음"`
- 파일만 있고 audit 없음 → ℹ️ `"<name>: 수동 박제(audit 기록 없음) — 정상"` (사용자 직접 /hire)
- 둘 다 정합 → ✅

### 37. dangling skills 참조 (ADR-0023)

`diagnose_phantom` 의 `dangling_skills`:

- 각 워커 `skills:` 토큰이 가리키는 `skills/<tok>.md` 존재 확인
- 부재 시 **⚠️** `"<worker>.skills='<tok>' → skills/<tok>.md 없음 (dangling)"`
- 전부 존재 / skills 선언 없음 → ✅

> [31] (skills/ 정합성) 의 dangling 과 중복처럼 보이나, [31] 은 skills_diagnostics
> (orphan 양방향 + invalid + meta) 전체, [37] 은 유령참조 관점의 dangling 만 재확인.
> 동일 사실이면 둘 다 같은 결과를 내야 정상 (cross-check).
```

- [ ] **Step 2: 출력 예시 표에 줄 추가**

`commands/doctor.md` 의 출력 예시 (`[34] HALT env...` 줄 뒤)에 추가:

```markdown
[35] name↔파일명 정합 (ADR-0023) : ✅ 43/43 일치
[36] 채용 audit↔파일 (ADR-0023)  : ✅ 정합 (고아 0)
[37] dangling skills (ADR-0023)  : ✅ dangling 0
```

- [ ] **Step 3: 항목 수 정정**

`commands/doctor.md` frontmatter `description` 또는 본문에 "32개 항목" / "[1]~[34]" 같은 총 항목 수 표기가 있으면 **[1]~[37]** 로 갱신 (결번 18·19 유지 명시).

`CLAUDE.md` 의 doctor 줄 (`| `/lskun-kit:doctor` | 환경 진단 (32개 항목, 라벨 [1]~[34]...`)을:
```
| `/lskun-kit:doctor` | 환경 진단 (라벨 [1]~[37] 중 18·19 결번 — ... + ADR-0023 [35][36][37]) |
```
로 갱신 (정확한 개수는 결번 고려해 계산: [1]~[37] 중 18·19 결번 = 35개).

- [ ] **Step 4: doctor 시뮬레이션 검증 (수동)**

Run: `python3 -c "import sys; sys.path.insert(0,'src'); from lskun_kit.phantom_diagnostics import diagnose_phantom; print('import OK')"`
Expected: `import OK` (md 가 참조하는 함수가 실제로 import 가능한지 확인).

- [ ] **Step 5: 커밋**

```bash
git add commands/doctor.md CLAUDE.md
git commit -m "docs(P122): doctor [35][36][37] 유령참조 진단 항목 + 항목 수 정정 (ADR-0023)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: 채용 순서 박제 (예방 보강) + 문서/버전

**Files:**
- Modify: `commands/hire.md`, `src/lskun_kit/templates/cpo.md`, `commands/work.md` (채용 순서)
- Modify: `docs/internals/adr-index.md`, `docs/internals/forbidden-history.md`, `docs/internals/phase-roadmap.md`
- Modify: `CLAUDE.md` (§1 버전/Phase, §6 forbidden)
- Modify: `.claude-plugin/plugin.json` (version)

**Interfaces:** 없음 (문서/버전).

- [ ] **Step 1: 채용 순서 명시**

`commands/hire.md` Python 진입점 예시 + `templates/cpo.md` 자동 채용 절차 + `commands/work.md` CPO 라우팅 자동 채용 단계, 세 곳에 순서 박제:

```
1. adapter.create_worker(name, fm, body)   # ① 파일 먼저 — 실패 시 중단, audit 안 남김
2. hire_audit.record_hire(actor="hr-lead", name=name, ...)  # ② 파일 성공 후에만 audit
```

각 파일의 기존 채용 의사코드 블록을 찾아 "파일 먼저 → audit" 순서가 명확히 드러나게 1~2줄 추가. (cpo.md 의 자동 채용 절차는 `[채용 알림]` 직전 단계.)

- [ ] **Step 2: forbidden-history.md 갱신**

`docs/internals/forbidden-history.md` 에 추가:
```markdown
- frontmatter `name` ≠ 파일명 stem 박제 — ADR-0023 (P122). create_worker 불변식 차단, doctor [35] ❌, migrate-schema 보정.
- 채용 시 파일 생성 전 audit 먼저 기록 (고아 audit) — ADR-0023 (P122). 순서: create_worker → record_hire.
```

`CLAUDE.md` §6 "절대 만들지 말 것" 목록에 1줄:
```markdown
- frontmatter name ↔ 파일명 stem 불일치 / 파일 없는 채용 audit (유령참조) — ADR-0023
```

- [ ] **Step 3: adr-index.md + phase-roadmap.md**

`docs/internals/adr-index.md` 에 ADR-0023 줄 추가 (기존 형식 따름):
```markdown
| ADR-0023 | 2026-06-25 | 채용 유령참조 — 진실원=파일명 stem, 3층 방어(예방/탐지/복구) | Accepted |
```

`docs/internals/phase-roadmap.md` 에 P122 1줄 추가 (기존 형식 따름):
```markdown
- **Phase 22 (0.29.0)** — 채용 유령참조 검증 (P122, ADR-0023): create_worker name==stem 불변식 + doctor [35][36][37] + migrate-schema name→stem 보정.
```

> 주의: Phase 번호는 phase-roadmap.md 의 마지막 Phase 를 확인해 +1 (현재 Phase 21 → 22). version 0.28.0 → 0.29.0.

- [ ] **Step 4: CLAUDE.md §1 + version bump**

`CLAUDE.md` §1 의 현재 Phase 줄을 갱신:
```
현재 Phase 22 (0.29.0) — 채용 유령참조 검증 (ADR-0023). ... 이전 (0.28.0) = 외주 setup 자동 시퀀스 (ADR-0022). ...
```

`.claude-plugin/plugin.json` 의 `"version": "0.28.0"` → `"0.29.0"`.

- [ ] **Step 5: 전체 테스트 + 버전 확인**

Run: `python3 -m unittest discover -s tests -v 2>&1 | tail -20`
Expected: 전체 PASS (OK).

Run: `grep '"version"' .claude-plugin/plugin.json`
Expected: `"version": "0.29.0",`

- [ ] **Step 6: 커밋**

```bash
git add commands/ src/lskun_kit/templates/cpo.md docs/internals/ CLAUDE.md .claude-plugin/plugin.json
git commit -m "docs(P122): 채용 순서(파일 먼저) 박제 + ADR-0023/forbidden/roadmap + version 0.29.0

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 검증 (전 Task 완료 후)

- [ ] **전체 테스트 통과**

Run: `python3 -m unittest discover -s tests 2>&1 | tail -5`
Expected: `OK` (실패 0, 에러 0).

- [ ] **doctor 참조 무결성** — doctor.md 가 참조하는 함수가 전부 import 가능

Run: `python3 -c "import sys; sys.path.insert(0,'src'); from lskun_kit.phantom_diagnostics import diagnose_phantom; from lskun_kit.schema_migration import plan; print('OK')"`
Expected: `OK`

- [ ] **신규/변경 파일 lint** — 구문 오류 없음

Run: `python3 -m py_compile src/lskun_kit/phantom_diagnostics.py src/lskun_kit/schema_migration.py src/lskun_kit/adapters/_markdown_tree.py`
Expected: 출력 없음 (성공).

---

## ADR 본문 vault 동기화 (구현 후, 별도)

ADR-0023 본문은 vault `decisions/ADR-0023-2026-06-25-phantom-reference-truth-source.md` 에 박제하고 hub 갱신 — repo 는 번호만 ([[vault-adr-sync]] 관행). 이 작업은 repo 코드와 무관하므로 PR 후 사용자에게 안내.

---

## Self-Review 결과

- **Spec 커버리지**: 예방(Task1·5) / 탐지(Task2·4) / 복구(Task3) / 테스트(각 Task) / 문서·ADR(Task4·5) — spec §3~8 전부 매핑됨. ✓
- **Placeholder**: 모든 step 에 실제 코드/명령/예상 출력 포함. "기존 형식 따름" 은 해당 파일을 열어 확인하라는 명시적 지시(파일 경로 제공). ✓
- **타입 일관성**: `diagnose_phantom`/`PhantomDiagnostics`/`name_mismatch`/`name_mismatches`(Plan 필드, 복수형 의도적 구분) — Task 2(진단)와 Task 3(migration) 은 별개 모듈이라 이름 충돌 아님. `has_critical`/`has_warning` 일관. ✓
