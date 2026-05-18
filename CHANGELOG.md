# Changelog

본 문서는 사용자 입장에서 LSKunCompanyKit 의 릴리스별 변경 사항을 정리한다.
모든 design pivot 은 [ADR](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/) 박제 후에만 코드에 반영된다.

본 changelog 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) 를 따르며, 버전 관리는 [SemVer](https://semver.org/lang/ko/) 를 지향한다 (0.x 동안은 minor 단위 breaking 가능).

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
