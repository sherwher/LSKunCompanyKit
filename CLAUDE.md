# LSKunCompanyKit — Claude Code Instructions

> 본 문서는 LSKunCompanyKit 저장소에서 Claude Code 가 따라야 할 프로젝트 헌법.
> 상위 결정문:
> - [ADR-0001](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0001-2026-05-15-stateful-workers-clean-slate.md) — 창설
> - [ADR-0002](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0002-2026-05-18-cpo-hr-pivot.md) — CPO/HR pivot (Phase 2 진입)
>
> Developer SSOT hub: `obsidian-vault/02_Projects/LSKunCompanyKit/LSKunCompanyKit-hub.md`

---

## 1. 프로젝트 정체성

- **이름:** LSKunCompanyKit
- **종류:** Claude Code plugin
- **버전:** 0.2.0-dev (Phase 2 — CPO/HR pivot, ADR-0002)
- **GitHub:** `github.com/sherwher/LSKunCompanyKit`
- **Plugin manifest name:** `LSKunCompanyKit`
- **Slash command namespace:** `/lskun-kit:*` (다른 prefix 사용 금지)
- **라이선스:** MIT

### 한 줄 정체성

> "Claude Code 에서 AI 직원이 작업을 기억하며 자라는 시스템.
> 저장 위치는 사용자 선택, 마이그레이션은 LSKunCompanyKit 책임."

### Slash commands (현재)

| 명령 | 역할 |
|---|---|
| `/lskun-kit:init` | 신규 회사 셋업 + CPO/HR 자동 hire (P13) |
| `/lskun-kit:hire` | 신규 워커 박제 (primitive) |
| `/lskun-kit:work` | 워커 호출. 이름 생략 시 CPO 가 라우팅 (P14) |
| `/lskun-kit:reflect` | 작업 종료 1줄 기록 (수동) |
| `/lskun-kit:migrate` | Local ↔ Vault 무결성 이동 |
| `/lskun-kit:doctor` | 환경 진단 |

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

v0.2 backend (2종, ADR-0002 §4 SSOT 야망 A 유지):

| Backend | 경로 | 선택 조건 |
|---|---|---|
| Vault | `<vault>/03_Companies/<company-name>/` | `LSKUN_VAULT` 환경변수 설정 시 우선 |
| Local (기본값) | `<project-root>/.company/` | 환경변수 없으면 자동 선택 |

Migration tool: `/lskun-kit:migrate --from=X --to=Y`.

---

## 4. SSOT 분리 정책 (강제)

| 영역 | 위치 | 내용 |
|---|---|---|
| **개발자 SSOT** | `02_Projects/LSKunCompanyKit/` (Vault) | ADR / Phase 계획 / interface 설계 |
| **사용자 SSOT — Vault** | `03_Companies/<company-name>/` | hired/ / company.md (회사 일반 운영 문서와 공존) |
| **사용자 SSOT — Local** | `<project-root>/.company/` | (동일 구조) |

### 강제 규칙

- 두 SSOT 위치를 plugin 본체가 명시적으로 다른 path 로 처리한다.
- 개발자 SSOT 에 회사 운영 데이터 (hired/ 등) 쓰지 말 것.
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

## 6. 절대 만들지 말 것 (ADR-0001 §7 + ADR-0002 §6 부분 폐기 반영)

다음을 도입하려는 충동이 들면 **즉시 멈추고 ADR 우선 작성:**

- PRD 사이클 강제
- persona evolution / 분기 회고
- CLI (`company` 명령) — slash command 만 허용
- cmux / tmux / sequential runner harness
- 정적 26 워커 정의
- scaffold 의 11 디렉토리 강제
- Workload Budget 강제
- CLAUDE.md 에 leader-worker 강제 규칙
- "회사 운영 OS" / "Growing Company" 같은 비대화 narrative
- COO / Brainstormer / Strategist / PM 등 임원 자동 추가
- CPO 가 인사팀장을 자동 chain 호출 (사용자 승인 1단계 필수)

### ADR-0002 로 **허용된 예외 (2명 한정)**

- **CPO** — `/lskun-kit:work` 의 워커 이름 생략 시 라우터로 동작
- **인사팀장 (HR Lead)** — 사용자 명시 호출 시 채용·해고·평가 동작

> 이 2명 외의 임원 컨셉을 추가하려면 새 ADR 박제 필요. 본 예외는 ADR-0002 §1~§2 가 정의한다.

---

## 7. 디렉토리 구조 (현재)

```
LSKunCompanyKit/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── commands/                  # 6개 slash command
│   ├── init.md               # /lskun-kit:init       (P13)
│   ├── doctor.md             # /lskun-kit:doctor
│   ├── hire.md               # /lskun-kit:hire
│   ├── work.md               # /lskun-kit:work       (라우팅, P14)
│   ├── reflect.md            # /lskun-kit:reflect
│   └── migrate.md            # /lskun-kit:migrate
├── src/lskun_kit/             # Python core (stdlib only, 0 외부 의존성)
│   ├── adapters/             # StorageAdapter ABC, MarkdownTreeAdapter, Local, Vault, frontmatter
│   ├── hooks/                # Claude Code hook 진입점 (stop_reflect)
│   ├── templates/            # CPO / HR 워커 markdown 템플릿 (P12)
│   ├── models.py             # Worker / HistoryEntry / Company
│   ├── errors.py             # LSKunKitError 계층
│   ├── session.py            # 활성 워커 1명 프로세스 간 공유
│   ├── context.py            # build_worker_context (history 컨텍스트 주입)
│   ├── reflection.py         # record (history 1줄 append)
│   ├── metrics.py            # estimate_citation_rate (deprecated, ADR-0002 §5)
│   ├── migration.py          # plan / execute (Local ↔ Vault)
│   ├── init.py               # 회사 셋업 + CPO/HR auto-hire (P13)
│   └── routing.py            # CPO 라우팅 컨텍스트 빌더 (P14)
├── tests/                     # stdlib unittest
├── docs/                      # storage-adapter-spec, reflection-spec, migration-spec
│                              # (p8-dogfooding-guide.md → deprecated, ADR-0002 §5)
├── CLAUDE.md                 # 본 문서
├── LICENSE                   # MIT
└── README.md
```

**hired/ 같은 회사 운영 데이터는 본 repo 에 절대 작성 금지.**
사용자 SSOT (Vault 또는 `.company/`) 에만 존재해야 함.

---

## 8. 로드맵

### Phase 1 (P0~P7 완료, P8/P9 폐기 by ADR-0002)

```
P0 ✅ ADR-0001 박제
P1 ✅ 옛 plugin / CLI 정리
P2 ✅ GitHub repo + 로컬 작업 위치 + LICENSE
P3 ✅ Plugin manifest + namespace + /lskun-kit:doctor             (#1)
P4 ✅ StorageAdapter 인터페이스 + LocalAdapter                    (#2)
P5 ✅ VaultAdapter + MarkdownTreeAdapter 공통 베이스              (#3)
P6 ✅ Reflection 자동화 (session/context/metrics/hook + 3 명령)   (#4)
P7 ✅ Migration tool (/lskun-kit:migrate)                         (#5)
P8 ❌ Dogfooding — 폐기 (ADR-0002 §5)
P9 ❌ KPI 측정 — 폐기 (ADR-0002 §5)
```

### Phase 2 (현재)

```
P10 ✅ ADR-0002 박제 (CPO/HR pivot, 2026-05-18)
P11 ⏳ CLAUDE.md 갱신 (본 문서)                                   ← 진행 중
P12    CPO / HR 워커 템플릿 (src/lskun_kit/templates/)
P13    /lskun-kit:init 구현
P14    /lskun-kit:work 라우팅 로직
P15    /lskun-kit:doctor 갱신 (init 미실행 / CPO·HR 존재 점검)
P16    README / docs 갱신
P17 -  일상 사용. KPI 검증 없음.
```

---

## 9. CPO / 인사팀장 동작 사양 (ADR-0002)

### CPO (Chief Product Officer)

- **호출 모델:** `/lskun-kit:work` 의 워커 이름 **생략 시에만** CPO 라우팅 (Q1=ii)
  - `/lskun-kit:work backend-engineer "..."` → 직통, CPO 경유 안 함
  - `/lskun-kit:work "..."` → CPO 가 받아 적절한 워커 추천
  - `/lskun-kit:work cpo "..."` → CPO 와 전략 대화
- **책임:** 요청 분석 → 워커 라우팅 / 적합 워커 없으면 "인사팀장에게 X 채용 요청 권장" 메시지 출력
- **금지:** 인사팀장 자동 호출 (사용자 승인 1단계 필수), 결재 라인 구성, 자동 PRD/로드맵

### 인사팀장 (HR Lead)

- **호출 모델:** `/lskun-kit:work hr-lead "..."` 사용자 명시 호출만 (Q2=i)
- **책임:** 채용 (`/lskun-kit:hire` wrapping), 해고 (워커 archive), 평가 (history 분석 리포트)
- **금지:** CPO 응답을 받아 자동 chain 실행, 사용자 미요청 정기 평가/리포트

---

## 10. 작업 규칙

- **커밋:** Conventional Commits (`feat:` / `fix:` / `refactor:` / `docs:` / `test:` / `chore:`)
- **PR:** ≤ 1 feature, ≤ 500 lines
- **언어:** 코드 식별자는 영어, 주석/문서/커밋 메시지는 한국어 허용
- **SRP** 준수
- **금지:** `.env` 편집 / prod config 변경 / 코드 내 secrets / 옛 자산 복붙
- **결정 변경:** ADR-0001 의 §1 정체성, §3 핵심 메커니즘, §4 Storage 추상화, §5 SSOT 분리, §6 Zero-Base, §7 폐기 목록 및 ADR-0002 의 결정 사항을 변경하려면 새 ADR 박제 필요. CLAUDE.md 만 고치지 말 것.
