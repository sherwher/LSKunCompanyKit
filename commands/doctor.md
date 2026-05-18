---
name: lskun-kit:doctor
description: LSKunCompanyKit 환경 진단 — Plugin manifest, backend, SSOT 분리, init 상태, CPO/HR 존재 여부, hook 등록
---

# /lskun-kit:doctor

LSKunCompanyKit 의 실행 환경을 진단한다. **읽기 전용** — 파일을 수정하지 않는다.

본 명령은 ADR-0002 §3 (init 명령) 도입 이후 진단 항목이 확장되었다. 이전 P3 단계의
"P6/P7 미구현" 표기는 제거됐다.

---

## 진단 항목 (9개)

순서대로 점검 후 ✅ / ⚠️ / ❌ 표기.

### 1. Claude Code 버전

- `claude --version` 캡처
- 캡처 실패 시 ⚠️

### 2. Plugin manifest 무결성

- `.claude-plugin/plugin.json` 존재 + `name == "LSKunCompanyKit"`
- `.claude-plugin/marketplace.json` 존재 + plugin 항목 ≥ 1
- namespace 가 `/lskun-kit:*` 임 확인

### 3. Storage backend 후보 탐색

- Local: `<project-root>/.company/`
- Vault: `$LSKUN_VAULT` 환경변수 → `03_Companies/<company>/`
- 각 backend 별로 존재 여부 / `company.md` 유무 / `hired/` 워커 수 / 마지막 history append 시각

### 4. SSOT cross-contamination 검증

- 본 repo 루트에 `hired/` 같은 회사 운영 데이터가 있으면 ❌
- 사용자 SSOT 위치에 ADR / Phase 계획 같은 plugin 설계 문서가 있으면 ❌

### 5. Worker frontmatter schema 검증

- 각 `hired/<worker>.md` 의 frontmatter 필수 4 필드 (`name`, `role`, `hired_at`, `storage_backend`) 점검
- `## Project History` 섹션 존재 여부 (없으면 ⚠️ 만)

### 6. Reflection hook 등록 상태

- `~/.claude/settings.json` 또는 프로젝트 `.claude/settings.json` 의 Stop hook 배열에 `python3 -m lskun_kit.hooks.stop_reflect` 포함 여부
- 미등록 시 ⚠️ + 등록 가이드

### 7. Migration tool 준비

- `/lskun-kit:migrate` 명령 등록 여부

### 8. **init 실행 상태 (P15 신설)**

활성 backend 의 회사 루트가 비어있는지 (= init 미실행) 확인:

- `company.md` 없음 → ⚠️ "init 미실행. `/lskun-kit:init` 을 실행하라"
- `company.md` 있음 → ✅

### 9. **CPO / 인사팀장 존재 여부 (P15 신설)**

ADR-0002 §1~§2 의 2명 자동 hire 워커가 backend 에 있는지 확인:

- `hired/cpo.md` 없음 → ⚠️ "CPO 미hired. `/lskun-kit:init` 재실행 권장"
- `hired/hr-lead.md` 없음 → ⚠️ 동일
- 둘 다 있음 → ✅

> backend 가 아예 없는 (Local/Vault 둘 다 없음) 초기 상태는 8 / 9 둘 다 "(N/A — backend 없음)" 으로 skip.

---

## 출력 포맷 (예시)

```
LSKunCompanyKit doctor (v0.2.0-dev)
================================================

[1] Claude Code 버전              : ✅ <version>
[2] Plugin manifest               : ✅ name=LSKunCompanyKit, namespace=/lskun-kit:*
[3] Storage backend
      Local  (<path>)             : ⚠️  .company/ 없음
      Vault  (<path>)             : ✅ workers=3, last_history=2026-05-17
[4] SSOT cross-contamination       : ✅ 분리 정상
[5] Worker frontmatter             : ✅ 3/3 통과
[6] Reflection hook                : ⚠️  Stop hook 미등록 — 등록 가이드 참조
[7] Migration tool                 : ✅ /lskun-kit:migrate 등록됨
[8] init 실행 상태                  : ✅ company.md 존재
[9] CPO / 인사팀장                  : ✅ cpo, hr-lead 모두 hired

결과: 환경 정상. 일상 사용 가능.
```

---

## 실패 시 가이드

- ❌ 발생 시 사용자에게 수정 방법 제시. **자동 수정은 하지 않는다** (읽기 전용 보장).
- cross-contamination 발견 시 ADR-0001 §5 / CLAUDE.md §4 링크 출력.
- init 미실행 시 ADR-0002 §3 / `/lskun-kit:init` 안내.

---

## 구현 노트

본 사양은 slash command 의 **외부 동작 정의**. 실제 진단 로직은 Phase 1 의 storage adapter +
Phase 2 의 `lskun_kit.init.resolve_company_root` / `adapter.list_workers()` 를 조합해 구현한다.
