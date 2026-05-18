# LSKunCompanyKit

> AI workers that remember their work.

**LSKunCompanyKit** 은 Claude Code 에서 AI 직원이 작업을 기억하며 자라는 시스템입니다.
저장 위치는 사용자가 고르고, 마이그레이션은 LSKunCompanyKit 이 책임집니다.

- **Status:** `0.2.0-dev` · Phase 2 (CPO/HR pivot — [ADR-0002](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0002-2026-05-18-cpo-hr-pivot.md))
- **License:** MIT
- **Namespace:** `/lskun-kit:*`

---

## 왜 만드는가

기존 multi-agent 프레임워크 (MetaGPT, ChatDev, CrewAI, MemGPT) 는 작업마다 워커의 기억이 초기화됩니다.
LSKunCompanyKit 은 Stanford Generative Agents (UIST 2023, arXiv:2304.03442) 의 **Reflection** 메커니즘을
markdown 1줄 단위로 자동화해서, 워커가 자기 history 를 다음 작업에 인용하게 만듭니다.

| 기능 | MetaGPT | ChatDev | CrewAI | MemGPT | **LSKunCompanyKit** |
|---|---|---|---|---|---|
| Stateful Workers | ❌ | ❌ | ❌ | ⚠️ | ✅ |
| Reflection 자동 | ❌ | ❌ | ❌ | ❌ | ✅ |
| 인간 가독성 (markdown) | 부분 | 부분 | ❌ | ❌ | ✅ |
| Storage Backend 추상화 | ❌ | ❌ | ❌ | ❌ | ✅ |
| Migration tool | ❌ | ❌ | ❌ | ❌ | ✅ |
| 멀티 PC 자연 동기화 | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## 핵심 메커니즘 — Reflection

작업 종료 hook 이 storage backend 에 1줄을 append 합니다:

```markdown
## Project History
- 2026-05-15 / payment-svc / idempotency / stripe-key-as-idem / first-pass 92%
```

다음 작업 시 워커는 자기 history 를 자동 주입받고, 과거 패턴을 인용합니다:

> "이전 음원 결제에서 idempotency key 패턴을 썼습니다. 이번 케이스에도 적합해 보입니다."

**시작/종료에 `.md` 1줄씩만. ceremony 0.**

---

## Storage Backend 추상화

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

v0.2 backend (2종):

| Backend | 경로 | 선택 조건 |
|---|---|---|
| **Vault** | `<vault>/03_Companies/<company-name>/` | `LSKUN_VAULT` 환경변수 있을 때 |
| **Local** (기본값) | `<project-root>/.company/` | 환경변수 없을 때 자동 |

Backend 간 이동: `/lskun-kit:migrate --from=local --to=vault` (SHA-256 무결성 보장).

---

## SSOT 분리

| 영역 | 위치 | 내용 |
|---|---|---|
| Plugin 개발자 SSOT | 본 repo | ADR / Phase 계획 / interface 설계 |
| 사용자 SSOT — Vault | `<vault>/03_Companies/<name>/` | hired/ reflections/ projects/ company.md |
| 사용자 SSOT — Local | `<project-root>/.company/` | (동일 구조) |

두 SSOT 는 물리적으로 분리되며, `/lskun-kit:doctor` 가 cross-contamination 을 검증합니다.

---

## 설치 (개발 중)

> 0.1.0-dev 는 아직 marketplace 정식 등록 전입니다. Claude Code 의 `/plugin` 은 marketplace 경유로만 설치되므로, 본 repo 자체를 marketplace 로 등록해야 합니다.

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

## 사용 흐름 (Phase 2)

### 1) 회사 셋업 — `init`

신규 회사 셋업의 단일 진입점. backend 자동 감지 + CPO + 인사팀장 자동 hire.

```text
# Local backend (가장 가벼움)
/lskun-kit:init

# Vault backend
export LSKUN_VAULT="$HOME/Documents/private-workspaces/obsidian-vault"
/lskun-kit:init Acme "AI agents for SMB compliance"
```

기존 `company.md` 가 있으면 **절대 덮어쓰지 않습니다** (ADR-0002 §3 보존 정책).

### 2) 작업 호출 — `work`

| 호출 형태 | 동작 |
|---|---|
| `/lskun-kit:work backend-engineer "..."` | 직통 호출 (CPO 경유 안 함) |
| `/lskun-kit:work cpo "..."` | CPO 와 전략 대화 |
| `/lskun-kit:work "..."` (이름 생략) | **CPO 가 적합 워커를 추천**, 사용자가 다음 명령 실행 |

CPO 는 인사팀장을 **자동으로 호출하지 않습니다** (ADR-0002 §1). 적합한 워커가 없으면 사용자에게 `/lskun-kit:work hr-lead "신규 채용 ..."` 을 권장만 합니다.

### 3) 회고 — `reflect` (또는 Stop hook)

작업 종료 시 1줄 박제. Stop hook 자동 또는 `/lskun-kit:reflect <project> <topic> <pattern> <score>` 수동.

---

## Roadmap

### Phase 1 (P0~P7 완료, P8/P9 폐기 by [ADR-0002](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0002-2026-05-18-cpo-hr-pivot.md))

```
P0~P7 ✅ ADR-0001 → manifest → storage adapter → reflection → migration
P8/P9 ❌ Dogfooding / KPI 측정 — 폐기 (ADR-0002 §5)
```

### Phase 2 (현재)

```
P10 ✅ ADR-0002 박제 (CPO/HR pivot)
P11 ✅ CLAUDE.md / docs 갱신
P12 ✅ CPO / HR 워커 템플릿 (src/lskun_kit/templates/)
P13 ✅ /lskun-kit:init
P14 ✅ /lskun-kit:work 라우팅
P15 ✅ /lskun-kit:doctor 갱신 (init 상태 + CPO/HR 점검)
P16 ✅ README 갱신
```

> 이전 [`docs/p8-dogfooding-guide.md`](docs/p8-dogfooding-guide.md) 는 deprecated. 역사적 참조용으로만 보존됩니다.

---

## License

MIT © 2026 이성근 (`sherwher@sherwher.org`)
