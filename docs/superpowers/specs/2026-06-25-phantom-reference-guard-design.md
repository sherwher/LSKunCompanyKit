# 유령참조(Phantom Reference) 검증 방안 — 설계 (spec)

- 작성일: 2026-06-25
- Phase: P122 (예정), version bump 0.28.0 → 0.29.0
- 신규 결정: **ADR-0023** (진실원 = 파일명 stem)
- 브랜치: `feat/p122-phantom-ref-guard`

---

## 1. 배경 / 문제

### 1.1 증상
채용 시 "유령참조" = CPO 가 `[채용 알림] 하린(...)` 1줄을 띄웠는데, 다음에 그 워커를
호출하면 `WorkerNotFoundError` 가 터지는 현상. 사용자 체감: **"방금 뽑았다며?"**

### 1.2 근본 원인 — 이름 권위의 비대칭
| 함수 | 위치 | 워커 이름을 어디서 얻는가 |
|---|---|---|
| `list_workers()` | `_markdown_tree.py:120-131` | **파일명 stem** (`harin.md` → `"harin"`) |
| `read_worker(name)` | `_markdown_tree.py:86-118` | 인자로 `hired/{name}.md` 를 찾되, 반환 `Worker.name` 은 **frontmatter `name` 값** (L99) |

파일명 stem 과 frontmatter `name` 이 어긋나면:
1. `routing.py:92-104` 가 stem(`harin`)으로 순회하며 `read_worker("harin")` → frontmatter
   `name`(예 `harlin`)을 라우팅 후보로 노출.
2. CPO 가 노출된 `harlin` 으로 dispatch → `build_worker_context(adapter,"harlin")`
   (`context.py:102`) → `read_worker("harlin")` → `hired/harlin.md` 없음 →
   **`WorkerNotFoundError` = 유령참조 폭발**.

### 1.3 인접 유령참조 (같은 뿌리)
- **고아 audit**: `record_hire`(audit, `hire_audit.py:228`)와 `create_worker`(파일,
  `_markdown_tree.py:145`)가 **별개 호출** → 한쪽만 성공 시 "기록은 있는데 파일 없는" 유령.
- **dangling skills**: 워커 `skills:` 토큰이 가리키는 `skills/<name>.md` 부재.
  현재 dispatch 시점에 inline "⚠️ 파일 없음"(`context.py:68`)만, 사전 검출 없음.

### 1.4 현재 doctor 의 사각지대
- `[5] Worker frontmatter`: 필수 6필드 *존재*만. `name` 값 ↔ stem 일치 검사 **없음**.
- `[29] hired/ 비워커 파일`: "valid worker(필수필드 보유)"만. 불일치 통과.
- `[14] audit log`: CPO 결재 audit(`.audit/decisions.jsonl`)만. 채용 audit cross-check 없음.
- `[31] skills/ 정합성`: orphan(파일↔선언없음)만. dangling(선언↔파일없음) 미검출.

---

## 2. 결정 사항 (확정)

| 항목 | 결정 | 근거 |
|---|---|---|
| 기대 보장 | **"채용 알림이 떴으면 그 워커는 반드시 호출 가능"** | 사용자 핵심 요구 |
| 진실원 | **파일명(stem)**. frontmatter `name` 은 파생 | list_workers·routing·dispatch 전부 stem 기반 |
| 채용 원자성 | **① `create_worker` 성공 → ② `record_hire`** (파일 먼저) | 파일 없는 audit(고아) 구조적 차단. 변경 최소 |
| doctor 심각도 | name↔stem 불일치 = **❌** / 고아 audit·dangling skill = **⚠️** / file-only(audit없음) = ℹ️ | 불일치는 dispatch 를 실제로 깨뜨림(치명적) |

**역방향(파일 있고 audit 없음)은 정상**: 사용자가 `/lskun-kit:hire` 를 직접 호출하면
audit(actor 자동채용 기록)이 안 남을 수 있음 → ℹ️(정보)로만 표시.

---

## 3. 아키텍처 — 3층 방어

```
[예방]  create_worker()       → name==stem 불변식 (write-path 차단)
        채용 흐름 순서          → 파일 먼저, audit 그 다음 (고아 audit 차단)
[탐지]  doctor [35][36][37]    → read-only 진단 (자동 수정 금지 — doctor 헌법)
[복구]  migrate-schema         → frontmatter name 을 stem 으로 보정 (dry-run + 백업 자동)
```

각 층은 독립 동작·독립 테스트. 한 층이 뚫려도 다음 층이 잡는다.

---

## 4. 컴포넌트 상세

### 4.1 예방 — `create_worker()` 불변식 (`adapters/_markdown_tree.py`)

`_worker_path(name)` allowlist 검증 직후, 파일 쓰기 전에 추가:

```python
def create_worker(self, name, frontmatter_dict, body):
    path = self._worker_path(name)            # 기존 allowlist 가드
    fm_name = frontmatter_dict.get("name")
    if fm_name != name:
        raise InvalidWorkerSchemaError(
            f"frontmatter name={fm_name!r} != 파일명 {name!r} — "
            f"유령참조 방지 (ADR-0023: 파일명이 진실원). "
            f"list_workers 는 파일명, read_worker 는 frontmatter name 을 반환하므로 "
            f"둘이 어긋나면 dispatch 가 깨진다."
        )
    if path.exists():
        raise FileExistsError(...)            # 기존
    ...                                        # 기존 write
```

- 부작용: 없음. 정상 hire 흐름(hire.md / HR Lead)은 항상 동일 name 을 양쪽에 씀.
- `InvalidWorkerSchemaError` 재사용 (`errors.py:19`, 이미 존재).

### 4.2 예방 — 채용 흐름 순서 (문서/persona 박제)

코드가 아니라 **LLM 절차** 이므로 다음 3곳에 "파일 먼저 → audit 그 다음" 순서 명시:
- `commands/hire.md` — Python 진입점 예시에 순서 주석
- `src/lskun_kit/templates/cpo.md` — 자동 채용 절차(현재 §6 / dispatch 표준 절차)
- `commands/work.md` — CPO 라우팅 자동 채용 단계

표준 순서(의사코드):
```
1. adapter.create_worker(name, fm, body)      # ① 파일 — 실패 시 여기서 중단, audit 안 남김
2. hire_audit.record_hire(actor="hr-lead", name=name, ...)   # ② audit — 파일 성공 후에만
3. [채용 알림] 1줄
4. Task(subagent_type="claude", ...) dispatch
```

### 4.3 탐지 — doctor 신규 항목 (read-only)

신규 diagnostics 함수를 `src/lskun_kit/` 에 추가(기존 `*_diagnostics.py` 패턴 따름:
`audit_diagnostics`, `skills_diagnostics`, `external_diagnostics` 존재 → 신규
`phantom_diagnostics.py` 또는 기존 모듈 확장 — 구현 계획에서 확정).

| 라벨 | 항목 | 검사 | 심각도/메시지 |
|---|---|---|---|
| `[35]` | name↔파일명 일치 | 각 `hired/*.md` frontmatter `name` == stem | 불일치 ❌ `harin.md: name='harlin' ≠ 'harin' → 유령참조 위험. /lskun-kit:migrate-schema 로 보정` |
| `[36]` | 채용 audit↔파일 정합 | `hired/.audit.jsonl` hire `name` 집합 vs `hired/*.md` stem 집합 | audit-only ⚠️ `채용 기록 있으나 hired/<name>.md 없음 (고아 audit)` / file-only ℹ️ `수동 박제(audit 없음) — 정상` |
| `[37]` | dangling skills | 각 워커 `skills:` 토큰 → `skills/<tok>.md` 존재 | 부재 ⚠️ `alice.skills='hipaa-x' → skills/hipaa-x.md 없음` |

- 전부 read-only. `[35]` ❌ 시 사용자에게 수정 방법(migrate-schema)만 제시(doctor 자동 수정 금지).
- 백업/임시 파일은 기존 `_is_backup_artifact` 가드로 제외.
- `commands/doctor.md` 본문 + 출력 예시 + **항목 수 [34] → [37] 정정** (CLAUDE.md doctor 줄도).

### 4.4 복구 — `migrate-schema` 보정

`schema_migration.py` / `commands/migrate-schema.md` 확장:
- name ≠ stem 발견 시: **frontmatter `name` 을 stem 으로 덮어씀** (파일명이 진실원).
- 기존 정책 준수: `--dry-run` 우선, 백업 자동(`*.lskun-pre-sync.bak` 또는 기존 migrate 백업 규약 — 구현 시 기존 코드 확인), frontmatter 그 외 필드 보존.
- 출력 1줄: `보정: harin.md frontmatter name 'harlin' → 'harin'`.

---

## 5. 데이터 흐름 (정상 채용, 수정 후)

```
사용자 요청 → CPO → 적합 워커 없음 → HR Lead Task dispatch
  → HR: create_worker(name, {name:name, ...})   # ① 불변식 통과 + 파일 생성
       └ 실패(불일치/IO) 시 → 여기서 중단, audit 안 남김, 사용자에 에러 1줄
  → HR: record_hire(actor="hr-lead", name=name)  # ② 파일 성공 후에만 audit
  → [채용 알림] 1줄 → CPO 가 Task(subagent_type="claude") dispatch
```

불변식 + 순서로 "audit 있는데 파일 없음" 과 "name≠stem" 둘 다 **생성 시점에 차단**.
기존에 이미 박힌 유령은 doctor 탐지 → migrate 복구.

---

## 6. 에러 처리
- `create_worker` 불일치 → `InvalidWorkerSchemaError` (LSKunKitError 상속, `except LSKunKitError` 일괄 catch 동작).
- doctor: 손상 줄 / 파싱 실패는 기존 doctor 관행대로 try/except → 메시지화(세션 안 막음).
- migrate: dry-run 으로 미리 보여주고, 백업 후에만 쓰기. 실패 시 원본 보존.

---

## 7. 테스트 (stdlib unittest)
1. `test_create_worker_name_mismatch_raises` — fm name ≠ 인자 → `InvalidWorkerSchemaError`
2. `test_create_worker_name_match_ok` — 일치 → 정상 생성 (회귀)
3. `test_doctor_detects_name_stem_mismatch` — 인위적 불일치 fixture → [35] ❌
4. `test_doctor_detects_orphan_hire_audit` — audit-only fixture → [36] ⚠️
5. `test_doctor_file_only_is_info` — 파일만(audit 없음) → [36] ℹ️ (정상)
6. `test_doctor_detects_dangling_skill` — 선언만 있는 skill → [37] ⚠️
7. `test_migrate_fixes_name_to_stem` — 불일치 → 보정 + 백업 + 그외 필드 보존
8. `test_clean_company_all_green` — 정상 회사 → [35][36][37] 모두 ✅/정상

---

## 8. 문서 / ADR / 동기화
- **ADR-0023 박제** (진실원=파일명 stem, read_worker 의미 결정). repo 는 번호 인용만,
  본문은 vault `decisions/ADR-0023-2026-06-25-phantom-reference-truth-source.md`
  (관행: repo→vault 동기화 + hub 갱신).
- `docs/internals/adr-index.md` — ADR-0023 번호·상태 추가.
- `docs/internals/forbidden-history.md` — "frontmatter name ≠ 파일명 stem 박제 금지" 추가.
- `docs/internals/phase-roadmap.md` — P122 1줄.
- `CLAUDE.md` — §1 버전/Phase, §6 forbidden 1줄, doctor 항목수 [34]→[37].
- `.claude-plugin/plugin.json` — version 0.28.0 → 0.29.0.

---

## 9. 범위 / YAGNI
- **이번 PR(P122)**: §4.1~4.4 + §7 테스트 + §8 문서. ≤500L 목표.
- **제외(별도)**: 모델 라우팅 현행화(`MODEL_ALIASES opus→4-8`), CLAUDE.md 슬림화/Rules,
  effort 차원, CMA/마켓플레이스 — 전부 유령참조와 독립. 별도 brainstorming/PR.
- 채용 통합 함수(`record_and_create`)는 **채택 안 함** — "파일 먼저" 순서 + 불변식으로
  충분. 통합 함수는 rate-limit 순서·예외 설계 비용이 커서 YAGNI.
```
