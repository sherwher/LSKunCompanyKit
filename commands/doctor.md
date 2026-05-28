---
name: lskun-kit:doctor
description: LSKunCompanyKit 환경 진단 — plugin manifest, backend, SSOT 분리, init 상태, CPO/HR 존재 여부, CLAUDE.md CPO persona 박제, hook 등록 등을 읽기 전용으로 점검
---

# /lskun-kit:doctor

LSKunCompanyKit 의 실행 환경을 진단한다. **읽기 전용** — 파일을 수정하지 않는다.

읽기 전용 환경 진단. 회사 운영 데이터를 수정하지 않는다.

---

## 진단 항목 (29개)

순서대로 점검 후 ✅ / ⚠️ / ❌ 표기.

### 1. Claude Code 버전

- `claude --version` 캡처
- 캡처 실패 시 ⚠️

### 2. Plugin manifest 무결성

- `.claude-plugin/plugin.json` 존재 + `name == "LSKunCompanyKit"`
- `.claude-plugin/marketplace.json` 존재 + plugin 항목 ≥ 1
- namespace 가 `/lskun-kit:*` 임 확인

### 3. Storage backend 탐색 (ADR-0015 — Local 단일)

- Local SSOT: `~/.lskun-companies/<name>/` (`paths.company_root(name)` 단일 진입점)
- 회사 이름은 현재 프로젝트 CLAUDE.md 의 LSKUN-CPO marker 에서 추출 (`persona_injection.extract_company_name`)
- `company.md` 유무 / `hired/` 워커 수 / `archived/` 워커 수
- ~~dual-backend 감지~~ — ADR-0015 로 폐기 (Vault backend 자체가 폐기)
- 잔재 정리: `$LSKUN_VAULT` env var 가 설정되어 있으면 ⚠️ "ADR-0015 — `LSKUN_VAULT` env var 는 더 이상 plugin core 가 참조하지 않음. `/lskun-kit:sync-in <name> <source>` 명령의 인자로만 사용. 환경변수는 제거 권장."
- 옛 `<project>/.company/` 디렉토리가 남아 있으면 ⚠️ "ADR-0015 결정 1-A — 옛 위치. 사용자 명시 정리 권장. 자동 삭제 금지."

### 4. SSOT cross-contamination 검증

- 본 repo 루트에 `hired/` 같은 회사 운영 데이터가 있으면 ❌
- 사용자 SSOT 위치에 ADR / Phase 계획 같은 plugin 설계 문서가 있으면 ❌

### 5. Worker frontmatter schema 검증

- 각 `hired/<worker>.md` 의 frontmatter **필수 6 필드** (`name`, `role`, `domain`, `hired_at`, `storage_backend`, `display_name`) 점검
- ADR-0014 — `## Project History` 섹션은 더 이상 강제하지 않음. 기존 사용자 자산이 있으면 `## Archived History (pre-0.18)` 로 rename 권장 (migrate-schema)
- `display_name` 누락 워커는 ⚠️ + "`/lskun-kit:migrate-schema --dry-run` 으로 변환 계획 확인 후 `/lskun-kit:migrate-schema` 실행 권장. 수동 편집 불필요."

### 6. Hook 등록 상태 (ADR-0014 갱신)

- plugin 자체의 `hooks/hooks.json` 에 SessionStart + PreToolUse(Task) 가 박제되어 있는지 점검
- ADR-0014 — Stop / PostToolUse hook 은 reflection 폐기로 제거됨. 잔존 시 ⚠️
- 사용자가 `~/.claude/settings.json` 등에서 본 plugin 의 hook 을 override / disable 했는지 best-effort 캡처
- plugin manifest 정상이고 사용자 override 없으면 ✅

### 6b. PreToolUse chain-guard hook

- plugin `hooks/hooks.json` 의 PreToolUse 배열에 `pre_tool_use.py` 직접 경로 호출 (matcher=`Task`) 포함 여부
- 모든 hook command 는 `python3 ${CLAUDE_PLUGIN_ROOT}/src/lskun_kit/hooks/*.py` 형식. `python3 -m lskun_kit...` 형식이 남아있으면 ❌ "ModuleNotFoundError 발현 가능"
- 미등록 시 ❌ "워커 → 워커 chain 차단 무력화 — sub-leader 출현 위험"
- `LSKUN_ALLOW_WORKER_CHAIN=1` 환경변수 설정 감지 시 ⚠️ "chain enforcement bypass 활성화 중 — 디버깅 외 비권장"

### 7. Sync 명령 등록 여부 (ADR-0015 — P90 예정)

- `/lskun-kit:sync-in` / `/lskun-kit:sync-out` 명령 등록 여부 (P90 완료 후 ✅, 미완료 시 ⚠️ "P90 에서 박제 예정")
- 옛 `/lskun-kit:migrate` 명령 존재 시 ❌ "ADR-0015 로 폐기됨. commands/migrate.md 삭제 필요"

### 8. init 실행 상태

활성 backend 의 회사 루트가 비어있는지 (= init 미실행) 확인:

- `company.md` 없음 → ⚠️ "init 미실행. `/lskun-kit:init` 을 실행하라"
- `company.md` 있음 → ✅

### 9. CPO / 인사팀장 존재 여부

자동 hire 되는 2명 (CPO / HR Lead) 이 backend 에 있는지 확인:

- `hired/cpo.md` 없음 → ⚠️ "CPO 미hired. `/lskun-kit:init` 재실행 권장"
- `hired/hr-lead.md` 없음 → ⚠️ 동일
- 둘 다 있음 → ✅

### 10. **회사 domain 박제**

- `company.md` 의 frontmatter 에 `domain` 필드 존재 여부
- 없거나 빈 문자열 → ⚠️ "도메인 미박제 — `/lskun-kit:migrate-schema` 로 보강."
- 있음 → ✅ + 값 출력

### 11. **CPO persona CLAUDE.md 박제**

사용자 프로젝트 root 의 `CLAUDE.md` 안에 `<!-- LSKUN-CPO:START -->` ~ `<!-- LSKUN-CPO:END -->` marker 구간 존재 여부:

- 없음 → ⚠️ "CPO persona 미박제 — 메인 세션이 CPO 로 동작하지 않음. `/lskun-kit:migrate-schema` 또는 `/lskun-kit:init` 재실행."
- 손상 (start 만 있고 end 없음) → ⚠️ "marker 손상 — 수동 수정 또는 재박제 필요"
- 정상 → ✅
- **백업 파일 감지**: `CLAUDE.md.lskun.bak` 가 존재하면 ⚠️ "직전 init 가 marker 내 사용자 손편집을 감지해 백업했다. 내용 비교 후 백업 제거 권장."

### 12. **CPO 모델 권장**

CPO 는 메인 세션의 사용자 `/model` 설정에 의존 (plugin 강제 불가). Claude Code 의 현재 모델이 Opus 계열인지 확인:

- 현재 모델 ID 가 `opus` 포함 → ✅ "권장 모델 사용 중"
- 그 외 (Sonnet / Haiku) → ⚠️ "CPO 결재·라우팅 정확도 향상을 위해 `/model opus` 권장 (강제 아님)"
- 모델 정보 캡처 불가 → ⚠️

### 13. **Worker model 필드**

- 각 `hired/<worker>.md` 의 optional `model` 필드 점검
- 없으면 ✅ "default = sonnet"
- "sonnet" / "opus" / 모델 ID 명시면 ✅ + 값 출력

### 14. **CPO 결재 audit log**

활성 backend 의 `<company-root>/.audit/decisions.jsonl` 무결성:

- 파일 부재 → ✅ "audit 박제 미시작 (첫 결재 시 자동 생성)" — 정보성, ⚠️ 아님
- 파일 존재 + 모든 줄이 valid single-line JSON + `request_id` / `verdict` 필수 필드 모두 포함 → ✅ + entry 수 출력
- 1줄이라도 parse 실패 → ⚠️ "audit log 파손 — 수동 백업 후 검토 권장. 자동 수정하지 않음"
- `verdict` 가 enum (`approved`/`rework`/`rejected`/`rerouted`) 외 값 → ⚠️ "스키마 위반 줄 발견"
- ~~dual-backend 추가 가드~~ — ADR-0015 로 폐기 (Local SSOT 단일, 양쪽 누적 시나리오 자체가 사라짐)

### 15. **Persona sync 상태**

메타 워커 (`cpo`, `hr-lead`) 의 `hired/<name>.md` frontmatter 의 `persona_synced_from` 가 현재 plugin 버전과 일치하는지 점검:

- 일치 → ✅ "synced from lskun-kit@<version>"
- 불일치 (값은 있으나 다른 버전) → ⚠️ "stale persona body — `/lskun-kit:sync-persona --execute` 권장"
- 부재 (기존 회사, ADR-0010 이전 hire) → ⚠️ "provenance 미박제 — `/lskun-kit:sync-persona --execute` 1회 권장"

### 16. **조직도 한 줄 요약**

`hired/` 디렉토리 스캔 후 한 줄 요약 (정보성, 진단 아님):

- 워커 수 (CPO / HR / Worker 카테고리별)
- 도메인 분포
- `/lskun-kit:org` 명령 안내

### 17. **Plugin install path 단일성 + canonical resolve (P77)**

`/lskun-kit:org` canonical 1줄이 항상 같은 파일에 도달하는지 점검:

- `$CLAUDE_PLUGIN_ROOT` env var 주입 여부 — 미주입이면 ℹ️ (정상. Claude Code 가 활성 plugin 1개에만 set 하는 환경 다수. fallback 으로 동작)
- `~/.claude/plugins/cache/LSKunCompanyKit/LSKunCompanyKit/` 아래 install 디렉토리 개수
  - 0개 → ❌ "plugin install 부재. marketplace 재설치 필요"
  - 1개 → ✅
  - 2개 이상 → ⚠️ "옛 버전 잔존 (`<list>`). LLM 이 버전 hardcode 시 모호. 최신 1개만 남기고 정리 권장"
- canonical 1줄 (commands/org.md:15) 의 셸 resolve chain 이 실제로 존재하는 `cli_org.py` 1개에 도달하는지 검증 (시뮬레이션. 실행은 하지 않음)
- env 주입 + install 경로 + cwd 경로가 **모두 다른 파일** 을 가리키면 ⚠️ "버전 drift 위험"

> Local SSOT 가 아예 없는 (`~/.lskun-companies/<name>/` 부재) 초기 상태는 8 / 9 / 10 / 11 / 13 / 14 / 15 / 16 모두 "(N/A — backend 없음)" 으로 skip. 17번은 plugin 자체 검사이므로 backend 무관하게 항상 수행.
>
> ADR-0019 (2026-05-27) — Archive 메커니즘 완전 폐기. 옛 항목 [18] (archived↔hired display_name 중복) + [19] (audit log dangling cross-check) 제거. 진단 25 → 23.

### 20. **OMC fallback 가드 활성 (ADR-0016)**

`src/lskun_kit/hooks/pre_tool_use.py` 의 OMC fallback 차단 로직 존재 + 활성 조건 충족 검증:

- pre_tool_use.py 파일에 `_OMC_BLOCK_PREFIXES` / `ENV_ALLOW_OMC` 상수 존재 → ✅
- ADR-0016 marker 주석 (`ADR-0016`) 본문 포함 → ✅
- plugin 버전 ≥ `0.20.0` → ✅ (`plugin.json` 의 `version` 비교)
- 활성 조건: `LSKUN_SSOT_ROOT` env var set 또는 cwd 상위 CLAUDE.md 의 LSKUN-CPO marker 존재 → 해당 시 ✅ "활성", 부재 시 ℹ️ "비활성 (marker 미박제 프로젝트)"
- 조건 미충족 (가드 로직 부재 / 버전 미달) → ⚠️ "ADR-0016 가드 비활성. plugin 0.20.0+ 로 업데이트 필요"

### 21. **`LSKUN_ALLOW_OMC_FALLBACK` 영구 export 검출 (ADR-0016 결정 5)**

shell profile 에 bypass env var 가 영구 export 되어 가드가 무력화되는지 검사:

- `~/.zshrc`, `~/.bashrc`, `~/.zprofile`, `~/.bash_profile` 파일에서 `LSKUN_ALLOW_OMC_FALLBACK` 등장 grep
- 발견 시 ⚠️ `"<file>:<line> LSKUN_ALLOW_OMC_FALLBACK 영구 export 검출. 가드 무력화 위험. 세션 단위 export 권장 (디버깅 후 unset)"`
- 동일 검사를 `LSKUN_ALLOW_WORKER_CHAIN` 에도 수행 → ADR-0004 §8 가드 무력화 동일 경고
- 미검출 시 ✅

### 22. **Dispatch allowlist 가드 활성 (ADR-0017)**

`src/lskun_kit/hooks/pre_tool_use.py` 의 allowlist 차단 로직 존재 + 활성 조건 충족 검증:

- pre_tool_use.py 파일에 `_ALLOWED_SUBAGENT` 상수 존재 → ✅
- pre_tool_use.py 파일에 `ENV_ALLOW_NON_CLAUDE` 상수 존재 (신규 정식 escape hatch) → ✅
- ADR-0017 marker 주석 (`ADR-0017`) 본문 포함 → ✅
- plugin 버전 ≥ `0.21.0` → ✅ (`plugin.json` 의 `version` 비교)
- 활성 조건: `LSKUN_SSOT_ROOT` env var set 또는 cwd 상위 CLAUDE.md 의 LSKUN-CPO marker 존재 → 해당 시 ✅ "활성", 부재 시 ℹ️ "비활성 (marker 미박제 프로젝트)"
- 조건 미충족 (allowlist 상수 부재 / 버전 미달) → ⚠️ "ADR-0017 가드 비활성. plugin 0.21.0+ 로 업데이트 필요"

### 23. **`LSKUN_ALLOW_NON_CLAUDE_DISPATCH` / `LSKUN_ALLOW_OMC_FALLBACK` 영구 export 검출 (ADR-0017 결정 8)**

shell profile 에 allowlist bypass env var 가 영구 export 되어 가드가 무력화되는지 검사:

- `~/.zshrc`, `~/.bashrc`, `~/.zprofile`, `~/.bash_profile` 파일에서 다음 두 패턴 grep:
  - `LSKUN_ALLOW_NON_CLAUDE_DISPATCH` (신규 정식, ADR-0017)
  - `LSKUN_ALLOW_OMC_FALLBACK` (ADR-0016 별칭, 하위호환 — 항목 21 와 중복 검출이지만 명확성 위해 본 항목에서도 별도 안내)
- 발견 시 ⚠️ `"<file>:<line> <var> 영구 export 검출. allowlist 가드 무력화 위험. 세션 단위 export 권장 (디버깅 후 unset)"`
- 미검출 시 ✅

### 24. **Persona sync 백업 누적 검사 (P107)**

`hired/` 디렉토리의 메타 워커별 sync 백업 파일 (`<name>.md.lskun-pre-sync.bak[.timestamp]`) 누적 수를 점검:

- 대상: `cpo`, `hr-lead` (메타 워커만, 일반 워커는 sync 대상 아님 → 백업 발생 X)
- 백업 ≤ 3개: ✅
- 백업 4~10개: ⚠️ `"<name>: 백업 N개 누적. /lskun-kit:sync-persona --cleanup-backups --execute 권장 (keep=3 기본)"`
- 백업 > 10개: ⚠️ 동일 메시지 (severity 만 상승, 자동 청소 X)
- 자동 청소 절대 금지 — 역사 자산 불변 원칙 (ADR-0015 정신)

### 27. **30일+ 미 dispatch 워커 검출 (P110-B, ADR-0018)**

`/lskun-kit:org --usage` 의 데이터 활용. 정보성 — **자동 평가·해고 절대 금지** (ADR-0006 + ADR-0018 boundary):

- `audit_view.read_usage(.audit/)` 호출 → 각 워커별 `last_seen` 추출
- 현재 UTC 시각 - `last_seen` ≥ 30 일 → ℹ️ `"<worker>: <N>일 전 마지막 dispatch (last_seen=<YYYY-MM-DD>)"` 단순 표시
- 한 번도 dispatch 안 된 워커 (audit 0건) → ℹ️ `"<worker>: 0 dispatches since hire"`
- ⚠️ / ❌ 사용 금지 — 단순 정보. 사용자가 보고 직접 판단
- 자동 해고 추천 X — 결정 7 (archive 폐기, ADR-0019) 정합

### 28. **도메인 분포 — 빈 도메인 / 1명만 있는 도메인 (P110-B)**

조직도의 도메인 분포를 정보성으로 표시:

- 각 도메인의 워커 수 카운트 (CPO/HR 제외)
- 워커 0명인 도메인 — ℹ️ `"domain '<X>': 0 workers (company.md 의 domain 박제 후 채용 X)"`
- 워커 1명인 도메인 — ℹ️ `"domain '<X>': 1 worker (single point — 도메인 확장 또는 통합 고려)"`
- 자동 조정 X — 단순 정보, 사용자 판단

### 29. **hired/ 의 비-워커 파일 검출 (P110-B, P107 연장)**

`hired/` 디렉토리에 워커 markdown 외 파일이 있는지 검출:

- `.md` 가 아닌 파일 (단, `.lskun-pre-sync.bak*` 백업 부산물은 P107 [25] 가 처리, 본 항목은 그 외 검출)
- `.md` 인데 worker frontmatter schema 미충족 (`name`/`role`/`domain`/`hired_at`/`storage_backend`/`display_name` 6 필드 중 일부 누락)
- 발견 시 ⚠️ `"hired/<file>: 워커가 아님 (사유: <missing fields | non-md>). 사용자 수동 정리 권장"`
- 자동 삭제 절대 금지

### 30. **archived/ dangling 검사 (P110-B, ADR-0019)**

ADR-0019 (archive 폐기) 후 사용자가 옛 `archived/` 디렉토리를 미정리한 경우 안내:

- `<company_root>/archived/` 디렉토리 존재 + 1개 이상 `.md` 파일 → ℹ️ `"archived/ 에 <N>개 파일 잔존. ADR-0019 로 plugin core 가 더 이상 참조하지 않음. 처리 옵션:"`
  - 옵션 A: `rm -rf ~/.lskun-companies/<name>/archived/` (완전 삭제)
  - 옵션 B: `mv archived/ ~/Documents/lskun-archived-<date>/` (외부 보관)
  - 옵션 C: 방치 (plugin 동작 영향 0)
- 자동 처리 절대 금지

### 31. **skills/ 정합성 검사 (ADR-0020, P111)**

각 워커의 `skills` 선언과 `<company_root>/skills/` 파일을 대조 (`lskun_kit.skills_diagnostics.diagnose_skills` 호출, read-only). active company 부재 시 skip (ℹ️). 양방향 + 이름/메타 검출:

- **dangling** (선언↔파일없음): ⚠️ `"<worker>.skills=<name> → skills/<name>.md 없음"`
- **orphan** (파일↔선언없음): ℹ️ `"skills/<name>.md → 선언 워커 0 (죽은 자산). 사용자 정리 권장 (archived/ 전철 방지)"`
- **invalid** (이름 allowlist 위반): ⚠️ `"<worker>.skills=<name> → 이름 패턴 위반 (^[a-z0-9][a-z0-9_-]{0,63}$). path traversal 표면"`
- **meta** (메타 워커에 skills): ⚠️ `"<worker> 는 메타 워커 — skills 비워둠 권장 (라우팅/dispatch 대상 아님)"`
- 모두 정상이면 ✅ `"skills/ 정합 (선언 N개, 파일 M개)"`
- 자동 삭제·생성 절대 금지 — 사실 표시만 (ADR-0006)

### 32. **external 정합성 검사 (ADR-0021, P120)**

`<company_root>/external/<project>/{redteam,customers}/` 구조와 brief/페르소나 파일 정합을 점검 (`lskun_kit.external_diagnostics.diagnose_external(<company>)` 호출, read-only). active company 부재 시 skip (ℹ️). 외주는 opt-in 이므로 미구성도 정상:

- 외주 미구성 (`has_external == False`): ℹ️ `"외주 미구성 (opt-in, ADR-0021). /lskun-kit:external 로 박제 가능"`
- brief 누락: ⚠️ `"external/<project>/<kind>/ 존재하나 brief.md 없음 — destructive 헌법 미박제 위험"`
- 그 밖의 정합성 위반: ⚠️ findings.issues 그대로 표시
- 모두 정상이면 ✅ `"external/ 정합"`
- 자동 생성·삭제 절대 금지 — 사실 표시만 (ADR-0006 + ADR-0021)

### 26. **audit log 누적 크기 모니터링 (P109-B)**

`<company_root>/.audit/decisions.jsonl` 의 파일 크기를 점검 (자동 회전 X, 안내만):

- 크기 < 10 MB: ✅
- 크기 ≥ 10 MB: ℹ️ `"decisions.jsonl 이 <N> MB. /lskun-kit:audit-rotate 로 옛 월 entry 를 decisions.<YYYY-MM>.jsonl.gz 로 분리 권장 (사용자 명시 명령)"`
- 자동 회전 절대 금지 — ADR-0006 정신 (사용자 명시 명령만)
- `decisions.<YYYY-MM>.jsonl.gz` 회전 파일은 별도 진단 없음 (크기 제약 X — 압축됨)

### 25. **hired/ 스캔 시 백업 부산물 누설 검사 (P107)**

`list_workers()` 가 sync 백업을 워커로 카운트하지 않는지 시뮬레이션 검증:

- `LocalAdapter(<active company>).list_workers()` 결과의 각 이름에 대해 `.lskun-pre-sync.bak` substring 검사
- 1개라도 포함되면 ❌ `"hired/ 백업 부산물이 워커로 카운트됨. _is_backup_artifact 가드 미작동. 회귀 가능성. issue 보고 요청."`
- 모두 정상이면 ✅

> 항목 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31 은 plugin 자체 검사로 backend 무관. plugin install 부재 시에도 수행 (24/25/26/27/28/29/30/31 은 active company 부재 시 skip ℹ️).
>
> ADR-0018 (No external harness) — 본 진단들은 모두 **사용자 명시 호출 `/lskun-kit:doctor` 시점에만 실행**. cron 같은 자동 회수 절대 금지. 평가·점수·랭킹 0 — 단순 사실 표시 (ADR-0006 + ADR-0002 §5 boundary).

---

## 출력 포맷 (예시)

```
LSKunCompanyKit doctor (v<plugin-version>)
================================================

[1]  Claude Code 버전              : ✅ <version>
[2]  Plugin manifest               : ✅ name=LSKunCompanyKit, namespace=/lskun-kit:*
[3]  Storage backend (Local 단일)   : ✅ ~/.lskun-companies/LSKun/ 존재, hired=3, archived=0
[4]  SSOT cross-contamination       : ✅ 분리 정상
[5]  Worker frontmatter             : ✅ 3/3 통과 (필드 6개 모두)
[6]  Hook 등록 (ADR-0014)           : ✅ SessionStart + PreToolUse(Task) 박제됨
[7]  Sync 명령 (ADR-0015)           : ✅ /lskun-kit:sync-in, /lskun-kit:sync-out 등록됨
[8]  init 실행 상태                  : ✅ company.md 존재
[9]  CPO / 인사팀장                  : ✅ cpo, hr-lead 모두 hired
[10] 회사 domain                    : ✅ "의료 SaaS"
[11] CPO persona (CLAUDE.md)        : ✅ marker 정상
[12] CPO 모델 권장                  : ⚠️  현재 sonnet — `/model opus` 권장
[13] Worker model 필드              : ✅ cpo=default, hr-lead=sonnet, alice=default
[14] CPO 결재 audit log             : ✅ 12 entries, schema OK
[15] Persona sync                   : ✅ cpo=lskun-kit@<ver>, hr-lead=lskun-kit@<ver>
[16] 조직도 요약                    : ✅ 5명 (CPO 1, HR 1, Worker 3) · 도메인: web 2, marketing 1, meta 2 · /lskun-kit:org 참고
[17] Plugin install 단일성 (P77)    : ✅ install=1 (0.16.0), canonical resolve OK
[24] Persona sync 백업 누적 (P107) : ⚠️  cpo: 백업 3개, hr-lead: 백업 3개 — keep≤3 권장
[25] hired/ 백업 부산물 누설        : ✅ list_workers OK (백업 0건 누설)
[26] audit log 누적 크기 (P109-B)  : ✅ decisions.jsonl = 23 KB (회전 불필요)
[27] 30일+ 미 dispatch (P110-B)    : ℹ️  aimbti-product-expert: 42일 전, careerai-pe: 0 dispatches (정보성)
[28] 도메인 분포 (P110-B)          : ℹ️  domain 'legal': 1 worker (single point), 'meta': 2
[29] hired/ 비워커 파일 (P110-B)  : ✅ all 43 files = valid workers
[30] archived/ dangling (P110-B)  : ℹ️  archived/ 4개 파일 잔존 (ADR-0019, 처리 옵션 A/B/C 안내)
[31] skills/ 정합성 (ADR-0020)    : ✅ skills/ 정합 (선언 N개, 파일 M개)
[32] external/ 정합성 (ADR-0021)  : ℹ️  외주 미구성 (opt-in)

결과: 환경 정상. 일상 사용 가능 (정보성 ℹ️ 는 사용자 판단 사항).
```

---

## 실패 시 가이드

- ❌ 발생 시 사용자에게 수정 방법 제시. **자동 수정은 하지 않는다** (읽기 전용 보장).
- cross-contamination 발견 시 SSOT 분리 정책 안내.
- init 미실행 시 `/lskun-kit:init` 안내.
- CPO persona 미박제 시 `/lskun-kit:init` 재실행 안내.
- 기존 회사 마이그레이션 필요 시 `/lskun-kit:migrate-schema` 안내.

---

## 구현 노트

본 사양은 slash command 의 **외부 동작 정의**. 실제 진단 로직은:

- Storage adapter: `lskun_kit.adapters.local` (ADR-0015 — Local 단일 backend)
- init 위치 결정: `lskun_kit.init.resolve_company_root`
- frontmatter 검증: `lskun_kit.adapters._markdown_tree.read_worker` (의도적으로 raise → doctor 는 try/except 로 메시지화)
- CPO persona detect: `lskun_kit.persona_injection.detect(project_root)`
- skills/ 정합성 ([31]): `lskun_kit.skills_diagnostics.diagnose_skills(adapter)` (ADR-0020, read-only)
- external/ 정합성 ([32]): `lskun_kit.external_diagnostics.diagnose_external(<company>)` (ADR-0021, read-only)
- 현재 모델: `claude --version` 또는 환경변수에서 추출 (best-effort)
