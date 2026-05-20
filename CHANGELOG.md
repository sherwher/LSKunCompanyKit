# Changelog

본 문서는 사용자 입장에서 LSKunCompanyKit 의 릴리스별 변경 사항을 정리한다.
모든 design pivot 은 [ADR](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/) 박제 후에만 코드에 반영된다.

본 changelog 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 를 따르며, 버전 관리는 [SemVer](https://semver.org/lang/ko/) 를 지향한다 (0.x 동안은 minor 단위 breaking 가능).

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
