# Changelog

본 문서는 사용자 입장에서 LSKunCompanyKit 의 릴리스별 변경 사항을 정리한다.
모든 design pivot 은 [ADR](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/) 박제 후에만 코드에 반영된다.

본 changelog 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 를 따르며, 버전 관리는 [SemVer](https://semver.org/lang/ko/) 를 지향한다 (0.x 동안은 minor 단위 breaking 가능).

## [0.30.0] — 2026-06-25

### Changed — 모델 라우팅 현행화 (P123)

`opus` alias 의 해소 대상을 최신 Claude Opus 로 갱신. alias 자체는 그대로이므로 기존 워커 frontmatter (`model: opus`) 와 `--model=opus` 옵션은 변경 없이 동작한다.

- **`opus` → `claude-opus-4-8`** (이전 `claude-opus-4-7`). Opus 4.7→4.8 은 breaking change 없음 (모델 ID 교체 + 재튜닝), 동일 가격대.
- `sonnet` (`claude-sonnet-4-6`) / `haiku` (`claude-haiku-4-5-20251001`) 는 현행 유지.
- 모델 ID 직접 입력 경로는 영향 없음 (`claude-opus-4-7` 등 과거 ID 도 그대로 통과).

> ADR-0004 §4 의 alias→ID 매핑 현행화. 결정 변경 아님 (ID 값만 갱신). 437 tests OK.

## [0.29.0] — 2026-06-25

### Added — 채용 유령참조 3층 방어 (ADR-0023, P122)

워커 frontmatter `name` 과 파일명 stem 이 달라지면 doctor/routing/audit 에서 존재하지 않는 워커를 참조하는 유령참조(phantom reference)가 발생하던 구조적 결함을 3층 방어로 차단.

- **예방 (Task1)**: `create_worker` 불변식 — `name == stem(filename)` 불일치 시 `InvalidWorkerSchemaError` raise. 유령참조를 생성 시점에 차단.
- **탐지 (Task2/Task4)**: `phantom_diagnostics.diagnose_phantom()` 신규 — name/stem 불일치, 고아 audit (파일 없는 audit 기록), 고아 skills 를 스캔. doctor [35][36][37] 진단 항목 3종 추가 (read-only).
- **복구 (Task3)**: `migrate-schema` 에 name→stem 보정 plan 추가 — `frontmatter.name ≠ stem` 워커를 발견하면 사용자 confirm 후 frontmatter 수정.
- **채용 순서 박제 (ADR-0023)**: `commands/hire.md` / `templates/cpo.md` / `commands/work.md` 에 ① `create_worker`(파일 먼저) → ② `record_hire`(audit) 순서 명문화. 파일 없는 audit(고아 audit) 금지.

> ADR-0023 박제. doctor 항목 34 → 37개 (라벨 [35][36][37]). forbidden-history.md + adr-index.md + phase-roadmap.md 동기화.

## [0.28.0] — 2026-05-29

### Added — 외주 setup 자동 시퀀스 결정론 강제 (ADR-0022, P121)

멀티-step CPO 시퀀스(외주 setup)가 도중에 멈춰 사용자가 "끊긴 것 아니냐"고 깨워야 진행되던 UX 결함을 plugin 차원에서 차단. 두 프로젝트에서 재현된 구조적 결함(Claude Code 의 turn-based 특성 + LLM 자율 종료)이라 hook 으로 결정론적 강제.

- **PostToolUse:Task hook** (`post_tool_use_external.py`): marker 살아있으면 Task 종료 직후 "다음 판단 step" 을 `<system-reminder>` 로 push (같은 turn 연속 유도, soft hint).
- **Stop hook** (`stop_external.py`): marker 살아있으면 turn 종료를 `decision="block"` 으로 차단 (hard guard). reason 은 "강제" 가 아니라 "다음 판단 step 을 이어서 수행" — CPO 결재권 보존 (ADR-0004 §8).
- **marker 파일** (`~/.lskun-companies/<company>/.external-setup.json`): `external_setup_state` 모듈이 start/advance/finalize/cancel + atomic write + 24h TTL + step 폭주 가드 관리. `current_step`/`next_action` 은 STEP_ENUM allowlist 강제 (sync-in 경유 prompt 인젝션 차단 — security C1).
- **안전장치**: `stop_hook_active=true` → 무조건 allow + marker auto-unlink (무한 lockup 방지 단일 invariant). `LSKUN_ALLOW_EXTERNAL_HALT=1` escape hatch. `/lskun-kit:external cancel <project>` 명시 중단.
- **`/clear` 강제 break**: hook 으로 못 푸는 워커 세션 정리 break 는 `commands/external.md` 본문 안내(pull)로 보완 — "한 turn 완수 + 사용자 응답 대기 금지" 명시.
- **doctor [33][34]**: stale/손상 marker 검출 + `.zshrc` 등의 `LSKUN_ALLOW_EXTERNAL_HALT` 영구 export 검출 (read-only).
- **sync 가드**: sync-in/out 시 `.external-setup.json` 발견하면 인지 경고 note (security C1 마지막 갈래).

> 3 전문가 점검(architect/critic/security) 의 BLOCKER 3건 + MAJOR 3건 전부 반영. reflection 폐기(ADR-0014)는 유지 — 본 hook 은 외주 setup 한정, marker 존재 시에만 동작, 자동 평가·history 박제 0 (forbidden-history.md:45 부분 supersede).

## [0.27.0] — 2026-05-28

### Added — 프로젝트별 외주 (레드팀 + 고객) 도입 (ADR-0021, P120)

CPO 가 프로젝트별로 외주 (레드팀·고객) 를 빌려 워커 결과물을 비평·청취하되, 결정은 CPO 단독으로 내리는 메커니즘 박제. 외주는 회사 임직원이 아닌 "회사 비종속 평가 자원". 회사 SSOT 하위 `external/<project>/` 에 거주 (3번째 SSOT 금지, ADR-0008 2축 유지).

- **명령**: `/lskun-kit:external setup|list|consult <project>` (옵셔널 — 존재 자체가 opt-in)
- **레드팀**: 경쟁사/보안비평/규제 관점에서 텍스트 비평만 (파괴 행위 금지 헌법 박제)
- **고객단**: 정성 페르소나 렌즈 (다수결/%/대부분 금지 — 환각 방어)
- **구성 시퀀스**: CPO 주도 — 도메인 워커 자문 → brief.md 합성 → HR Lead 가 페르소나 박제. 도메인 워커 부재 시 자동 채용 (ADR-0004 §3 재사용)
- **보안**: 외주 body·의견 untrusted → `build_external_context` 가 backtick + tilde fence 양쪽 중화, HTML 주석 제거, 8000자 절단. 모든 외주 경로 `is_relative_to` traversal 격리 + project 세그먼트 dot 전면 금지
- **세션 clear 후 dispatch**: 외주 dispatch 는 워커 세션 종료 후 CPO 단독 (PreToolUse hook deny 회피, command 본문 명시)
- **audit 통합**: `record_external_onboard` (event_type=onboard_external, hire rate-limit 우회 — 고객 N명 동시 박제 정상)
- **doctor [32]**: external 정합성 — brief.md 존재 + cross-project leak 검증 (read-only)
- **마이그레이션**: `Worker.kind` OPTIONAL (REQUIRED 미포함 → 기존 워커 호환 보존)

**검증 (3 전문가 점검 — architect/critic/security)**:
- BLOCKER 2건 + MAJOR 5건 발견 → 설계 반영 후 10 task TDD 분해
- 363 tests PASS, 외부 SDK 0 (ADR-0009 정합)
- 사용자 의도 손실 0 — "프로젝트 전문가 주도 셋팅" 을 도메인 워커 자문 시퀀스로 복원

> spec: `docs/superpowers/specs/2026-05-28-external-redteam-customers-design.md`
> plan: `docs/superpowers/plans/2026-05-28-external-redteam-customers.md`

## [0.26.0] — 2026-05-27

### Added — 워커 전문 도구 (`skills`) 박제 (ADR-0020, P111)

JD 의 산문 전문성만으로는 워커가 "이 도구가 내 전문 도구"임을 인지하지 못하던 문제. 워커 frontmatter 에 optional `skills` 필드 (콤마 구분 string) 를 추가해 채용 시점에 전문 도구 (`~/.lskun-companies/<name>/skills/<name>.md`) 를 박제한다.

- **dispatch 주입**: `build_skills_block` 헬퍼가 두 dispatch 경로 (직통 `/work <name>` + CPO 라우팅) 에 skill 경로를 주입하고, 워커가 작업 전 Read 한다. 누락 스킬은 `⚠️ 파일 없음` 표시.
- **스킬 생성**: 채용 시 (HR Lead 자율) + 필요 시 (CPO 판단 → HR Lead 위임, 사용자 알림 1줄). 로컬 파일 Write 만 — 외부 호출 0 (ADR-0009 범위 내). marketplace 다운로드 미채택.
- **보안**: skill 이름 allowlist (`^[a-z0-9][a-z0-9_-]{0,63}$`) + path traversal 가드.
- **doctor [31]**: skills/ 정합성 (dangling / orphan / invalid / meta 양방향, read-only).
- **마이그레이션**: optional 이라 기존 워커 0 변경 (P69 keywords 선례).

> critic + architect 검증 워커가 blocker C1 (두 dispatch 경로 prompt 조립 불일치 → 단일 주입점) 을 발견해 시정 후 박제. 검증 spec: `docs/p111-worker-skills.md`.

## [0.25.1] — 2026-05-27

### Changed — 워커 dispatch description 포맷 공식화

`subagent_type` 이 ADR-0017 로 항상 `claude` 라 Claude Code status line 첫 컬럼에 워커 정체가 안 보이던 문제. `Task` tool 의 `description` 을 `<워커명·role · 작업요약>` 포맷으로 강제해 status line 만으로 "지금 누가 도는지" 확인 가능.

- `commands/work.md` — 라우팅 절차 + dispatch 강제 노트 + 사양 + Python 진입점 주석에 포맷 명시
- `src/lskun_kit/templates/cpo.md` — CPO persona dispatch 템플릿 + 필수 포맷 노트

ADR-0017 미변경 (그 위의 운영 디테일 추가) — 신규 ADR 불필요.

## [0.25.0] — 2026-05-27

### Added — ADR-0018 박제 + doctor [27]~[30] + README onboarding (P110)

P106 메타 리뷰의 P2 묶음 (ADR + health check + onboarding) 완성. 3 sub-phase 합본 release.

**Added (P110-A — ADR-0018 박제)**:
- `docs/p110-adr-0018.md` 신규 design doc — "No external harness, doctor is the harness"
- `docs/internals/adr-index.md` 표에 ADR-0018 1행 추가
- 4회 같은 결론 재발견 패턴 차단을 위한 박제 (P106 = 1회, P110-A = 2회. 임계점 5회까지 3회 여유)

**Added (P110-B — doctor 진단 4종)**:
- `[27]` 30일+ 미 dispatch 워커 검출 — `/org --usage` 데이터 활용, 정보성 ℹ️ (자동 평가·해고 절대 금지)
- `[28]` 도메인 분포 — 빈 도메인 / 1명만 있는 도메인 (single point) 정보성
- `[29]` hired/ 의 비-워커 파일 검출 — `.md` 비-md / schema 위반 ⚠️ (자동 삭제 X)
- `[30]` archived/ dangling 검사 — ADR-0019 후 옛 archived/ 잔존 시 ℹ️ + 처리 옵션 3종 (rm/외부 이동/방치)
- 진단 24 → 28

**Added (P110-C — README onboarding)**:
- README 의 `## 5분 첫 사용` 섹션 신규 — 5단계 (init → 권한 confirm → CPO/HR 확인 → 첫 dispatch → doctor + `--usage`)
- ADR-0018 정신 박제 — "외부 harness 불필요, plugin 자체가 harness"

**원칙 준수 (ADR-0006 + ADR-0018 boundary 유지)**:
- 모든 신규 진단 = 정보성 ℹ️ — 자동 평가·해고·KPI 0
- 사용자 명시 호출 `/lskun-kit:doctor` 시점에만 실행, cron 자동 회수 X
- archived/ 자동 정리 절대 금지 (사용자 명시 rm 만)

**Tests**:
- 코드 변경 0 (doctor 는 markdown-only LLM 실행)
- 277 → 277 tests, 회귀 0 (P109 결과 유지)
- CLAUDE.md 크기 가드 통과 (P109-C 가드 활성, 12.0 KB 수준 유지)

## [0.24.0] — 2026-05-27

P106 메타 리뷰의 P1 묶음 (자기관찰 도구) 완성. 3 sub-phase 합본 release.

### Changed — CLAUDE.md slim (P109-C) — 47 KB → 11.8 KB (75% 절감)

매 세션 컨텍스트 주입되는 토큰 비용 절감 + 신규 도입자 진입장벽 완화.

**Changed**:
- CLAUDE.md 의 ADR 인덱스 22줄 → 1줄 참조 + `docs/internals/adr-index.md` (전체 표)
- CLAUDE.md 의 §6 (절대 만들지 말 것 누적, 85 lines) → 핵심 8개 요약 + `docs/internals/forbidden-history.md` (전체 65+ 항목)
- CLAUDE.md 의 §7 (디렉토리 구조 상세, 52 lines) → 핵심 5개 + `docs/internals/directory-structure.md` (전체 구조)
- CLAUDE.md 의 §8 (로드맵 Phase 1~18, 323 lines) → 1줄 참조 + `docs/internals/phase-roadmap.md` (전체 기록)
- 정보 손실 0 — 단순 위치 이동, ADR 참조 unchanged
- CPO marker 박제 영역 (사용자 프로젝트 측 CLAUDE.md) 무관 — plugin 본 repo CLAUDE.md 만 압축

**Tests**:
- `test_claude_md_size.py` 신규 3 케이스
  - hard cap 15 KB 위반 시 fail (회귀 가드)
  - soft target 8 KB 위반 시 stderr 경고 (정보성)
  - 분리된 internal docs 4종 참조 + 존재 검증
- 274 → 277 tests, 회귀 0

### Added — `/lskun-kit:audit-rotate` + doctor [26] (P109-B)

P106 메타 리뷰의 P1 두 번째 항목. `.audit/decisions.jsonl` 의 무한 누적 차단. **사용자 명시 명령만** (자동 회전 X — ADR-0006 정신).

**Added**:
- `src/lskun_kit/audit_rotate.py` 신규 — `RotationPlan` / `MonthBucket` dataclass + `plan_rotation(audit_dir, now_month)` + `execute_rotation(plan)` + `render_result(plan)`. 월별 분리 (`YYYY-MM`), 옛 월 → `decisions.<month>.jsonl.gz` (gzip), 현재 월만 평문 `decisions.jsonl` 잔존.
- `commands/audit-rotate.md` 신규 slash command (plan / `--execute`).
- doctor [26] 신규 — `decisions.jsonl` 크기 ≥ 10 MB 시 ℹ️ 회전 안내. 자동 실행 X. 진단 23 → 24.

**Tests**:
- `test_audit_rotate.py` 신규 6 케이스 (단일 월 no-op / 다월 gz 분리 / 현재 월 보존 / idempotent replay / 파일 부재 / malformed 잔존)
- 268 → 274 tests, 회귀 0

**원칙 준수**:
- 사용자 명시 명령만, 자동 회전 X — ADR-0006 §6 정합
- append-only 유지 — 옛 entry 내용 rewrite 절대 금지. 월별 묶기만
- idempotent — 재실행 시 기존 .gz 에 append (옛 데이터 손실 0)
- atomic-ish — gzip write 모두 성공 후 원본 truncate
- malformed 보존 — JSON parse 실패 라인은 회전하지 않고 현재 월에 잔존 (사용자 수동 정리)
- `/org --usage` (P109-A) 와 연동 — 회전된 파일도 read-only 집계

### Added — `/org --usage` (P109-A)

P106 메타 리뷰의 P1 첫 항목. 4 페르소나 brainstorming 결론 (외부 harness 불필요, 부족한 것 = 자기관찰 도구) 의 자연스러운 연장.

**Added**:
- `src/lskun_kit/audit_view.py` 신규 — `WorkerUsage(name, dispatches, last_seen)` dataclass + `read_usage(audit_dir)` 함수. `.audit/decisions.jsonl` (현재 월) + `decisions.<YYYY-MM>.jsonl.gz` (회전된, P109-B 와 연동) 동시 read-only 집계. best-effort (불량 JSON 라인 skip).
- `OrgReport.usage_by_worker: dict[str, WorkerUsage] | None` 필드.
- `org.build(adapter, with_usage=False)` 인자 — `with_usage=True` 시 audit_view 호출.
- `OrgReport.render(compact, show_usage=False)` 분기 — True 시 markdown table 에 컬럼 2개 (`Dispatches` / `Last seen`) 추가, compact 시 1줄 끝에 ` · N dispatches · last=<date>` append.
- `cli_org.py --usage` 옵션 신규.
- `commands/org.md` — `--usage` / `--full --usage` 사용 예 + 원칙 박제.

**Tests**:
- `test_audit_view.py` 신규 8 케이스 (단일 entry / 집계 / best-effort skip / 부재 dir / gz 회전 파일 동시 / worker 누락 / ts 누락 / non-dict JSON)
- 260 → 268 tests, 회귀 0

**원칙 준수**:
- 사용자 명시 옵션 (자동 산출 X) — ADR-0002 §5 + ADR-0006
- 평가·점수·랭킹 X — 단순 count + ISO timestamp
- audit log read-only — rewrite 절대 없음 (ADR-0006 §6 정합)

P109-B (audit log 회전) + P109-C (CLAUDE.md slim) 진행 후 0.24.0 release 예정.

## [0.23.0] — 2026-05-27

### **BREAKING — Archive 메커니즘 완전 폐기 (ADR-0019)**

P106 메타 리뷰의 연장선에서 사용자 결재로 archive 메커니즘 완전 폐기. 4 페르소나 재토론 (실사용자 / 아키텍트 / 도입자·보안 / Critic) 끝에 archive 의 잠재가치 3종 (휴지통 / 에러 메시지 / 포렌식) 모두 LSKun 1인 운영 환경에서 미실현 — 사용자가 archived/ 4명을 자료로 조회한 적 없음 — 입증. ADR-0015 결정 7-A/7-B/7-C/7-D/7-E 5개 모두 supersede.

**Changed (BREAKING)**:
- **`StorageAdapter.archive_worker(name, archived_at, archived_reason)` → `delete_worker(name)`** — frontmatter 박제·archived/ 이동·중복 가드 모두 제거. 단순 `hired/<name>.md` unlink.
- **`WorkerArchivedError` 클래스 완전 삭제** — `errors.py` 에서 제거. caller 는 `WorkerNotFoundError` 하나만 처리.
- **`routing._check_archived` + archived 가드 폐기** — `decide_target` 의 archived 분기 제거. hired 부재 = direct mode 통과 + 후속 dispatch 가 NotFound 처리.
- **`OrgReport.archived_entries` 필드 제거** + `org.build` 의 `include_archived` 인자 제거 + `report.render` 의 archived 섹션 제거.
- **`cli_org.py --include-archived` 옵션 제거**.
- **doctor [18] (archived ↔ hired display_name 중복) + [19] (audit log dangling cross-check) 제거** — 진단 25 → 23.
- **`templates/hr-lead.md` 의 해고 절차 단순화** — confirm 메시지 / `adapter.delete_worker(name)` 호출. archived/ 경로·display_name 결합 해제 안내 제거.

**Removed**:
- `archived/` 디렉토리 자동 생성 (`archive_worker` 의 부산물). plugin core 가 절대 생성하지 않음.
- `frontmatter.archived_at` / `frontmatter.archived_reason` 박제 메커니즘.
- ADR-0015 결정 7-A/7-B/7-C/7-D/7-E 5개 모두 supersede 표시.

**Tests**:
- `ArchiveWorkerTests` 5 케이스 → `DeleteWorkerTests` 2 케이스 (단순 unlink + missing raises)
- `OrgArchivedTests` 1 → `OrgArchivedRemovedTests` 1 (archived/ 무시 회귀 가드)
- `test_routing.py` 의 archived 케이스 2 → `test_deleted_worker_is_simply_missing` 1
- 264 → 260 tests (-4 net, -7 archived 제거 + 3 회귀 가드 추가), 회귀 0

**기존 사용자 자산 처리 가이드 (LSKun ~/.lskun-companies/<name>/archived/)**:
- 0.23.0 plugin 은 archived/ 디렉토리를 더 이상 참조하지 않음 (조회·라우팅·doctor 모두 무시)
- 사용자가 직접 선택:
  1. **삭제** — `rm -rf ~/.lskun-companies/<name>/archived/` (복구 불가)
  2. **보관** — 디렉토리 그대로 둠. plugin 동작에 영향 0 (단순 잔재)
  3. **외부 이동** — 다른 위치로 mv 후 사용자 별도 백업
- 자동 청소 제공하지 않음 (ADR-0019 — plugin core 가 archived/ 를 알지도 못함)

**ADR 정합**:
- ADR-0001 §3 (Stateful Workers) — JD = time-invariant state 유지. 워커 = 채용 시 완성형 정체성 유지
- ADR-0006 (audit log 불변) — audit log rewrite 금지 유지. archive 폐기와 무관
- ADR-0009 (self-contained) — plugin core 가 외부 SDK 0 유지
- ADR-0014 (reflection 폐기) — "역사 자산" 논리 약화의 일관된 연장
- ADR-0015 결정 7 5개 supersede, 단 결정 1~6 (Local SSOT 단일화 / 멱등성 init / Skill 우회 금지 / 권한 박제 / Sync 분리 / vault → sync 분리) 모두 유지

## [0.22.0] — 2026-05-27

### Added — Persona sync 백업 청소 + hired/ 스캔 백업 부산물 방어 가드 (P106 / P107)

4 페르소나 다자 토론 (실사용자 / 아키텍트 / 도입자·보안 / Critic) 의 brainstorming 결론을 박제. 진단 결과 본 plugin 은 목표에 부합하며 외부 harness (cmux/ralph/ultrawork) 도입은 불필요. 부족한 것 = **자기관찰 도구**. 본 릴리스는 그 첫 단계 (P107) — sync 백업 누적 청소 + 백업 부산물 누설 방어.

**문제 발견 (실측)**:
- LSKun 사용자 환경의 `hired/` 에 `*.lskun-pre-sync.bak[.timestamp]` 6개 누적 (cpo 3개 + hr-lead 3개)
- `/sync-persona --execute` 가 변경 발생마다 timestamp 백업을 만드는데 청소 메커니즘 부재
- 현재 `*.md` glob 은 백업 파일을 자연 배제하지만 미래 회귀 가능성 (glob 패턴 변경 / 사용자 수동 정리 사고)

**Added**:
- **`persona_sync.plan_cleanup_backups(adapter, keep=3)` + `execute_cleanup_backups(plans)`** — 메타 워커별 sync 백업 청소. 최신 mtime 순 keep 개수만 남기고 unlink. 사용자 명시 옵션만 (자동 청소 X, ADR-0015 정신).
- **`render_cleanup_report(plans, dry_run)`** — plan/result 가독 출력.
- **`commands/sync-persona.md` 갱신** — `--cleanup-backups [--keep N] [--execute]` 옵션 박제.
- **`MarkdownTreeAdapter.list_workers()` 명시적 방어 필터** — `_is_backup_artifact(filename)` 헬퍼로 `.lskun-pre-sync.bak` substring 검사. 현재 안전하나 회귀 가드.
- **doctor [24] [25] 신규** — 백업 누적 검사 + hired/ 백업 부산물 누설 시뮬레이션. 진단 항목 23 → 25.
- **`docs/p106-meta-review-and-roadmap.md`** — 4 페르소나 브레인스토밍 + P0~P3 로드맵 박제.

**Tests**:
- `BackupCleanupTests` 5 케이스 (mtime keep N / execute unlink / keep=0 / idempotent replay / negative keep raises)
- `BackupArtifactGuardTests` 3 케이스 (`.bak` suffix / timestamp suffix / `.md` 로 끝나는 백업 substring 가드)
- 256 → 264 tests (+8 신규), 회귀 0

**비고**:
- ADR-0018 ("No external harness, doctor is the harness") 박제는 P1 (audit rotate + `/org --usage` + CLAUDE.md slim) 완료 후 P109 에서 진행 예정.
- 자동 청소 / 자동 진단 회수 = 영구 금지. 사용자 명시 명령만.

## [0.21.1] — 2026-05-26

### Fixed — `persona_sync._split_body_history` substring 오탐 시정

`/lskun-kit:sync-persona` 실행 시 `hr-lead.md` template line 72 의 정당한 inline backtick 인용 `` `## Project History` `` (JD body 작성 §5 설명 줄) 을 splitter 가 history heading 으로 오탐 → body 73~165행 (해고 절차 / display_name 결합 해제 / audit dangling / 권한 경계 / 금지 사항 9항) 가 history_section 으로 잘려나가 sync 시 손상되는 버그 시정. 0.20.0 sync 시점에 실제 손상 발생 후 사용자 수동 복구로 확인.

**근본 원인**:
- `_split_body_history` 가 `heading in body` substring 매칭 사용
- inline backtick / fenced code block 내부 인용도 매칭되어 false positive

**Fixed**:
- `src/lskun_kit/persona_sync.py` — substring 매칭 → 줄 시작 (`^## ...`) 매칭. fenced code block (``` ``` ``` / ``` ~~~ ```) 내부 라인 제외. inline backtick 인용은 줄 시작이 아니므로 자연 배제.

**Tests**:
- 신규 `SplitBodyHistorySplitterTests` 5 케이스 (inline backtick / fenced ``` / 진짜 heading / archived heading / ~~~ fenced)
- 기존 `test_no_history_remains_no_history_after_sync` 갱신 — substring 검사 → 줄 시작 heading 검사로 정확화
- 전체 251 → 256 tests, 회귀 0

**복구 가이드 (0.20.0 sync 사용자)**:
- 0.21.1 plugin 업데이트 후 `/lskun-kit:sync-persona` 재실행 — splitter 정상 동작으로 hr-lead.md body 전체가 정상 sync.
- 0.20.0 sync 직후 손상 백업 (`<name>.md.lskun-pre-sync.bak`) 이 남아 있으면 진단 비교 가능.

## [0.21.0] — 2026-05-26

### Changed — Dispatch subagent_type Allowlist 정책 전환 ([ADR-0017](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0017-2026-05-26-dispatch-subagent-allowlist.md))

4회째 재발한 메인 LLM 의 자의적 OMC executor dispatch 우회 (LSKun 본진 세션, 2026-05-26) 의 근본 시정. ADR-0016 의 denylist (OMC + general-purpose 만 차단) 가 4회째 우회됨을 입증 → **Allowlist 모델로 전환**. 활성 회사 marker 박힌 cwd 에서는 `subagent_type="claude"` 만 정식 dispatch 로 허용.

**Changed (BREAKING for marker-active projects)**:
- **`pre_tool_use.py` allowlist 전환** — `_OMC_BLOCK_PREFIXES` / `_OMC_BLOCK_EXACT` 제거. `_ALLOWED_SUBAGENT = frozenset({"claude"})` 신설. `subagent_type` 미지정/null 은 일반 Task 호출로 allow 유지.
- **차단 범위 확장** — OMC + general-purpose + 외부 plugin subagent (vercel:* / codex:* / figma:* / posthog:* 등) + read-only agent (Explore / Plan) 모두 deny. 회사 외 작업이면 escape hatch 1회 set.
- **평가 순서 7 → 8단계** — claude 정식 dispatch (#7) + allowlist fallthrough deny (#8) 추가.

**Added**:
- **신규 정식 escape hatch `LSKUN_ALLOW_NON_CLAUDE_DISPATCH=1`** — 의미 명확 (denylist 잔재 명칭 탈피). 활성 시 stderr 경고.
- **ADR-0016 별칭 `LSKUN_ALLOW_OMC_FALLBACK=1`** 영구 유지 — 하위호환 (기존 사용자 자산 보존). 둘 중 하나라도 set 이면 통과.
- **Skill 문서 + persona template 박제** — `commands/work.md` §"메인 세션 CPO 라우팅" / §사양 / §"Python 진입점", `templates/cpo.md` §"Task tool 로 워커 dispatch" + §"폐기·금지", `templates/hr-lead.md` §채용 모두 `subagent_type="claude"` 강제 명시. Skill 문서가 dispatch subagent 를 규정 (4회 재발의 근본 원인 = Skill 문서 미규정 시정).
- **doctor 진단 [22] [23]** — Allowlist 가드 활성 검증 + bypass env 영구 export 검출 (zshrc/bashrc/zprofile/bash_profile grep).
- **테스트 8건 신규 + 10건 갱신** — `AllowlistAdr0017NewTests` (claude allow / vercel deny / codex deny / Explore deny / 두 bypass var / chain 우선 등). `DispatchAllowlistTests` 의 Explore/Plan/외부 plugin allow → deny 반전. 전체 회귀 0 (251 tests).

**Breaking 가이드**:
- marker 박힌 프로젝트에서 OMC executor 외 다른 plugin subagent (vercel/codex/figma 등) 를 정당 사용하던 사용자: 세션 단위로 `export LSKUN_ALLOW_NON_CLAUDE_DISPATCH=1` 또는 별칭 `LSKUN_ALLOW_OMC_FALLBACK=1`. `.zshrc`/`.bashrc` 영구 export 는 doctor [23] 가 경고.
- Explore / Plan 도 차단됨 — 사용자 의도 정당 사용은 escape hatch 필요.

**검증**: 251/251 tests 통과 (기존 233 + 갱신 10 + 신규 8). 회귀 0.

**잔존 위험** (ADR-0017 §"인지된 잔존 위험" 명시):
- `subagent_type` 미지정 Task 호출에 prompt 만 워커 흉내 — 일반 Task 로 allow. text instruction 가드.
- `Skill(skill="oh-my-claudecode:executor", ...)` 직접 호출 — Task matcher 가 Skill 미포착. 5회째 발생 시 새 ADR.
- plugin 개발자 본인 dogfood 시나리오 (cwd mismatch) — marker 비활성. escape hatch 또는 cwd 이동.

## [0.20.0] — 2026-05-26

### Added — 호출자 측 OMC fallback 차단 ([ADR-0016](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0016-2026-05-26-omc-fallback-block.md))

3회째 재발한 메인 LLM 의 자의적 OMC executor dispatch 우회를 PreToolUse:Task hook 레벨에서 차단. ADR-0015 가 plugin core 측 (Skill 실패 → fallback) 을 막은 것을 호출자 측 (Skill invoke 누락 → Agent + OMC executor 직행) 으로 확장.

**Added**:
- **`pre_tool_use.py` OMC fallback 차단 분기** — 활성 회사 marker 박힌 프로젝트에서 `subagent_type` 이 `oh-my-claudecode:*` (prefix) 또는 `general-purpose` (exact) 인 Task 호출을 deny. Explore/Plan/외부 plugin agent 는 통과 (가드 범위 '중')
- **`LSKUN_ALLOW_OMC_FALLBACK=1` escape hatch** — chain bypass 와 동일 패턴. 활성 시 stderr 경고
- **`LSKUN_HOOK_DEBUG_DUMP=1` 실측 모드** — ADR-0016 결정 3. 임시 stderr payload dump (실측 후 unset). 구현 phase 첫 작업에서 `subagent_type` 키 위치 실측 용
- **doctor 진단 항목 [20] [21]** — OMC 가드 활성 검증 + bypass env var 영구 export 검출 (zshrc/bashrc/zprofile/bash_profile grep)
- **테스트 10건 신규** — `OmcFallbackBlockTests` (차단/허용/bypass/chain 우선순위 등). 기존 chain 차단 7건 회귀 0

**Changed**:
- **`_decide()` 평가 순서 명문화** — 1) non-Task → allow, 2) chain bypass, 3) OMC bypass, 4) marker 부재 → allow, 5) 활성 워커 세션 → chain deny, 6) `subagent_type` 차단 → OMC deny, 7) fallthrough → allow. chain 차단이 OMC 차단보다 우선 (결정 7)
- **활성 회사 marker 검출 2층** — 1순위 `LSKUN_SSOT_ROOT` env var (O(1)), 2순위 cwd 상위 CLAUDE.md marker (session_start 의 `_find_active_company_root()` 재사용)

**비-Breaking**: marker 박힌 프로젝트에서 OMC executor 를 정당하게 사용하던 사용자는 `LSKUN_ALLOW_OMC_FALLBACK=1` 1회 set 필요 (세션 단위 권장, shell profile 영구 export 는 doctor [21] 가 경고).

**검증**: 17/17 tests 통과 (기존 7 + 신규 10). 전체 회귀 0.

**잔존 위험** (ADR-0016 §"인지된 잔존 위험" 명시):
- Explore/Plan 에 LSKun 워커 persona 흉내 주입 — text instruction 으로만 가드
- `Skill(skill="oh-my-claudecode:executor", ...)` 직접 호출 — Task matcher 밖. 모니터링 대상
- Bash 경유 `codex` CLI 직접 실행 — 우회 가능. 모니터링 대상

## [0.19.0] — 2026-05-22

### Changed — Local SSOT 단일화 + 멀티 프로젝트 회사 공유 ([ADR-0015](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0015-2026-05-22-multi-project-company-sharing.md))

**Breaking**:
- **Vault backend 폐기** — `adapters/vault.py` 삭제, `LSKUN_VAULT` / `LSKUN_COMPANY` env var plugin core 참조 제거. 기존 vault 사용자는 `/lskun-kit:sync-in <name> <vault-path>` 로 1회 마이그레이션 (README §"사용 흐름 0)")
- **`<project>/.company/` 폐기** — 회사 SSOT 단일 위치 `~/.lskun-companies/<name>/` (`paths.company_root(name)` 단일 진입점). 옛 위치는 사용자 수동 정리
- **`/lskun-kit:migrate` 명령 삭제** — Local ↔ Vault 양방향 도구 폐기. 대체: `/sync-in` / `/sync-out`

### Added
- **`paths.py`** — `~/.lskun-companies/<name>/` + `~/.lskun-companies/.backups/<name>/` 의 단일 진입점. `validate_company_name` (영문/숫자/_/-/. + 시작 영문/숫자, `.backups` 예약어)
- **`LocalAdapter.from_company_name(name)`** — 회사 이름으로 adapter 생성 (절대경로 인자 인터페이스도 유지)
- **`permissions.py`** — `~/.claude/settings.json` 의 `permissions.allow` 에 5개 패턴 자동 박제 (Read/Edit/Write/Bash ls/cat). 멱등 + atomic-ish write + ConfirmRequired 패턴
- **`sync.py` + `/sync-in` + `/sync-out`** — 외부 mirror ↔ Local SSOT 파일시스템 복사 (`shutil.copytree`). 백업 자동 (sync-in: `~/.lskun-companies/.backups/`, sync-out: target sibling). 외부 SDK 0
- **`init.py` 멱등성 4행** (결정 2-B): founded / joined / silent / marker_replaced. 다른 회사 marker 재진입 시 `ConfirmRequired` raise (옵션 B — plugin core 가 stdin 안 잡음, LLM caller 가 confirm 후 재호출)
- **`hooks/session_start.py` marker-based** — CLAUDE.md LSKUN-CPO marker 가 회사-프로젝트 결합의 단일 진실원. cwd `.company/` 탐색 폐기
- **`extract_company_name(project_root)`** — marker 본문에서 회사 이름 추출 (init 의 cross-check, hook 의 resolve)
- **`WorkerArchivedError`** + **`archive_worker(name, archived_at, archived_reason)`** — ADR-0015 결정 7. archive 시점에 frontmatter 박제 (display_name 보존 — 자동 익명화 금지). routing.py 의 archived 가드 (결정 7-E)
- **doctor 진단 신규 2종** — [18] archived ↔ hired display_name 중복 검출 (결정 7-C), [19] audit log dangling cross-check (결정 7-D, rewrite 금지)
- **CPO templates 의 Skill 경유 강제** (결정 3-A/3-B) — Task tool 의 `oh-my-claudecode:*` / `general-purpose` fallback 영구 금지 (novacare 사건 재발 차단)

### Removed
- `adapters/vault.py` + `VaultAdapter` / `VaultCompanyNotFoundError` / `list_companies` (vault 헬퍼)
- `src/lskun_kit/migration.py` (Local ↔ Vault SHA-256 양방향) + `commands/migrate.md` + `docs/migration-spec.md`
- `init.py` 의 `ENV_VAULT` / `ENV_COMPANY` / `detect_backend` / `detect_dual_backend`
- `LSKUN_VAULT` / `LSKUN_COMPANY` env var plugin core 참조 모두 (총 0건)

### Notes — 검증 (ADR-0015 §검증 기준 6 항목)
- 215 → 227 tests (+12), 회귀 0
- novacare 같은 임의 프로젝트에서 sandbox 차단 0
- 1 회사 N 프로젝트 공유 가능 (5개 이상 검증)
- plugin core 의 vault 직접 참조 0건
- /init 멱등성 4행 명세 박제 + 사용자 confirm 패턴 일관 (P89 / P90 도 같은 ConfirmRequired 패턴)
- 워커 해고 → 같은 role 재채용 시나리오 정상

### Catch-up — 0.18.0 (ADR-0014 Reflection 폐기)
P78~P82 동안 ADR-0014 박제 시점에 CHANGELOG 항목 작성이 누락되었다. 0.10.0 정신과 동일하게 ADR-0014 문서가 1차 진실원으로 남으며, 본 entry 는 0.18.0 → 0.19.0 변화만 기록.

## [0.11.0] — 2026-05-20

### Changed — Plugin version single-source SSOT ([ADR-0012](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0012-2026-05-20-single-source-version.md))
- `.claude-plugin/plugin.json` 의 `version` 필드를 **유일한 version 진실원** 으로 확정
- `src/lskun_kit/__init__.py` 의 `__version__` 을 hardcode `"0.8.0"` → `plugin.json` 동적 parse 로 교체. import 시점 1회 평가, stdlib only (ADR-0009 self-contained 유지). Persona sync provenance (`lskun-kit@<version>`) 가 자동으로 정합화됨
- `.claude-plugin/marketplace.json` 의 `version` 필드 제거 — spec 상 fallback (1순위 = plugin.json) 이라 작동 영향 0, drift 원천만 제거
- `CLAUDE.md` §7 디렉토리 트리의 `# version: …` 주석 제거 + §1 "버전" 라인을 plugin.json 참조 안내로 교체
- `README.md` Status 라인 — 숫자 박제 제거, plugin.json SSOT 안내로 교체
- `commands/{sync-persona,doctor,org}.md` 의 예시 출력 — `0.8.0` 등 hardcode → `<plugin-version>` / `<ver>` placeholder

### Notes — Release 절차 단순화
- 박제 위치 7곳 → 1곳 (`plugin.json` 만 bump)
- 누락 위험 0
- 기존 110+ test 영향 없음 (test fixture 의 `"0.8.0"` 는 sync 로직 검증용 임의 값, plugin 자체 version 과 무관)

### Catch-up — 0.9.0 / 0.10.0
P60~P70 동안 ADR-0010 (persona sync) / ADR-0011 (JD 기반 채용) 박제 시점에 plugin.json 은 bump 됐으나 CHANGELOG 항목 작성이 누락되었다. 본 ADR-0012 가 의도하는 "단일 SSOT" 정신상 CHANGELOG 항목 역추적 작성은 본 phase 범위 밖이며, ADR-0010 / ADR-0011 문서가 1차 진실원으로 남는다.

## [0.8.0] — 2026-05-19

### Added — Persona sync + provenance + 조직도 view ([ADR-0010](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0010-2026-05-19-persona-sync-and-provenance.md))
- `/lskun-kit:sync-persona` — 메타 워커 (CPO / HR Lead) body 를 plugin 최신 template 와 sync. frontmatter / Project History 절대 보존, idempotent, 자동 백업
- `/lskun-kit:org` — 회사 조직도 read-only view (CPO / HR / Worker 카테고리별 + 도메인 분포 + persona sync 상태 요약)
- `lskun_kit.persona_sync` 모듈 — `plan` / `execute` / `diff_text_for` + plan→confirm→execute 패턴
- `lskun_kit.org` 모듈 — `build()` / `OrgReport.render()`
- Worker frontmatter optional 필드 — `persona_synced_from` (예: `lskun-kit@0.8.0`) + `persona_synced_at` (ISO date)
- `init.run()` 의 CPO/HR Lead hire 시 자동으로 provenance 박제
- `/lskun-kit:doctor` 항목 15 (Persona sync 상태) + 항목 16 (조직도 한 줄 요약) 신설
- 신규 테스트 — `test_persona_sync.py` (9건) + `test_org.py` (8건)

### Changed
- slash command frontmatter description 의 ADR / P-번호 사족 제거 — 사용자 일람에서 노출되는 한 줄을 동작 중심으로 정리
- 명령 본문의 ADR 인용 / "## 사양 참조" 류 섹션 제거 — 명령 사양은 외부 동작 정의에 집중, ADR 추적은 vault 측만

### Notes — Idempotent sync 보장
- 이미 sync 된 상태에서 재실행 → no-op (백업 0)
- body 는 sync 됐지만 provenance 부재 (기존 회사) → provenance 만 박제

## [0.7.0] — 2026-05-19

### Removed / Reverted — ADR-0007 폐기 ([ADR-0008](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0008-2026-05-19-local-first-no-link.md))
- **`.claude/lskun-kit.json`** 프로젝트→회사 link 메커니즘 전체 revert (PR #20)
- `src/lskun_kit/project_link.py` 삭제
- `tests/test_project_link.py` 삭제
- `commands/role-init.md` 삭제
- `init.py` 의 link 박제 로직 제거
- ADR-0007 status → `superseded by ADR-0008`

### Decision — ADR-0009 (self-contained default)
- Plugin core 는 외부 시스템 (Obsidian vault, Notion 등) 에 종속되지 않는다
- Local backend 만으로 모든 핵심 메커니즘 완전 동작 (Reflection / Workers / CPO 결재 / audit)
- Vault 는 명시 opt-in 통합 (`LSKUN_VAULT` env var 설정 시에만 활성화)
- "future: Notion" 등 외부 통합 promise 폐기 — 실제 도입 시 별도 ADR + add-on package
- plugin core 안에서 외부 SDK / API 호출 영원히 금지
- 문서 디커플링: 사용자 vault 절대경로 → 추상 placeholder (`<your-vault>/`, `<your-project>/`)
- adapters/__init__.py / base.py docstring 의 "(Notion API 등)" 일반화
- CLAUDE.md 의 저자 개인 Developer SSOT hub 경로 박제 제거

### Decision — ADR-0008
- ADR-0001 §4 backend 모델 그대로 유지 (Local default + Vault optional, 동등)
- ADR-0004 §1 "CLAUDE.md marker = 진실원" 복원 (ADR-0007 §4 의 "캐시" 강등 철회)
- SSOT 2축 유지 (개발자 / 회사 운영). 사용자 프로젝트는 작업 위치이며 SSOT 아님
- multi-project 단일 회사 케이스 발생 시 별도 ADR + `/lskun-kit:promote` 사후 도입 (현재 미도입)
- 사유: 3명 전문 에이전트 (architect / critic / analyst) 만장일치 ADR-0007 폐기 권고. YAGNI / dead artifact / 인프라:핵심 2.7:1 / 24h 자기 모순 / revert 비용 << 유지 비용

### Retained from 0.6.0-dev (P52 — ADR-0006)
- `lskun_kit.audit` 모듈 / `.audit/decisions.jsonl` / verdict enum 4종 / doctor 항목 14
- (상세 변경 사항은 아래 [0.6.0] 섹션 참조)

## [0.6.0] — 2026-05-18

### Added — CPO 결재 audit log ([ADR-0006](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0006-2026-05-18-cpo-decision-audit.md))
- `lskun_kit.audit` 모듈 — `AuditEntry` dataclass + `record()` + `new_request_id()`
- `.audit/decisions.jsonl` (append-only JSONL) 에 CPO 결재 1건당 1줄 박제
- verdict enum 4종 — `approved` / `rework` / `rejected` / `rerouted`
- `StorageAdapter.append_audit()` 확장 (default `NotImplementedError`, `MarkdownTreeAdapter` 구현 제공)
- `reflection.record(request_id=...)` optional kwarg — audit ↔ reflection link
- `/lskun-kit:doctor` 항목 14 신설 — `.audit/decisions.jsonl` schema 검증 + dual-backend 가드
- CPO persona (`templates/cpo.md`) — 결재 직후 `audit.record()` 호출 의무 (책임 8 + Approval Loop step 5)

### Guarantees (불변, ADR-0006 §6)
- append-only (overwrite / delete 금지)
- 1줄 1 JSON object (single-line)
- `request_id` 필수
- `verdict` enum 외 거부
- `.audit/` 자동 생성

### Changed
- CLAUDE.md §6 폐기 목록 — ADR-0006 의 5개 금지 추가 (자동 분석 / 자동 평가·해고 / 자동 회고 / 위원회 / 외부 전송)
- CLAUDE.md §1 정체성 + §7 디렉토리 트리 — audit.py 박제

### Tests
- `tests/test_audit.py` 신규 — schema 검증 + append-only + dual newline 거부 + request_id 유일성 + reflection link kwarg (16 tests)

## [0.5.0] — 2026-05-18

### Added
- `/lskun-kit:migrate-schema` — v0.2 / v0.3 schema 회사를 v0.4 (6 필수 필드 + CLAUDE.md marker) 로 끌어올리는 사용자 confirm 기반 마이그레이션 도구 ([ADR-0005](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0005-2026-05-18-schema-migration.md))
- 변환 계획 dry-run + 인터뷰 응답 기반 실행 2단계
- 변경 전 `<file>.lskun-pre-migrate.bak` 자동 백업
- CPO / HR Lead 의 `domain: meta` 자동 부여 (인터뷰 생략)
- `lskun_kit.schema_migration` 모듈 — `plan` / `execute` / `detect_worker_schema` / `detect_company_schema`

### Guarantees (불변)
- `## Project History` 섹션은 한 줄도 변경하지 않음
- 기존 frontmatter 키 절대 덮어쓰지 않음 (누락 키만 추가)
- 백업 강제 (skip 옵션 없음)

### Changed
- `/lskun-kit:doctor` — schema 누락 시 안내 메시지에 `/lskun-kit:migrate-schema --dry-run` 경로 명시
- ADR-0004 §6 의 "frontmatter 5→6 자동 마이그레이션 X" 단서 조항 폐기 (ADR-0005 §1)

## [0.4.0] — 2026-05-18

### Added
- PreToolUse chain-guard hook — 워커 → 워커 chain 차단 (ADR-0004 §8)
- HR Lead 자동 채용 rate-limit + audit log (`hire_audit.py`)
- CPO 라우팅 시나리오 회귀 가드 테스트

### Changed
- Hook bootstrap 을 `python3 -m lskun_kit...` → `python3 ${CLAUDE_PLUGIN_ROOT}/src/lskun_kit/hooks/*.py` 직접 경로 호출로 변경 (ModuleNotFoundError 방지)
- `doctor` 진단 항목 13개로 확장

### Removed
- `metrics.py` — KPI 측정 폐기 정책 (ADR-0002 §5) 에 맞춰 dead code 제거

## [0.3.0] — 2026-05-18

### Added — Leader-Worker pivot ([ADR-0004](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0004-2026-05-18-leader-worker-pivot.md))
- 메인 세션 자체가 회사의 **CPO** 로 동작 — `/lskun-kit:work "..."` (이름 생략) 호출 시 CPO 가 라우팅·결재·응답
- CPO 의 **자동 채용** — 적합 워커 부재 시 HR Lead 를 Task tool 로 호출하여 즉시 채용 (사용자 알림 1줄, 차단 X)
- `display_name` 필수 필드 — 사람 이름 (자동 생성 금지)
- `model` optional 필드 — `sonnet` / `opus` / 모델 ID alias 지원
- `/lskun-kit:init` 5단계 인터뷰 (회사 이름 / 소개 / 도메인 / CPO 이름 / HR 이름)
- 사용자 프로젝트 `CLAUDE.md` 에 `<!-- LSKUN-CPO:START -->` ~ `<!-- LSKUN-CPO:END -->` marker 로 CPO persona inline 박제
- SessionStart hook — 활성 회사·hired·history 동적 컨텍스트 자동 주입
- `--model` / `--domain` 옵션 — `/lskun-kit:hire`, `/lskun-kit:work`

### Added — Domain-aware workers ([ADR-0003](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0003-2026-05-18-domain-aware-workers.md))
- 워커 frontmatter `domain` 필수 필드 — 같은 `role` 이라도 회사 도메인별 reflection history 분리
- CPO 라우팅 0순위 = 회사 `domain` 일치 워커

### Removed (폐기)
- CPO/HR 외 임원 자동 추가 (COO/CTO/PM 등) — ADR-0002 §6
- 워커 → 워커 chain (sub-leader 출현 방지) — ADR-0004 §8

## [0.2.0] — 2026-05-18

### Added — CPO/HR pivot ([ADR-0002](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0002-2026-05-18-cpo-hr-pivot.md))
- `/lskun-kit:init` — 신규 회사 단일 셋업 진입점 (CPO + HR Lead 자동 hire)
- `/lskun-kit:doctor` — 환경 진단 명령
- CPO / HR Lead persona 템플릿 — `cpo.md` (chief-product-officer) + `hr-lead.md`

### Removed (폐기)
- Dogfooding / KPI 측정 (ADR-0002 §5) — 정성 검증으로 전환

## [0.1.0] — 2026-05-15

### Added — 창설 ([ADR-0001](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0001-2026-05-15-stateful-workers-clean-slate.md))
- Plugin manifest (`.claude-plugin/plugin.json`, `marketplace.json`)
- StorageAdapter 추상화 — Local (`.company/`) / Vault (`<vault>/03_Companies/<name>/`)
- Reflection — Stop hook 이 작업 종료 시 `hired/<worker>.md` 의 `## Project History` 에 1줄 자동 append
- `/lskun-kit:hire` — 워커 박제 primitive
- `/lskun-kit:work` — 워커 호출 (history 컨텍스트 자동 주입)
- `/lskun-kit:reflect` — 수동 reflection 보강
- `/lskun-kit:migrate` — Local ↔ Vault SHA-256 무결성 이동
- SSOT 분리 정책 — plugin 개발자 SSOT (본 repo + obsidian-vault/02_Projects) vs 사용자 SSOT (`.company/` 또는 `<vault>/03_Companies/`)

### Principles (불변)
- Zero-Base — 옛 ai-company / claude-company-kit 자산 0 승계 (컨셉만)
- Ceremony 0 — 시작/종료에 `.md` 1줄씩만
