---
name: lskun-kit:doctor
description: LSKunCompanyKit 환경 진단 — Plugin manifest, backend, SSOT 분리, init 상태, CPO/HR 존재 여부, CPO persona CLAUDE.md 박제, hook 등록 (ADR-0001~0004)
---

# /lskun-kit:doctor

LSKunCompanyKit 의 실행 환경을 진단한다. **읽기 전용** — 파일을 수정하지 않는다.

본 명령은 ADR-0002 (init 명령), ADR-0003 (domain 필드), ADR-0004 (메인 세션 = CPO + display_name + model), ADR-0006 (CPO 결재 audit log) 의 도입에 따라 진단 항목이 확장됐다.

---

## 진단 항목 (14개)

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
- **P33 — dual-backend 감지**: 양쪽 다 `company.md` 보유 시 ⚠️ "history 박제가 한쪽에만 누적될 위험. `/lskun-kit:migrate` 로 동기화 권장 (자동 마이그레이션은 ADR-0001 §5 SSOT 정책상 금지)." `lskun_kit.init.detect_dual_backend` 호출.

### 4. SSOT cross-contamination 검증

- 본 repo 루트에 `hired/` 같은 회사 운영 데이터가 있으면 ❌
- 사용자 SSOT 위치에 ADR / Phase 계획 같은 plugin 설계 문서가 있으면 ❌

### 5. Worker frontmatter schema 검증 (ADR-0003 + ADR-0004 §6)

- 각 `hired/<worker>.md` 의 frontmatter **필수 6 필드** (`name`, `role`, `domain`, `hired_at`, `storage_backend`, `display_name`) 점검
- `## Project History` 섹션 존재 여부 (없으면 ⚠️ 만)
- `display_name` 누락 워커는 ⚠️ + "P50/ADR-0005 — `/lskun-kit:migrate-schema --dry-run` 으로 변환 계획 확인 후 `/lskun-kit:migrate-schema` 실행 권장. 수동 편집 불필요."

### 6. Reflection hook 등록 상태

- plugin 자체의 `hooks/hooks.json` 에 SessionStart + **Stop** hook 둘 다 박제되어 있는지 점검 (default-on 검증)
- 사용자가 `~/.claude/settings.json` 등에서 본 plugin 의 hook 을 override / disable 했는지 best-effort 캡처
- plugin manifest 에 Stop hook 누락 시 ❌ (ADR-0001 §3 핵심 메커니즘 #1 무력화)
- plugin manifest 정상이고 사용자 override 없으면 ✅

### 6b. PreToolUse chain-guard hook (ADR-0004 §8, P31 신설 / P48 경로 형식)

- plugin `hooks/hooks.json` 의 PreToolUse 배열에 `pre_tool_use.py` 직접 경로 호출 (matcher=`Task`) 포함 여부
- 모든 hook command 는 P48 부터 `python3 ${CLAUDE_PLUGIN_ROOT}/src/lskun_kit/hooks/*.py` 형식. `python3 -m lskun_kit...` 형식이 남아있으면 ❌ "ModuleNotFoundError 발현 가능 — P48 회귀"
- 미등록 시 ❌ "워커 → 워커 chain 차단 무력화 — ADR-0004 §8 위반 가능"
- `LSKUN_ALLOW_WORKER_CHAIN=1` 환경변수 설정 감지 시 ⚠️ "chain enforcement bypass 활성화 중 — 디버깅 외 비권장"

### 7. Migration tool 준비

- `/lskun-kit:migrate` 명령 등록 여부

### 8. init 실행 상태

활성 backend 의 회사 루트가 비어있는지 (= init 미실행) 확인:

- `company.md` 없음 → ⚠️ "init 미실행. `/lskun-kit:init` 을 실행하라"
- `company.md` 있음 → ✅

### 9. CPO / 인사팀장 존재 여부

ADR-0002 §1~§2 의 2명 자동 hire 워커가 backend 에 있는지 확인:

- `hired/cpo.md` 없음 → ⚠️ "CPO 미hired. `/lskun-kit:init` 재실행 권장"
- `hired/hr-lead.md` 없음 → ⚠️ 동일
- 둘 다 있음 → ✅

### 10. **회사 domain 박제 (ADR-0003)**

- `company.md` 의 frontmatter 에 `domain` 필드 존재 여부
- 없거나 빈 문자열 → ⚠️ "도메인 미박제 — `/lskun-kit:migrate-schema` 로 보강 (ADR-0005)."
- 있음 → ✅ + 값 출력

### 11. **CPO persona CLAUDE.md 박제 (ADR-0004 §1, P23 신설)**

사용자 프로젝트 root 의 `CLAUDE.md` 안에 `<!-- LSKUN-CPO:START -->` ~ `<!-- LSKUN-CPO:END -->` marker 구간 존재 여부:

- 없음 → ⚠️ "CPO persona 미박제 — 메인 세션이 CPO 로 동작하지 않음. `/lskun-kit:migrate-schema` (ADR-0005) 또는 `/lskun-kit:init` 재실행."
- 손상 (start 만 있고 end 없음) → ⚠️ "marker 손상 — 수동 수정 또는 재박제 필요"
- 정상 → ✅
- **P34 — 백업 파일 감지**: `CLAUDE.md.lskun.bak` 가 존재하면 ⚠️ "직전 init 가 marker 내 사용자 손편집을 감지해 백업했다. 내용 비교 후 백업 제거 권장."

### 12. **CPO 모델 권장 (ADR-0004 §4, P23 신설)**

CPO 는 메인 세션의 사용자 `/model` 설정에 의존 (plugin 강제 불가). Claude Code 의 현재 모델이 Opus 계열인지 확인:

- 현재 모델 ID 가 `opus` 포함 → ✅ "권장 모델 사용 중"
- 그 외 (Sonnet / Haiku) → ⚠️ "CPO 결재·라우팅 정확도 향상을 위해 `/model opus` 권장 (강제 아님)"
- 모델 정보 캡처 불가 → ⚠️

### 13. **Worker model 필드 (ADR-0004 §4, P23 신설)**

- 각 `hired/<worker>.md` 의 optional `model` 필드 점검
- 없으면 ✅ "default = sonnet"
- "sonnet" / "opus" / 모델 ID 명시면 ✅ + 값 출력

### 14. **CPO 결재 audit log (ADR-0006, P52 신설)**

활성 backend 의 `<company-root>/.audit/decisions.jsonl` 무결성:

- 파일 부재 → ✅ "audit 박제 미시작 (첫 결재 시 자동 생성)" — 정보성, ⚠️ 아님
- 파일 존재 + 모든 줄이 valid single-line JSON + `request_id` / `verdict` 필수 필드 모두 포함 → ✅ + entry 수 출력
- 1줄이라도 parse 실패 → ⚠️ "audit log 파손 — 수동 백업 후 검토 권장. 자동 수정하지 않음"
- `verdict` 가 enum (`approved`/`rework`/`rejected`/`rerouted`) 외 값 → ⚠️ "스키마 위반 줄 발견"
- **dual-backend 추가 가드**: Local 과 Vault 양쪽에 `.audit/decisions.jsonl` 가 모두 존재하면 ⚠️ "audit log 가 한쪽에만 누적되어야 함 — ADR-0001 §5 SSOT 위반 의심"

> backend 가 아예 없는 (Local/Vault 둘 다 없음) 초기 상태는 8 / 9 / 10 / 11 / 13 / 14 모두 "(N/A — backend 없음)" 으로 skip.

---

## 출력 포맷 (예시)

```
LSKunCompanyKit doctor (v0.5.0)
================================================

[1]  Claude Code 버전              : ✅ <version>
[2]  Plugin manifest               : ✅ name=LSKunCompanyKit, namespace=/lskun-kit:*
[3]  Storage backend
       Local  (<path>)             : ⚠️  .company/ 없음
       Vault  (<path>)             : ✅ workers=3, last_history=2026-05-17
[4]  SSOT cross-contamination       : ✅ 분리 정상
[5]  Worker frontmatter             : ✅ 3/3 통과 (필드 6개 모두)
[6]  Reflection hook                : ✅ plugin manifest 에 SessionStart + Stop 박제됨
[7]  Migration tool                 : ✅ /lskun-kit:migrate 등록됨
[8]  init 실행 상태                  : ✅ company.md 존재
[9]  CPO / 인사팀장                  : ✅ cpo, hr-lead 모두 hired
[10] 회사 domain                    : ✅ "의료 SaaS"
[11] CPO persona (CLAUDE.md)        : ✅ marker 정상
[12] CPO 모델 권장                  : ⚠️  현재 sonnet — `/model opus` 권장
[13] Worker model 필드              : ✅ cpo=default, hr-lead=sonnet, alice=default
[14] CPO 결재 audit log             : ✅ 12 entries, schema OK

결과: 환경 정상. 일상 사용 가능.
```

---

## 실패 시 가이드

- ❌ 발생 시 사용자에게 수정 방법 제시. **자동 수정은 하지 않는다** (읽기 전용 보장).
- cross-contamination 발견 시 ADR-0001 §5 / CLAUDE.md §4 링크 출력.
- init 미실행 시 ADR-0002 §3 / `/lskun-kit:init` 안내.
- CPO persona 미박제 시 ADR-0004 §1 / `/lskun-kit:init` 재실행 안내.
- 기존 회사 마이그레이션 (frontmatter 5→6) 시 사용자에게 `display_name:` 한 줄 수동 추가 안내. ADR-0004 §6 의 "자동 마이그레이션 X" 정책.

---

## 구현 노트

본 사양은 slash command 의 **외부 동작 정의**. 실제 진단 로직은:

- Storage adapter: `lskun_kit.adapters.local` / `lskun_kit.adapters.vault`
- init 위치 결정: `lskun_kit.init.resolve_company_root`
- frontmatter 검증: `lskun_kit.adapters._markdown_tree.read_worker` (의도적으로 raise → doctor 는 try/except 로 메시지화)
- CPO persona detect: `lskun_kit.persona_injection.detect(project_root)`
- 현재 모델: `claude --version` 또는 환경변수에서 추출 (best-effort)
