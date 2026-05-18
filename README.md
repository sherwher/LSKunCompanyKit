# LSKunCompanyKit

> AI workers that remember their work. The main session **is** the CPO.

**LSKunCompanyKit** 은 Claude Code 에서 AI 직원이 작업을 기억하며 자라는 시스템입니다. 메인 세션 자체가 회사의 **CPO** 로 동작하여 적합 워커를 자동 라우팅·결재하고, 없으면 자동으로 채용합니다. 도메인 (의료/금융/교육 등) 별 전문가 채용으로 reflection 자산이 도메인 단위로 축적됩니다.

- **Status:** `0.3.0-dev` · Phase 3 (Leader-Worker pivot — [ADR-0004](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0004-2026-05-18-leader-worker-pivot.md))
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
       Local | Vault | (future: Notion, ...)
```

| Backend | 경로 | 선택 조건 |
|---|---|---|
| **Vault** | `<vault>/03_Companies/<company-name>/` | `LSKUN_VAULT` 환경변수 있을 때 |
| **Local** (기본값) | `<project-root>/.company/` | 환경변수 없을 때 자동 |

Backend 간 이동: `/lskun-kit:migrate --from=local --to=vault` (SHA-256 무결성 보장).

---

## SSOT 분리

| 영역 | 위치 | 내용 |
|---|---|---|
| Plugin 개발자 SSOT | 본 repo + `obsidian-vault/02_Projects/LSKunCompanyKit/` | ADR / Phase 계획 / interface 설계 |
| 사용자 SSOT — Vault | `<vault>/03_Companies/<name>/` | `company.md` / `hired/` |
| 사용자 SSOT — Local | `<project-root>/.company/` | (동일 구조) |

두 SSOT 는 물리적으로 분리되며 `/lskun-kit:doctor` 가 cross-contamination 을 검증합니다.

또한 ADR-0004 §1 에 따라 **사용자 프로젝트 root 의 `CLAUDE.md`** 에 marker 구간 (`<!-- LSKUN-CPO:START -->` ~ `<!-- LSKUN-CPO:END -->`) 으로 CPO persona 가 inline 박제됩니다. marker 외 본문은 한 줄도 건드리지 않습니다.

---

## 설치

> 0.3.0-dev 는 marketplace 정식 등록 전입니다. 본 repo 자체를 marketplace 로 등록해야 합니다.

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
# Local backend
/lskun-kit:init

# Vault backend
export LSKUN_VAULT="$HOME/Documents/private-workspaces/obsidian-vault"
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

### 4) 회고 — `reflect` (또는 Stop hook)

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

### Phase 3 (현재)

```
P17 ✅ ADR-0003 박제 (도메인 인지 워커)
P18 ✅ ADR-0003 코드 (domain 필드 + CPO/HR persona 라우팅 0단계)
P21 ✅ ADR-0004 박제 (메인 세션 = CPO, Leader-Worker, 자동 채용)
P22 ✅ display_name + model 필드
P23 ✅ /init 인터뷰 5단계 + CLAUDE.md inline 박제 (layer A)
P24 ✅ SessionStart hook 으로 활성 회사 dynamic context 주입 (layer B)
P25 ✅ CPO/HR persona 본문 재작성 (Leader-Worker dispatch / 자동 채용)
P26 ✅ 모델 라우팅 (alias) + hire/work --model --domain 옵션
P27 ✅ 본 README / docs / version bump (0.2.0-dev → 0.3.0-dev)
P28 - 일상 사용. KPI 검증 없음 (ADR-0002 §5 정책 유지).
```

---

## ADRs (Architectural Decision Records)

본 plugin 의 모든 design pivot 은 ADR 박제 후에만 코드에 반영됩니다.

- [ADR-0001](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0001-2026-05-15-stateful-workers-clean-slate.md) — 창설 (Stateful Workers, Reflection, Zero-Base)
- [ADR-0002](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0002-2026-05-18-cpo-hr-pivot.md) — CPO/HR 도입 (Phase 2)
- [ADR-0003](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0003-2026-05-18-domain-aware-workers.md) — 도메인 인지 워커 (`role × domain`)
- [ADR-0004](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0004-2026-05-18-leader-worker-pivot.md) — 메인 세션 = CPO (Leader-Worker, 자동 채용, 모델 라우팅)

이전 [`docs/p8-dogfooding-guide.md`](docs/p8-dogfooding-guide.md) 는 deprecated. 역사적 참조용으로만 보존됩니다.

---

## License

MIT © 2026 이성근 (`sherwher@sherwher.org`)
