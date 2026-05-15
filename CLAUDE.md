# LSKunCompanyKit — Claude Code Instructions

> 본 문서는 LSKunCompanyKit 저장소에서 Claude Code 가 따라야 할 프로젝트 헌법.
> 상위 결정문: [ADR-0001](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0001-2026-05-15-stateful-workers-clean-slate.md)
> Developer SSOT hub: `obsidian-vault/02_Projects/LSKunCompanyKit/LSKunCompanyKit-hub.md`

---

## 1. 프로젝트 정체성

- **이름:** LSKunCompanyKit
- **종류:** Claude Code plugin
- **버전:** 0.1.0-dev (zero-base, pre-alpha)
- **GitHub:** `github.com/sherwher/LSKunCompanyKit`
- **Plugin manifest name:** `LSKunCompanyKit`
- **Slash command namespace:** `/lskun-kit:*` (다른 prefix 사용 금지)
- **라이선스:** MIT

### 한 줄 정체성

> "Claude Code 에서 AI 직원이 작업을 기억하며 자라는 시스템.
> 저장 위치는 사용자 선택, 마이그레이션은 LSKunCompanyKit 책임."

---

## 2. 핵심 메커니즘 — 단 1개

**Reflection — 작업 종료 시 자동 기록.**

```
작업 종료 hook → storage backend 에 자동 append:
  hired/<worker>.md 의 ## Project History 에 1줄 추가
        ↓
다음 작업 → 워커 자기 history 자동 주입 → 과거 패턴 인용
```

원칙: 시작/종료에 `.md` 1줄씩만. **ceremony 0.** 추가 단계 만들지 말 것.

---

## 3. Storage Backend 추상화

```
LSKunCompanyKit core (interface 만 알고 구현은 모름)
   └── StorageAdapter
         read_worker(name), append_history(name, entry),
         list_workers(), read_company()
              ↓
       Local | Vault | (future: Notion, ...)
```

v0.1 출시 backend (2종):

| Backend | 경로 |
|---|---|
| Local (기본값) | `<project-root>/.company/` |
| Vault | `<vault>/03_Companies/<company-name>/` |

Migration tool: `/lskun-kit:migrate --from=X --to=Y` (LSKunCompanyKit 책임).

---

## 4. SSOT 분리 정책 (강제)

| 영역 | 위치 | 내용 |
|---|---|---|
| **개발자 SSOT** | `02_Projects/LSKunCompanyKit/` (Vault) | ADR / Phase 계획 / interface 설계 |
| **사용자 SSOT — Vault** | `03_Companies/<company-name>/` | hired/ / reflections/ / projects/ / company.md |
| **사용자 SSOT — Local** | `<project-root>/.company/` | (동일 구조) |

### 강제 규칙

- 두 SSOT 위치를 plugin 본체가 명시적으로 다른 path 로 처리한다.
- 개발자 SSOT 에 회사 운영 데이터 (hired/, reflections/) 쓰지 말 것.
- 사용자 SSOT 에 plugin 알고리즘 ADR 쓰지 말 것.
- `/lskun-kit:doctor` 가 cross-contamination 을 검증한다.

---

## 5. Zero-Base 원칙

이전 ai-company / claude-company-kit 의 어떤 자산도 **승계 금지**. 컨셉만 가져온다.

| 영역 | 처리 |
|---|---|
| 옛 코드 / scripts / templates | ❌ 0 승계 |
| 옛 plugin manifest / hooks | ❌ 새로 작성 |
| 옛 release.sh sanitize | ❌ 새로 작성 |
| 옛 GitHub repo (`claude-company-kit`) | 방치, archive 표시 안 함 |
| 옛 clone 폴더 / CLI / plugin install | 사용자 측에서 정리 완료 |
| Git history | 새 repo, 새 commit history |

**컨셉만 승계:** Stateful Workers + Reflection + Storage Abstraction + SSOT 분리.

---

## 6. 절대 만들지 말 것 (ADR-0001 §7 폐기 목록)

다음을 도입하려는 충동이 들면 **즉시 멈추고 ADR 우선 작성:**

- Founding Team / CPO / COO / HR Lead / Brainstormer / Strategist / PM 같은 임원 컨셉
- PRD 사이클 강제
- persona evolution / 분기 회고
- CLI (`company` 명령) — slash command 만 허용
- cmux / tmux / sequential runner harness
- 정적 26 워커 정의
- scaffold 의 11 디렉토리 강제
- Workload Budget 강제
- CLAUDE.md 에 leader-worker 강제 규칙
- "회사 운영 OS" / "Growing Company" 같은 비대화 narrative

---

## 7. 디렉토리 구조 (현재)

```
LSKunCompanyKit/
├── .claude-plugin/
│   ├── plugin.json           # P3 작성
│   └── marketplace.json
├── commands/                  # 5개 slash command
│   ├── doctor.md             # /lskun-kit:doctor    (P3)
│   ├── hire.md               # /lskun-kit:hire      (P6)
│   ├── work.md               # /lskun-kit:work      (P6)
│   ├── reflect.md            # /lskun-kit:reflect   (P6)
│   └── migrate.md            # /lskun-kit:migrate   (P7)
├── src/lskun_kit/             # Python core (stdlib only, 0 외부 의존성)
│   ├── adapters/             # StorageAdapter ABC, MarkdownTreeAdapter, Local, Vault, frontmatter
│   ├── hooks/                # Claude Code hook 진입점 (stop_reflect)
│   ├── models.py             # Worker / HistoryEntry / Company
│   ├── errors.py             # LSKunKitError 계층
│   ├── session.py            # 활성 워커 1명 프로세스 간 공유
│   ├── context.py            # build_worker_context (history 컨텍스트 주입)
│   ├── reflection.py         # record (history 1줄 append)
│   ├── metrics.py            # estimate_citation_rate (KPI 측정)
│   └── migration.py          # plan / execute (Local ↔ Vault)
├── tests/                     # stdlib unittest, 52 케이스 (P4 14 + P5 10 + P6 21 + P7 7)
├── docs/                      # storage-adapter-spec, reflection-spec, migration-spec, p8-dogfooding-guide
├── CLAUDE.md                 # 본 문서
├── LICENSE                   # MIT (P2 완료)
└── README.md
```

**hired/ / reflections/ / projects/ 같은 회사 운영 데이터는 본 repo 에 절대 작성 금지.**
사용자 SSOT (Vault 또는 `.company/`) 에만 존재해야 함.

---

## 8. Phase 1 로드맵

```
P0 ✅ ADR-0001 박제
P1 ✅ 옛 plugin / CLI 정리
P2 ✅ GitHub repo + 로컬 작업 위치 + LICENSE
P3 ✅ Plugin manifest + namespace + /lskun-kit:doctor             (#1)
P4 ✅ StorageAdapter 인터페이스 + LocalAdapter                    (#2)
P5 ✅ VaultAdapter + MarkdownTreeAdapter 공통 베이스              (#3)
P6 ✅ Reflection 자동화 (session/context/metrics/hook + 3 명령)   (#4)
P7 ✅ Migration tool (/lskun-kit:migrate)                         (#5)
P8 ⏳ Dogfooding (1주, Vault backend + 멀티 PC)                   ← 현재
P9    KPI 측정 → 채택 / 폐기 / 조건부 채택 판정 (ADR-0002 박제)
```

도그푸딩 가이드: `docs/p8-dogfooding-guide.md`

---

## 9. 검증 KPI (Phase 1 완료 시점)

| KPI | 목표 |
|---|---|
| Reflection 인용율 | 60%+ |
| 사용자 효용 (정성) | "내 직원이 기억한다" 느낌 |
| 토큰 영향 | < 20% 증가 |
| 멀티 PC 동기화 충돌 | 월 1회 미만 |
| Migration 무결성 | 데이터 손실 0 |

미달 시 → 컨셉 폐기 가능. dogfooding 결과가 최종 판정자.

---

## 10. 작업 규칙

- **커밋:** Conventional Commits (`feat:` / `fix:` / `refactor:` / `docs:` / `test:` / `chore:`)
- **PR:** ≤ 1 feature, ≤ 500 lines
- **언어:** 코드 식별자는 영어, 주석/문서/커밋 메시지는 한국어 허용
- **SRP** 준수
- **금지:** `.env` 편집 / prod config 변경 / 코드 내 secrets / 옛 자산 복붙
- **결정 변경:** ADR-0001 의 §1 정체성, §3 핵심 메커니즘, §4 Storage 추상화, §5 SSOT 분리, §6 Zero-Base, §7 폐기 목록을 변경하려면 새 ADR 박제 필요. CLAUDE.md 만 고치지 말 것.
