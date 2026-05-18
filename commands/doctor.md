---
name: lskun-kit:doctor
description: LSKunCompanyKit 환경 진단 — Plugin manifest, backend, SSOT 분리, init 상태, CPO/HR 존재 여부, CPO persona CLAUDE.md 박제, hook 등록 (ADR-0001~0004)
---

# /lskun-kit:doctor

LSKunCompanyKit 의 실행 환경을 진단한다. **읽기 전용** — 파일을 수정하지 않는다.

본 명령은 ADR-0002 (init 명령), ADR-0003 (domain 필드), ADR-0004 (메인 세션 = CPO + display_name + model) 의 도입에 따라 진단 항목이 확장됐다.

---

## 진단 항목 (13개)

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

### 5. Worker frontmatter schema 검증 (ADR-0003 + ADR-0004 §6)

- 각 `hired/<worker>.md` 의 frontmatter **필수 6 필드** (`name`, `role`, `domain`, `hired_at`, `storage_backend`, `display_name`) 점검
- `## Project History` 섹션 존재 여부 (없으면 ⚠️ 만)
- `display_name` 누락 워커는 ⚠️ + "ADR-0004 §5 — 수동으로 frontmatter 에 추가 필요" 안내

### 6. Reflection hook 등록 상태

- `~/.claude/settings.json` 또는 프로젝트 `.claude/settings.json` 의 Stop hook 배열에 `python3 -m lskun_kit.hooks.stop_reflect` 포함 여부
- 미등록 시 ⚠️ + 등록 가이드

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
- 없거나 빈 문자열 → ⚠️ "도메인 미박제 — 도메인 전문가 채용 라우팅 제한됨. company.md 에 수동 추가 또는 `/lskun-kit:init` 재실행"
- 있음 → ✅ + 값 출력

### 11. **CPO persona CLAUDE.md 박제 (ADR-0004 §1, P23 신설)**

사용자 프로젝트 root 의 `CLAUDE.md` 안에 `<!-- LSKUN-CPO:START -->` ~ `<!-- LSKUN-CPO:END -->` marker 구간 존재 여부:

- 없음 → ⚠️ "CPO persona 미박제 — 메인 세션이 CPO 로 동작하지 않음. `/lskun-kit:init` 재실행 (또는 향후 `/lskun-kit:doctor --reinject-cpo` 추가 예정) 으로 재박제"
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

> backend 가 아예 없는 (Local/Vault 둘 다 없음) 초기 상태는 8 / 9 / 10 / 11 / 13 모두 "(N/A — backend 없음)" 으로 skip.

---

## 출력 포맷 (예시)

```
LSKunCompanyKit doctor (v0.3.0-dev)
================================================

[1]  Claude Code 버전              : ✅ <version>
[2]  Plugin manifest               : ✅ name=LSKunCompanyKit, namespace=/lskun-kit:*
[3]  Storage backend
       Local  (<path>)             : ⚠️  .company/ 없음
       Vault  (<path>)             : ✅ workers=3, last_history=2026-05-17
[4]  SSOT cross-contamination       : ✅ 분리 정상
[5]  Worker frontmatter             : ✅ 3/3 통과 (필드 6개 모두)
[6]  Reflection hook                : ⚠️  Stop hook 미등록 — 등록 가이드 참조
[7]  Migration tool                 : ✅ /lskun-kit:migrate 등록됨
[8]  init 실행 상태                  : ✅ company.md 존재
[9]  CPO / 인사팀장                  : ✅ cpo, hr-lead 모두 hired
[10] 회사 domain                    : ✅ "의료 SaaS"
[11] CPO persona (CLAUDE.md)        : ✅ marker 정상
[12] CPO 모델 권장                  : ⚠️  현재 sonnet — `/model opus` 권장
[13] Worker model 필드              : ✅ cpo=default, hr-lead=sonnet, alice=default

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
