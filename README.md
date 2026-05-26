# LSKunCompanyKit

> Domain-expert AI workers, hired complete. The main session **is** the CPO.

**LSKunCompanyKit** 은 Claude Code 에서 **도메인 적합 전문가** 를 채용·운영하는 시스템입니다. 메인 세션 자체가 회사의 **CPO** 로 동작하여 적합 워커를 자동 라우팅·결재하고, 없으면 JD 기반 자동 채용합니다. 워커는 채용 시점에 HR Lead 가 작성한 JD (도메인 날리지 + 전문성) 로 **완성형** 이며, 시간 흐름으로 진화하지 않습니다 (ADR-0014, 2026-05-22). 회사 성장 = 인원 추가 + 도메인 확장.

- **Status:** Version 은 `.claude-plugin/plugin.json` 의 `version` 필드가 단일 진실원 (ADR-0012). 가장 최근 design pivot 은 [ADR-0012](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0012-2026-05-20-single-source-version.md) (단일 SSOT version 정책)
- **License:** MIT
- **Namespace:** `/lskun-kit:*`

---

## 왜 만드는가

기존 multi-agent 프레임워크 (MetaGPT, ChatDev, CrewAI) 는 워커 정의가 매번 휘발됩니다. LSKunCompanyKit 은 다음 4가지를 결합합니다:

1. **JD-driven Workers** — 채용 시점에 도메인 날리지 + 전문성을 JD (persona body) 로 박제. 워커 = 채용 즉시 완성형 (ADR-0014)
2. **Leader–Worker (메인 세션 = CPO)** — 사용자 요청 → CPO 라우팅 → 워커 dispatch → 결재 → 응답을 한 세션 안에서 수행
3. **도메인 인지 (`role × domain`)** — 의료 backend-engineer vs 핀테크 backend-engineer 의 JD 가 도메인별로 분리되어 회사 도메인 폭이 자산
4. **Storage Backend 추상화** — Local (`.company/`) 또는 Vault (`<vault>/03_Companies/<company>/`). 사용자 선택, plugin 이 마이그레이션 책임

**Reflection 메커니즘 (history 누적) 은 ADR-0014 로 폐기** (2026-05-22). 6일 실측 (LSKun 41명 / 8건 박제 / 누락률 80.5%) + 4 전문가 5차 만장일치. 워커는 시간 흐름으로 진화하지 않으며, 자산은 JD only (정적 단일 차원). 코드 제거는 P79 진행 예정.

| 기능 | MetaGPT | ChatDev | CrewAI | MemGPT | **LSKunCompanyKit** |
|---|---|---|---|---|---|
| JD-driven workers (채용 시 완성형) | ❌ | ❌ | ❌ | ❌ | ✅ |
| Leader–Worker 결재 | ❌ | ❌ | ❌ | ❌ | ✅ |
| 도메인 전문가 채용 | ❌ | ❌ | ❌ | ❌ | ✅ |
| 자동 채용 (사용자 알림만) | ❌ | ❌ | ❌ | ❌ | ✅ |
| 인간 가독성 (markdown) | 부분 | 부분 | ❌ | ❌ | ✅ |
| Storage Backend 추상화 | ❌ | ❌ | ❌ | ❌ | ✅ |
| Migration tool | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## 메커니즘 1 — JD-driven Workers (ADR-0014, 2026-05-22)

워커는 채용 시점에 HR Lead 가 작성한 JD (persona body) 로 **완성형**. 시간 흐름으로 진화하지 않으며, 자산은 JD only 단일 차원.

```markdown
---
name: backend-engineer-medical
role: backend-engineer
domain: medical-saas
display_name: Alex Kim
---

# backend-engineer-medical (Alex Kim)

## 도메인 전문성
- HIPAA PHI 마스킹 패턴
- HL7 FHIR R4 / FHIR R5 차이
- EHR 통합 (Epic / Cerner) API quirk
...
```

채용 = 완성형 전문가 박제. 회사 성장 = 인원 추가 + 도메인 확장. **워커가 시간으로 성장한다 모델 부정** (ADR-0014).

> 옛 메커니즘 (Reflection — 작업 종료 시 history 1줄 append → 다음 dispatch context 주입) 은 ADR-0014 로 폐기. 6일 실측 누락률 80.5% + 4 전문가 5차 만장일치. 코드 제거는 P79 진행 예정.

---

## 메커니즘 2 — Leader–Worker, 메인 세션 = CPO (ADR-0004)

```
사용자
  ↓
메인 세션 = CPO (CLAUDE.md inline 박제 + SessionStart hook 으로 회사 컨텍스트)
  ↓ Task tool
워커 (frontmatter.model = sonnet|opus, persona = hired/<name>.md)
  ↑ 보고 (작업 결과 / first-pass / reflection 후보 3섹션)
메인 세션 = CPO 가 결재 → 사용자 응답
```

- **결재:** 워커 보고의 사용자 요청 부합 여부 검수, 미달 시 재작업 (최대 2회). audit log (ADR-0006) 박제 유지
- **자동 채용:** 적합 워커 없으면 HR Lead 를 Task tool 로 호출 → 채용 → `[채용 알림]` 1줄 → 신규 워커 dispatch (사용자 차단 X)
- **모델 라우팅:** 워커 default = Sonnet, frontmatter `model` 또는 CPO 동적 override 로 Opus
- **금지:** 워커 → 워커 chain (sub-leader 출현 방지), CPO/HR 외 임원 자동 추가, 워커 진화 narrative (ADR-0014)

---

## 메커니즘 3 — Role × Domain (ADR-0003)

워커 frontmatter:

```yaml
---
name: backend-engineer-medical
role: backend-engineer
domain: 의료 SaaS         # 회사 도메인 상속 또는 명시 override
hired_at: 2026-05-18
storage_backend: local
display_name: Alex Kim
model: opus               # optional (default: sonnet)
---
```

- 같은 `role` 이라도 `domain` 마다 JD 가 분리 → "HIPAA PHI 마스킹 패턴" 같은 도메인 지식이 JD 본문에 박제 (ADR-0014 재해석)
- CPO 라우팅 0순위 = 회사 `domain` 일치 워커
- 도메인 미일치 시 일반 워커 fallback + "도메인 전문가 채용 권장" 메시지
- 사전 정의 카탈로그 없음 (`medical`, `fintech` 등 enum 강제 X) — 자유 입력

---

## Storage Backend (ADR-0015 — Local 단일 SSOT)

```
LSKunCompanyKit core (interface 만 알고 구현은 모름)
   └── StorageAdapter (read_worker / list_workers / read_company
                       + create_worker / archive_worker / append_audit)
              ↓
       Local (단일 backend, ~/.lskun-companies/<name>/)
              ↕ (사용자 명시 sync 명령만)
       외부 mirror (vault / Obsidian / Notion local / Dropbox / 외장 디스크)
```

| 항목 | 위치 |
|---|---|
| **회사 자원 SSOT** | `~/.lskun-companies/<name>/` |
| **백업** | `~/.lskun-companies/.backups/<name>/<YYYYMMDD-HHMMSS>/` |
| **외부 mirror** | 사용자 임의 경로 (vault 등) — plugin core 는 path 만 알고 SDK 0 |

ADR-0015 (2026-05-22) — Plugin core 는 vault 를 직접 참조하지 않는다. Sync 는 명시적 액션 (`/lskun-kit:sync-in <name> <source>` / `/lskun-kit:sync-out <name> <target>`) 이며 `shutil.copytree` 만 사용. 양방향 자동 merge / 자동 스케줄링 / 외부 SDK 호출 모두 영구 금지.

ADR-0009 — Local 만으로 JD-driven Workers / CPO 결재 / audit log / 권한 자동 박제 모두 완전 동작. 외부 시스템 통합은 별도 add-on package 책임.

권한: `/init` 신규 회사 창설 시 `~/.claude/settings.json` 에 5개 패턴 (Read/Edit/Write/Bash ls/cat 의 `~/.lskun-companies/<name>/**`) 자동 박제 (사용자 confirm 1회).

---

## SSOT 분리 (ADR-0015)

| 영역 | 위치 | 내용 |
|---|---|---|
| Plugin 개발자 SSOT | 본 repo (코드) + 저자별 별도 위치 (ADR / Phase 계획) | plugin 본 repo 의 문서는 저자 개인 SSOT 위치를 박제하지 않는다 (ADR-0009) |
| **사용자 SSOT** (단일) | `~/.lskun-companies/<name>/` | `company.md` / `hired/` / `archived/` / `.audit/` |
| 외부 mirror (선택) | 사용자 임의 경로 (vault 등) | sync 명령으로만 동기화. plugin core 는 path 만 알고 SDK 0 |

ADR-0015 (2026-05-22) — 사용자 SSOT 는 Local 단일 위치. `<project>/.company/` 는 모든 형태로 폐기 (SSOT / cache / mirror 무엇으로도 도입 금지). 1 회사 N 프로젝트 공유 가능 — 각 프로젝트의 `CLAUDE.md` LSKUN-CPO marker 가 회사-프로젝트 결합을 표현.

두 SSOT (개발자 / 사용자) 는 물리적으로 분리되며 `/lskun-kit:doctor` 가 cross-contamination 을 검증합니다.

또한 ADR-0004 §1 에 따라 **사용자 프로젝트 root 의 `CLAUDE.md`** 에 marker 구간 (`<!-- LSKUN-CPO:START -->` ~ `<!-- LSKUN-CPO:END -->`) 으로 CPO persona 가 inline 박제됩니다. marker 외 본문은 한 줄도 건드리지 않습니다.

---

## 설치

> 0.5.0 은 marketplace 정식 등록 전입니다. 본 repo 자체를 marketplace 로 등록해야 합니다.

### 옵션 A — GitHub repo 경유 (다른 PC 동기화에 유리)

```text
/plugin marketplace add sherwher/LSKunCompanyKit
/plugin install LSKunCompanyKit@LSKunCompanyKit
```

### 옵션 B — 로컬 경로 경유 (개발/도그푸딩 빠른 반복)

```bash
git clone https://github.com/sherwher/LSKunCompanyKit.git
```

```text
/plugin marketplace add /path/to/LSKunCompanyKit
/plugin install LSKunCompanyKit@LSKunCompanyKit
```

설치 후 검증:

```text
/lskun-kit:doctor
```

---

## 사용 흐름 (Phase 3)

### 0) 기존 vault 사용자 마이그레이션 (ADR-0015, Phase 15)

ADR-0015 (2026-05-22) — Local SSOT 단일 위치 (`~/.lskun-companies/<name>/`) 로 통일. 기존 vault (`<your-vault>/03_Companies/<name>/`) 사용자는 **최초 1회만** sync-in 실행:

```bash
# 1. plugin 갱신 후 최초 1회만 실행
/lskun-kit:sync-in LSKun ~/path/to/your-vault/03_Companies/LSKun

# 2. plugin 이 vault → ~/.lskun-companies/LSKun/ 복사 + 권한 자동 박제 + 백업

# 3. 이후 모든 프로젝트는 /init LSKun 으로 marker 박제만 수행
cd <any-project>
/lskun-kit:init LSKun
```

**자동 마이그레이션은 도입하지 않습니다** (ADR-0015 결정 1-A — plugin core 가 vault 직접 참조 영구 금지). `LSKUN_VAULT` env var 가 설정되어 있어도 plugin 은 자동 sync-in 하지 않으며, 사용자가 명시 호출해야 합니다.

이후 vault 와의 동기화가 필요하면 양방향 sync 명령으로 진행:
- `/lskun-kit:sync-out LSKun ~/path/to/your-vault/03_Companies/LSKun` (local → vault)
- `/lskun-kit:sync-in LSKun ~/path/to/your-vault/03_Companies/LSKun` (vault → local)

양방향 자동 merge 는 미도입 — 사용자가 시점 선택. 충돌이 빈번하면 사용자 측 워크플로 문제로 진단합니다.

### 1) 회사 셋업 — `init` (ADR-0015 멱등성 4행)

신규 회사 셋업의 단일 진입점. `~/.lskun-companies/<name>/` 에 회사 자원 박제 + 회사 `domain` 박제 + CPO/HR 자동 hire + 사용자 프로젝트 CLAUDE.md 에 CPO persona inline 박제 + `~/.claude/settings.json` 권한 자동 박제.

```text
# ADR-0015 — Local SSOT 단일 backend (외부 의존성 0)
/lskun-kit:init Acme "AI agents for SMB compliance"
```

Claude 가 5가지를 순차 질문:

1. 회사 이름
2. 회사 한 줄 소개
3. 회사 도메인 (예: "의료 SaaS")
4. CPO 의 사람 이름 (`display_name`, 자동 생성 금지)
5. HR Lead 의 사람 이름 (`display_name`)

멱등성 4행 (ADR-0015 결정 2-B):

| 회사 자원 | 프로젝트 marker | 동작 |
|---|---|---|
| 신규 | 부재 | 회사 창설 + hire + marker 박제 + 권한 박제 (`founded`) |
| 기존 | 부재 (joining) | 자원 preserve + marker 박제 만 (`joined`) |
| 기존 | 같은 회사 | silent skip — 완전 멱등 (`silent`) |
| 기존 | 다른 회사 | confirm 강제 (`marker_replaced`) — `ConfirmRequired` 예외 |

같은 회사를 5개 이상 프로젝트에서 공유 가능. 기존 `company.md` 가 있으면 절대 덮어쓰지 않습니다.

### 2) 작업 호출 — `work`

| 호출 형태 | 동작 |
|---|---|
| `/lskun-kit:work "..."` (이름 생략) | **메인 세션 = CPO** 가 받아 라우팅 → 결재 → 응답. 부재 워커 시 **자동 채용**. |
| `/lskun-kit:work backend-engineer "..."` | 직통 호출 (CPO 결재 생략, cheap path) |
| `/lskun-kit:work cpo "..."` | CPO 와 전략 대화 |
| `/lskun-kit:work hr-lead "..."` | HR Lead 직접 호출 (해고 / 평가 명시 요청용) |
| `/lskun-kit:work <worker> "..." --model=opus` | 워커 dispatch 모델 override (ADR-0004 §4) |

### 3) 채용 — `hire` (자동 또는 수동)

자동 채용은 CPO 가 `Task` tool 로 HR Lead 호출, 사용자 알림 1줄 (차단 X). 수동:

```text
/lskun-kit:hire alice backend-engineer "앨리스 박"
/lskun-kit:hire sec-arch security-architect "Sarah Chen" --domain=핀테크 --model=opus
```

### 4) 기존 회사 schema 보강 — `migrate-schema` (ADR-0005)

0.2 ~ 0.4 사이에 생성된 회사는 frontmatter 필수 필드가 부족할 수 있습니다. v0.4 schema (6 필드 + CLAUDE.md marker) 로 끌어올리는 사용자 confirm 기반 도구:

```text
/lskun-kit:migrate-schema --dry-run    # 변환 계획만 표시
/lskun-kit:migrate-schema              # 인터뷰 후 실행 (자동 백업)
```

원칙 (불변):

- `## Project History` 섹션은 한 줄도 변경하지 않음
- 기존 frontmatter 키 절대 덮어쓰지 않음 (누락 키만 추가)
- 변경 전 `<file>.lskun-pre-migrate.bak` 자동 백업

### 5) 회고 — `reflect` (또는 Stop hook)

CPO 가 워커 보고의 `reflection 후보` 섹션을 자동 박제. 수동 보강:

```text
/lskun-kit:reflect <project> <topic> <pattern> <first_pass_score>
```

---

## Roadmap

### Phase 1 (P0~P7 완료, P8/P9 폐기 by ADR-0002)

```
P0~P7 ✅ ADR-0001 → manifest → storage adapter → reflection → migration
P8/P9 ❌ Dogfooding / KPI 측정 — 폐기 (ADR-0002 §5)
```

### Phase 2 (P10~P16 완료)

```
P10~P16 ✅ ADR-0002 박제 → CPO/HR 템플릿 → /init → /work 라우팅 → /doctor 갱신 → README
```

### Phase 3 (P17~P27 완료)

```
P17~P27 ✅ ADR-0003/0004 박제 → domain 필드 → CPO 라우팅 0단계 → display_name/model →
          /init 5단계 인터뷰 + CLAUDE.md inline 박제 → SessionStart hook →
          CPO/HR persona 재작성 → 모델 라우팅 alias → README 갱신
```

### Phase 4 (P28~P49 완료)

```
P28~P45 ✅ 일상 dogfooding, hire_audit, PreToolUse chain-guard hook, doctor 항목 확장
P46~P48 ✅ dead code 제거 + hook bootstrap ($CLAUDE_PLUGIN_ROOT 직접 경로)
P49     ✅ version bump 0.3.0-dev → 0.4.0-dev
```

### Phase 5 (P50~P51 완료)

```
P50 ✅ ADR-0005 박제 + /lskun-kit:migrate-schema (v0.2/v0.3 → v0.4 자동 보강, history 보존)
P51 ✅ 0.5.0 릴리스 컷 (README / CHANGELOG / version bump)
```

### Phase 6 (P52 완료)

```
P52 ✅ ADR-0006 박제 + lskun_kit/audit.py (CPO 결재 audit log)
       — .audit/decisions.jsonl, AuditEntry, verdict enum 4종 (approved/rework/rejected/rerouted)
       — StorageAdapter.append_audit() ABC 확장 + reflection.record(request_id=...) link
       — doctor 항목 14 신설
       — raw 로그만 박제, 자동 분석/대시보드/KPI 금지 (ADR-0002 §5 유지)
```

### Phase 15 (P83~P93 — Local SSOT 단일화 + 멱등성 + Sync 분리 + 권한 자동 박제 + 워커 해고 결합 해제, ADR-0015, 0.19.0)

```
P83 ✅ ADR-0015 박제 (4 전문가 만장일치 + 사용자 confirm)
P84 ✅ 기존 vault 사용자 마이그레이션 가이드 박제 (README)
P85 ✅ adapters/vault.py + migration.py + tests 폐기 (-938 LoC)
       — plugin core 의 vault 직접 참조 영구 차단
P86 ✅ paths.py 신규 + LocalAdapter.from_company_name (+345 LoC)
       — ~/.lskun-companies/<name>/ 단일 진입점
P87+P88 ✅ init.py 멱등성 4행 + hook marker-based 통일 (+685/-392 LoC)
       — ConfirmRequired 패턴 (옵션 B) + LSKUN_VAULT env 폐기
P89 ✅ permissions.py 신규 (+412 LoC) — settings.json 자동 박제
       — 5개 권한 패턴 (Read/Edit/Write/Bash ls/cat) + 멱등성
P90 ✅ sync-in / sync-out 명령 + sync.py 신규 (+695 LoC)
       — shutil.copytree 만, 외부 SDK 0, 사용자 시점 선택
P91 ✅ CPO templates 의 dispatch Skill 경유 강제 (+32 LoC)
       — Task tool 의 oh-my-claudecode:* / general-purpose fallback 금지
P93 ✅ 워커 해고 결합 해제 (+240 LoC) — WorkerArchivedError + archive_worker
       시그니처 확장 (archived_at + archived_reason) + doctor 진단 2종
P92 ✅ docs 일괄 갱신 + version 0.19.0 (본 phase)
```

핵심 결정: Plugin core 가 회사 자원의 물리적 위치를 결정하는 유일한 모듈 (`paths.py`). 1 회사 N 프로젝트 공유 가능. Vault 통합은 사용자 명시 sync 명령으로만.

215 → 227 tests (+12), 회귀 0.

### Phase 14 (P78~P82 — Reflection 폐기, ADR-0014, 0.18.0)

```
P78 ✅ ADR-0014 박제 + 정체성 동기화 (CLAUDE.md / README / manifest / hub)
P79 ✅ 코드 + tests 제거 (5 sub-commit, 274 → 215 tests, 순 -2316 LoC)
       - reflection.py / audit_diagnostics.py / Stop hook / PostToolUse hook 제거
       - HistoryEntry / append_history ABC / context.py "Past Patterns" 제거
       - routing.py history tie-break / org.py h=N 카운트 제거
       - templates/cpo.md + hr-lead.md 재작성 (JD-driven)
       - commands + docs 일괄 갱신
       - migrate-schema 의 legacy `## Project History` → `## Archived History (pre-0.18)` rename
P80 ✅ docs 일괄 갱신 (CLAUDE.md §3/§5/§6/§7/§8 + README ADR 표 + Phase 14)
P81 ❌ Dogfooding 실측 폐기 (ADR-0002 §5 정책 위반 회피)
P82 - version 0.18.0 + push (사용자 confirm 게이트)
```

핵심 결정: 워커 = 채용 시 완성형 (time-invariant JD). 자산 = JD only (정적 단일 차원). 회사 성장 = 인원 추가 + 도메인 확장.

### Phase 7 (이전 — 0.7.0-dev)

```
P53~P56 ❌ ADR-0007 (SSOT 3축 + .claude/lskun-kit.json link) — 박제 후 전체 폐기
P57     ✅ ADR-0007 폐기 + ADR-0008 박제 (Local-first 유지) + PR #20 revert
        — 3명 전문 에이전트 만장일치 권고 반영 (architect/critic/analyst)
        — YAGNI: multi-project 단일 회사 케이스 0건 + 인프라:핵심 비율 2.7:1 위험
        — ADR-0004 §1 marker = 진실원 복원 + ADR-0001 §4 backend 동등 유지
P58     ✅ ADR-0009 박제 — self-contained default, vault optional, no future promises
        — Local 만으로 모든 핵심 메커니즘 동작. Vault 는 명시 opt-in 통합으로 명문화
        — "future: Notion" 약속 폐기, 외부 도구 컨벤션 박제 제거
        — 문서·예시 디커플링 (절대경로 → placeholder)
```

---

## ADRs (Architectural Decision Records)

본 plugin 의 모든 design pivot 은 ADR 박제 후에만 코드에 반영됩니다.

- [ADR-0001](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0001-2026-05-15-stateful-workers-clean-slate.md) — 창설 (Stateful Workers, Reflection, Zero-Base)
- [ADR-0002](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0002-2026-05-18-cpo-hr-pivot.md) — CPO/HR 도입 (Phase 2)
- [ADR-0003](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0003-2026-05-18-domain-aware-workers.md) — 도메인 인지 워커 (`role × domain`)
- [ADR-0004](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0004-2026-05-18-leader-worker-pivot.md) — 메인 세션 = CPO (Leader-Worker, 자동 채용, 모델 라우팅)
- [ADR-0005](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0005-2026-05-18-schema-migration.md) — Schema 마이그레이션 (`/lskun-kit:migrate-schema`)
- [ADR-0006](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0006-2026-05-18-cpo-decision-audit.md) — CPO 결재 audit log (`.audit/decisions.jsonl`)
- ~~[ADR-0007](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0007-2026-05-19-ssot-3axis-and-project-link.md)~~ — SSOT 3축 + project link (**superseded by ADR-0008**)
- [ADR-0008](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0008-2026-05-19-local-first-no-link.md) — Local-first, vault optional, link 미도입
- [ADR-0009](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0009-2026-05-19-self-contained-default.md) — Self-contained default + 외부 통합은 명시 opt-in (Notion 등 "future" promise 폐기)
- [ADR-0010](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0010-2026-05-19-persona-sync-and-provenance.md) — Persona sync + provenance + 조직도 view (`/lskun-kit:sync-persona` / `/lskun-kit:org`)
- [ADR-0011](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0011-2026-05-20-jd-based-hiring.md) — JD 기반 채용 (persona body 의 JD inline 박제)
- [ADR-0012](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0012-2026-05-20-single-source-version.md) — Plugin version single-source SSOT (`plugin.json` 단일 진실원)
- [ADR-0013](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0013-2026-05-20-stable-org-and-reflection-step.md) — 조직도 stable markdown table (reflection 박제 강제는 ADR-0014 로 부분 폐기)
- [ADR-0014](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0014-2026-05-22-reflection-removal-and-jd-driven-identity.md) — Reflection 메커니즘 완전 폐기 + JD-driven 정체성 박제. 워커 = 채용 시 완성형.
- **[ADR-0015](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0015-2026-05-22-multi-project-company-sharing.md) — Local SSOT 단일화 (`~/.lskun-companies/<name>/`) + `/init` 멱등성 + Vault Mirror 분리 + 권한 자동 박제 + 워커 해고 결합 해제** (결정 7 머지). ADR-0008 supersede. 1 회사 N 프로젝트 공유. Phase 15 (P83~P93) 구현 완료.

---

## License

MIT © 2026 이성근 (`sherwher@sherwher.org`)
