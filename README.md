# LSKunCompanyKit

> AI workers that remember their work.

**LSKunCompanyKit** 은 Claude Code 에서 AI 직원이 작업을 기억하며 자라는 시스템입니다.
저장 위치는 사용자가 고르고, 마이그레이션은 LSKunCompanyKit 이 책임집니다.

- **Status:** `0.1.0-dev` · pre-alpha · zero-base 시작
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

v0.1 출시 backend (2종):

| Backend | 경로 |
|---|---|
| **Local** (기본값) | `<project-root>/.company/` |
| **Vault** | `<vault>/03_Companies/<company-name>/` |

Backend 간 이동: `/lskun-kit:migrate --from=local --to=vault` (Phase 1 후반 구현).

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

> 0.1.0-dev 는 아직 marketplace 정식 등록 전입니다. 로컬 clone 으로 시험할 수 있습니다.

```bash
git clone https://github.com/sherwher/LSKunCompanyKit.git
cd LSKunCompanyKit

# Claude Code 에서 local plugin 등록
/plugin install ./
```

설치 후 검증:

```text
/lskun-kit:doctor
```

---

## Roadmap (Phase 1)

```
P0 ✅ ADR-0001 박제
P1 ✅ 옛 plugin / CLI 정리
P2 ✅ GitHub repo + 로컬 작업 위치 + LICENSE
P3 ⏳ Plugin manifest + namespace + /lskun-kit:doctor   ← 현재
P4    StorageAdapter 인터페이스 + Local adapter
P5    Vault adapter
P6    Reflection 자동화 (hook + frontmatter schema)
P7    Migration tool (/lskun-kit:migrate)
P8    Dogfooding (Vault backend, 멀티 PC)
P9    KPI 측정
```

---

## License

MIT © 2026 이성근 (`sherwher@sherwher.org`)
