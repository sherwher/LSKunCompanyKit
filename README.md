# LSKunCompanyKit

> AI workers that remember their work. The main session **is** the CPO.

**LSKunCompanyKit** 은 Claude Code 에서 AI 직원이 작업을 기억하며 자라는 시스템입니다. 메인 세션 자체가 회사의 **CPO** 로 동작하여 적합 워커를 자동 라우팅·결재하고, 없으면 자동으로 채용합니다. 도메인 (의료/금융/교육 등) 별 전문가 채용으로 reflection 자산이 도메인 단위로 축적됩니다.

- **Status:** Version 은 `.claude-plugin/plugin.json` 의 `version` 필드가 단일 진실원 (ADR-0012). 가장 최근 design pivot 은 [ADR-0012](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0012-2026-05-20-single-source-version.md) (단일 SSOT version 정책)
- **License:** MIT
- **Namespace:** `/lskun-kit:*`

---

## 왜 만드는가

기존 multi-agent 프레임워크 (MetaGPT, ChatDev, CrewAI, MemGPT) 는 작업마다 워커의 기억이 초기화됩니다. LSKunCompanyKit 은 다음 4가지를 결합합니다:

1. **Stateful Workers + Reflection** — Stanford Generative Agents (UIST 2023, arXiv:2304.03442) 의 메커니즘을 markdown 1줄 단위로 자동화
2. **Leader–Worker (메인 세션 = CPO)** — 사용자 요청 → CPO 라우팅 → 워커 dispatch → 결재 → 응답을 한 세션 안에서 수행
3. **도메인 인지 (`role × domain`)** — 의료 backend-engineer vs 핀테크 backend-engineer 의 reflection 자산이 분리되어 시간이 갈수록 도메인 격차가 벌어짐
4. **Storage Backend 추상화** — Local (`.company/`) 또는 Vault (`<vault>/03_Companies/<company>/`). 사용자 선택, plugin 이 마이그레이션 책임

| 기능 | MetaGPT | ChatDev | CrewAI | MemGPT | **LSKunCompanyKit** |
|---|---|---|---|---|---|
| Stateful Workers | ❌ | ❌ | ❌ | ⚠️ | ✅ |
| Reflection 자동 | ❌ | ❌ | ❌ | ❌ | ✅ |
| Leader–Worker 결재 | ❌ | ❌ | ❌ | ❌ | ✅ |
| 도메인 전문가 채용 | ❌ | ❌ | ❌ | ❌ | ✅ |
| 자동 채용 (사용자 알림만) | ❌ | ❌ | ❌ | ❌ | ✅ |
| 인간 가독성 (markdown) | 부분 | 부분 | ❌ | ❌ | ✅ |
| Storage Backend 추상화 | ❌ | ❌ | ❌ | ❌ | ✅ |
| Migration tool | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## 메커니즘 1 — Reflection (ADR-0001)

작업 종료 hook 이 storage backend 에 1줄 append:

```markdown
## Project History
- 2026-05-15 / payment-svc / idempotency / stripe-key-as-idem / first-pass 92%
```

다음 작업 시 워커는 자기 history 를 자동 주입받고 과거 패턴을 인용합니다:

> "이전 음원 결제에서 idempotency key 패턴을 썼습니다. 이번 케이스에도 적합해 보입니다."

시작/종료에 `.md` 1줄씩만. **ceremony 0.**

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

- **결재:** 워커 보고의 first-pass 점수와 사용자 요청 부합 여부 검수, 미달 시 재작업 (최대 2회)
- **자동 채용:** 적합 워커 없으면 HR Lead 를 Task tool 로 호출 → 채용 → `[채용 알림]` 1줄 → 신규 워커 dispatch (사용자 차단 X)
- **모델 라우팅:** 워커 default = Sonnet, frontmatter `model` 또는 CPO 동적 override 로 Opus
- **금지:** 워커 → 워커 chain (sub-leader 출현 방지), CPO/HR 외 임원 자동 추가, persona evolution narrative

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

- 같은 `role` 이라도 `domain` 마다 reflection history 가 분리 → "HIPAA PHI 마스킹 로깅 패턴" 같은 도메인 자산이 누적
- CPO 라우팅 0순위 = 회사 `domain` 일치 워커
- 도메인 미일치 시 일반 워커 fallback + "도메인 전문가 채용 권장" 메시지
- 사전 정의 카탈로그 없음 (`medical`, `fintech` 등 enum 강제 X) — 자유 입력

---

## Storage Backend

```
LSKunCompanyKit core (interface 만 알고 구현은 모름)
   └── StorageAdapter
         read_worker(name)
         append_history(name, entry)
         list_workers()
         read_company()
              ↓
       Local (default, self-contained) | Vault (Optional Integration)
```

| Backend | 경로 | 선택 조건 |
|---|---|---|
| **Local** (default) | `<project-root>/.company/` | 항상 사용 가능 — **plugin 자체 동작, 외부 의존성 0** |
| **Vault** (Optional) | `<your-vault>/03_Companies/<company-name>/` | `LSKUN_VAULT` 환경변수 명시 설정 시 (opt-in) |

ADR-0009 — Local 만으로 Reflection / Stateful Workers / CPO 결재 / audit log 모두 완전 동작. Vault 는 사용자가 명시 opt-in 한 통합이며, 다른 외부 시스템 (Notion 등) 통합은 별도 add-on package 책임으로 본 core 에 두지 않는다.

Backend 간 이동: `/lskun-kit:migrate --from=local --to=vault` (SHA-256 무결성 보장).

---

## SSOT 분리

| 영역 | 위치 | 내용 |
|---|---|---|
| Plugin 개발자 SSOT | 본 repo (코드) + 저자별 별도 위치 (ADR / Phase 계획) | plugin 본 repo 의 문서는 저자 개인 SSOT 위치를 박제하지 않는다 (ADR-0009) |
| 사용자 SSOT — Local (default) | `<project-root>/.company/` | `company.md` / `hired/` |
| 사용자 SSOT — Vault (opt-in) | `<your-vault>/03_Companies/<name>/` | (동일 구조) |

두 SSOT 는 물리적으로 분리되며 `/lskun-kit:doctor` 가 cross-contamination 을 검증합니다.

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

### 1) 회사 셋업 — `init`

신규 회사 셋업의 단일 진입점. backend 자동 감지 + 회사 `domain` 박제 + CPO/HR 자동 hire + 사용자 프로젝트 CLAUDE.md 에 CPO persona inline 박제.

```text
# Local backend (default — self-contained)
/lskun-kit:init

# Vault backend (Optional — opt-in 통합)
export LSKUN_VAULT="<your-vault-root>"
/lskun-kit:init Acme "AI agents for SMB compliance"
```

Claude 가 5가지를 순차 질문:

1. 회사 이름
2. 회사 한 줄 소개
3. 회사 도메인 (예: "의료 SaaS")
4. CPO 의 사람 이름 (`display_name`, 자동 생성 금지)
5. HR Lead 의 사람 이름 (`display_name`)

기존 `company.md` 가 있으면 절대 덮어쓰지 않습니다.

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

### Phase 7 (현재 — 0.7.0-dev)

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

이전 [`docs/p8-dogfooding-guide.md`](docs/p8-dogfooding-guide.md) 는 deprecated. 역사적 참조용으로만 보존됩니다.

---

## License

MIT © 2026 이성근 (`sherwher@sherwher.org`)
