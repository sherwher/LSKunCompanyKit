---
name: lskun-kit:doctor
description: LSKunCompanyKit 환경 진단 — Claude Code 버전, vault 경로, .company/ 디렉토리, SSOT cross-contamination 검증
---

# /lskun-kit:doctor

LSKunCompanyKit 의 실행 환경을 진단하고 사용자 SSOT 가 올바르게 분리되어 있는지 검증합니다.

본 명령은 **읽기 전용** 입니다. 파일을 수정하지 않으며, 진단 결과만 출력합니다.

---

## 진단 항목

다음 7개 항목을 순서대로 점검하고, 각 항목을 ✅ / ⚠️ / ❌ 로 표시한 진단 리포트를 출력합니다.

### 1. Claude Code 버전

- `claude --version` 출력을 캡처하여 0.1.0-dev 호환성을 확인한다.
- 캡처 실패 시 ⚠️ 로 표기하고 사용자에게 수동 확인을 요청한다.

### 2. Plugin manifest 무결성

- `.claude-plugin/plugin.json` 존재 및 `name == "LSKunCompanyKit"` 확인
- `.claude-plugin/marketplace.json` 존재 및 plugin 항목 1개 이상
- namespace 가 `/lskun-kit:*` 임을 확인

### 3. Storage backend 후보 탐색

다음 두 위치를 탐색하여 사용 가능한 backend 를 보고한다 (둘 다 없어도 정상 — 초기 상태):

- Local: `<project-root>/.company/`
- Vault: 사용자가 환경변수 `LSKUN_VAULT` 또는 `~/.lskun-kit/config.json` 으로 지정한 경로 하위의 `03_Companies/`

각 backend 별로 다음을 보고:
- 존재 여부
- `company.md` 있음 / 없음
- `hired/` 디렉토리 워커 수
- 마지막 history append 시각 (가능한 경우)

### 4. SSOT cross-contamination 검증

다음 위치에 회사 운영 데이터 (hired/ / reflections/ / projects/) 가 있으면 ❌:

- 본 repo 루트 (개발자 SSOT 에 사용자 데이터가 섞이면 안 됨)
- 사용자 SSOT 위치에 ADR / Phase 계획 같은 plugin 설계 문서가 섞이면 ❌

### 5. Worker frontmatter schema 검증 (backend 가 있는 경우)

각 `hired/<worker>.md` 의 frontmatter 가 다음 필수 필드를 가지는지 확인:

- `name`, `role`, `hired_at`, `storage_backend`

`## Project History` 섹션 존재 여부도 확인 (없어도 ⚠️ 만, ❌ 는 아님).

### 6. Reflection hook 등록 상태 (P6 이후)

`~/.claude/settings.json` 또는 프로젝트의 `.claude/settings.json` 에 LSKunCompanyKit 의 작업 종료 hook 이 등록되어 있는지 확인. 미등록 시 ⚠️ + 등록 가이드 출력.

> 본 항목은 P6 (Reflection 자동화) 구현 후부터 의미가 있다. P3 단계에서는 "P6 미구현" 으로 표기.

### 7. Migration tool 준비 상태 (P7 이후)

`/lskun-kit:migrate` 명령 등록 여부 확인. P7 이전에는 "P7 미구현" 으로 표기.

---

## 출력 포맷

```
LSKunCompanyKit doctor (v0.1.0-dev)
================================================

[1] Claude Code 버전              : ✅ <version>
[2] Plugin manifest               : ✅ name=LSKunCompanyKit, namespace=/lskun-kit:*
[3] Storage backend
      Local  (<path>)             : ⚠️  .company/ 없음 (초기 상태)
      Vault  (<path>)             : ✅ workers=3, last_history=2026-05-15
[4] SSOT cross-contamination       : ✅ 분리 정상
[5] Worker frontmatter             : ✅ 3/3 통과
[6] Reflection hook                : ⏳ P6 미구현 (현재 Phase: P3)
[7] Migration tool                 : ⏳ P7 미구현

결과: 환경 정상. 다음 작업: P4 (StorageAdapter 인터페이스).
```

---

## 실패 시 가이드

- ❌ 가 있는 경우 사용자에게 수정 방법을 제시하되, **자동 수정은 하지 않는다**. 본 명령은 읽기 전용.
- cross-contamination 발견 시 [ADR-0001 §5](https://github.com/sherwher/LSKunCompanyKit/blob/main/CLAUDE.md#4-ssot-분리-정책-강제) 의 SSOT 분리 정책 링크를 출력한다.

---

## 구현 노트 (개발자용)

본 문서는 prototype slash command 의 **사양** 이다. 실제 진단 로직은 P4 이후 storage adapter 와 함께 단계적으로 구현된다.

P3 단계에서는 항목 1, 2, 4 만 실제 동작하며, 나머지는 "Phase 미구현" 으로 표시한다.
