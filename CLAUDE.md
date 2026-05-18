# LSKunCompanyKit — Claude Code Instructions

> 본 문서는 LSKunCompanyKit 저장소에서 Claude Code 가 따라야 할 프로젝트 헌법.
> 상위 결정문:
> - [ADR-0001](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0001-2026-05-15-stateful-workers-clean-slate.md) — 창설
> - [ADR-0002](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0002-2026-05-18-cpo-hr-pivot.md) — CPO/HR pivot (Phase 2 진입)
> - [ADR-0003](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0003-2026-05-18-domain-aware-workers.md) — 도메인 인지 워커 (`role × domain`)
> - [ADR-0004](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0004-2026-05-18-leader-worker-pivot.md) — **메인 세션 = CPO (Leader-Worker, 자동 채용)**
> - [ADR-0005](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0005-2026-05-18-schema-migration.md) — Schema 마이그레이션 (`/lskun-kit:migrate-schema`)
>
> Developer SSOT hub: `obsidian-vault/02_Projects/LSKunCompanyKit/LSKunCompanyKit-hub.md`

---

## 1. 프로젝트 정체성

- **이름:** LSKunCompanyKit
- **종류:** Claude Code plugin
- **버전:** 0.5.0-dev (Phase 5 — schema 마이그레이션 도입, ADR-0005)
- **GitHub:** `github.com/sherwher/LSKunCompanyKit`
- **Plugin manifest name:** `LSKunCompanyKit`
- **Slash command namespace:** `/lskun-kit:*` (다른 prefix 사용 금지)
- **라이선스:** MIT

### 한 줄 정체성

> "Claude Code 의 메인 세션 자체가 회사의 CPO 로 동작하여, AI 직원이 작업을 기억하며 자라는 시스템.
> 사용자 요청 → CPO 자동 라우팅 → 워커 dispatch → 결재 → 응답. 부재 워커는 자동 채용.
> 저장 위치는 사용자 선택, 마이그레이션은 LSKunCompanyKit 책임."

### Slash commands (현재)

| 명령 | 역할 |
|---|---|
| `/lskun-kit:init` | 신규 회사 셋업 + CPO/HR 자동 hire (P13) |
| `/lskun-kit:hire` | 신규 워커 박제 (primitive) |
| `/lskun-kit:work` | 워커 호출. 이름 생략 시 CPO 가 라우팅 (P14) |
| `/lskun-kit:reflect` | 작업 종료 1줄 기록 (수동) |
| `/lskun-kit:migrate` | Local ↔ Vault 무결성 이동 |
| `/lskun-kit:migrate-schema` | 기존 회사 frontmatter 를 v0.4 schema 로 보강 (P50/ADR-0005) |
| `/lskun-kit:doctor` | 환경 진단 |

---

## 2. 핵심 메커니즘 — 3개 (ADR-0001 + ADR-0003 + ADR-0004)

### 2.1 Reflection — 작업 종료 시 자동 기록 (ADR-0001)

```
작업 종료 hook → storage backend 에 자동 append:
  hired/<worker>.md 의 ## Project History 에 1줄 추가
        ↓
다음 작업 → 워커 자기 history 자동 주입 → 과거 패턴 인용
```

원칙: 시작/종료에 `.md` 1줄씩만. **ceremony 0.**

### 2.2 Leader–Worker, 메인 세션 = CPO (ADR-0004)

```
사용자
  ↓
메인 세션 = CPO persona (CLAUDE.md inline 박제 + SessionStart hook 으로 회사 컨텍스트)
  ↓ Task tool
워커 (frontmatter.model = sonnet|opus, persona = hired/<name>.md)
  ↑ 보고 (작업 결과 / first-pass / reflection 후보 3섹션)
메인 세션 = CPO 가 결재 → 사용자 응답
```

CPO 는 **결재 라인 + 단독 채용 권한**. 부재 워커 발견 시 HR Lead 를 Task tool 로 호출하여 자동 채용, 사용자에게 알림 1줄. 워커 → 워커 chain 은 금지 (sub-leader 출현 방지).

### 2.3 Role × Domain — 도메인 인지 워커 (ADR-0003)

같은 `role` 이라도 회사 `domain` 별로 reflection history 가 분리 → 시간이 갈수록 도메인 자산 (예: HIPAA PHI 마스킹, HL7 FHIR 함정) 누적. CPO 라우팅 0순위 = 도메인 일치. 사전 enum 강제 X (자유 입력).

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

## 6. 절대 만들지 말 것 (ADR-0001 §7 + ADR-0002 §6 + ADR-0004 §8 누적)

다음을 도입하려는 충동이 들면 **즉시 멈추고 ADR 우선 작성:**

- PRD 사이클 강제 / 분기 회고 자동 생성
- persona evolution narrative (워커가 시간에 따라 자동 진화하는 서사)
- CLI (`company` 명령) — slash command 만 허용
- cmux / tmux / sequential runner harness
- 정적 26 워커 사전 정의 (자동 채용은 CPO 의 실시간 판단 기반, 사전 정의 X)
- scaffold 의 11 디렉토리 강제
- Workload Budget 강제
- "회사 운영 OS" / "Growing Company" 같은 비대화 슬로건 narrative
- COO / CTO / Brainstormer / Strategist / PM 등 임원 자동 추가 (CPO/HR 외)
- **워커 → 워커 chain (sub-leader 출현)** — chain 권한은 CPO 단독 (ADR-0004 §8)
- **결재 라인 확장** — 부 결재자 / 위원회 / 다단계 승인 (CPO 단독)
- ~~CPO 가 인사팀장을 자동 chain 호출 (사용자 승인 1단계 필수)~~ — **ADR-0004 §3 로 폐기**, 자동 채용 허용

### ADR-0002 로 **허용된 예외 (2명 한정)**

- **CPO** — 메인 세션 자체가 CPO persona 로 동작 (ADR-0004 §1). 결재 라인 + 단독 채용 권한.
- **인사팀장 (HR Lead)** — CPO 가 Task tool 로 호출 시 자동 채용 진행. 사용자 명시 호출은 해고·평가 전용.

> 이 2명 외의 임원 컨셉을 추가하려면 새 ADR 박제 필요. 본 예외는 ADR-0002 §1~§2 및 ADR-0004 §1~§3 이 정의한다.

### ADR-0004 가 폐기한 ADR-0002 단서 조항

ADR-0002 의 다음 조항은 ADR-0004 가 supersede 했다:

- ~~"CPO 가 인사팀장을 chain 호출하지 않는다 / 사용자 승인 1단계 필수"~~ → CPO 자동 채용 허용 (사용자 알림만)
- ~~"CPO 는 결재 라인이 아니다 / 다른 워커의 작업 결과를 검수·승인하지 않는다"~~ → CPO 가 결재 라인
- ~~"HR Lead 는 사용자 명시 호출만 받는다"~~ → CPO 의 Task dispatch 도 수용 (해고만 명시 요청 유지)

### ADR-0005 가 폐기한 ADR-0004 §6 조항

- ~~"frontmatter 5→6 자동 마이그레이션 X / 사용자가 display_name 1줄 수동 추가"~~ → `/lskun-kit:migrate-schema` 로 사용자 confirm 기반 plugin 책임 마이그레이션 (ADR-0005)
- 단, **history 보존 / frontmatter 덮어쓰기 금지 / 백업 강제** 가드는 불변

---

## 7. 디렉토리 구조 (현재)

```
LSKunCompanyKit/
├── .claude-plugin/
│   ├── plugin.json           # version: 0.4.0-dev
│   └── marketplace.json
├── hooks/
│   └── hooks.json            # SessionStart hook 등록 (P24)
├── commands/                  # 6개 slash command
│   ├── init.md               # /lskun-kit:init      (P13/P23 — 5-step 인터뷰 + CLAUDE.md 박제)
│   ├── doctor.md             # /lskun-kit:doctor    (P15/P23 — 13개 진단 항목)
│   ├── hire.md               # /lskun-kit:hire      (P26 — --domain --model 옵션)
│   ├── work.md               # /lskun-kit:work      (P14/P26 — 메인 세션 = CPO, --model)
│   ├── reflect.md            # /lskun-kit:reflect
│   ├── migrate.md            # /lskun-kit:migrate         (Local ↔ Vault)
│   └── migrate-schema.md     # /lskun-kit:migrate-schema  (P50/ADR-0005)
├── src/lskun_kit/             # Python core (stdlib only, 0 외부 의존성)
│   ├── adapters/             # StorageAdapter ABC, MarkdownTreeAdapter, Local, Vault, frontmatter
│   ├── hooks/                # stop_reflect (P6) + session_start (P24)
│   ├── templates/            # CPO / HR persona markdown — P25 본문 (Leader-Worker dispatch)
│   ├── models.py             # Worker / HistoryEntry / Company + REQUIRED_WORKER_FIELDS (6) + MODEL_ALIASES
│   ├── errors.py             # LSKunKitError 계층
│   ├── session.py            # 활성 워커 1명 프로세스 간 공유
│   ├── context.py            # build_worker_context (history 컨텍스트 주입)
│   ├── reflection.py         # record (history 1줄 append)
│   ├── migration.py          # plan / execute (Local ↔ Vault)
│   ├── schema_migration.py   # v0.2/v0.3 → v0.4 frontmatter 보강 (P50/ADR-0005)
│   ├── hire_audit.py         # HR Lead 자동 채용 rate-limit + audit log (P32/P45)
│   ├── init.py               # 회사 셋업 + CPO/HR auto-hire + CLAUDE.md 박제 호출 (P13/P23)
│   ├── persona_injection.py  # CLAUDE.md marker 박제·교체·검출 (P23)
│   └── routing.py            # CPO 라우팅 컨텍스트 빌더 (P14)
├── tests/                     # stdlib unittest, 110+ tests
├── docs/                      # storage-adapter-spec, reflection-spec, migration-spec
│                              # (p8-dogfooding-guide.md → deprecated, ADR-0002 §5)
├── CLAUDE.md                 # 본 문서
├── LICENSE                   # MIT
└── README.md                 # P27 — Phase 3 갱신
```

**hired/ 같은 회사 운영 데이터는 본 repo 에 절대 작성 금지.**
사용자 SSOT (Vault 또는 `.company/`) 에만 존재해야 함.

---

## 8. 로드맵

### Phase 1 (P0~P7 완료, P8/P9 폐기 by ADR-0002)

```
P0~P7 ✅ ADR-0001 → manifest → storage adapter → reflection → migration
P8/P9 ❌ Dogfooding / KPI 측정 — 폐기 (ADR-0002 §5)
```

### Phase 2 (P10~P16 완료)

```
P10 ✅ ADR-0002 박제
P11 ✅ CLAUDE.md 갱신
P12 ✅ CPO / HR 워커 템플릿
P13 ✅ /lskun-kit:init
P14 ✅ /lskun-kit:work 라우팅
P15 ✅ /lskun-kit:doctor 갱신
P16 ✅ README 갱신
```

### Phase 3 (완료)

```
P17 ✅ ADR-0003 박제 (도메인 인지 워커)
P18 ✅ ADR-0003 코드 (domain 필드 + CPO 라우팅 0단계)        (#12)
P21 ✅ ADR-0004 박제 (메인 세션 = CPO, Leader-Worker)
P22 ✅ display_name + model 필드                            (#13)
P23 ✅ init 인터뷰 + CLAUDE.md inline CPO persona 박제       (#14)
P24 ✅ SessionStart hook 으로 활성 회사 dynamic context 주입 (#15)
P25 ✅ CPO/HR persona 본문 재작성 (Leader-Worker dispatch)   (#16)
P26 ✅ 모델 라우팅 + hire/work --model --domain 옵션        (#17)
P27 ✅ README / CLAUDE.md / docs 갱신 + version bump        (본 PR)
P28 - 일상 사용. KPI 검증 없음 (ADR-0002 §5 정책 유지).
```

---

## 9. CPO / 인사팀장 동작 사양 (ADR-0002 + ADR-0004)

### CPO (Chief Product Officer)

- **호출 모델:** 메인 Claude Code 세션 자체가 CPO persona 로 동작 (ADR-0004 §1, CLAUDE.md inline 박제)
  - `/lskun-kit:work "..."` (이름 생략) → CPO 가 받아 라우팅 → 결재 → 응답
  - `/lskun-kit:work backend-engineer "..."` → 직통, CPO 결재 생략 (cheap path)
  - `/lskun-kit:work cpo "..."` → CPO 와 전략 대화
- **책임:**
  - 요청 분석 → 적합 워커 라우팅 (도메인 일치 우선)
  - Task tool 로 워커 dispatch (model 결정 = frontmatter / 동적 override / default sonnet)
  - 워커 보고 결재 (first-pass ≥ 70 승인 / 재작업 최대 2회)
  - **부재 워커 자동 채용** — HR Lead 를 Task tool 로 호출 + 사용자 알림 1줄 (차단 X)
  - Reflection 자동 박제 (워커 보고의 후보 → reflection.record)
- **금지:** 워커 → 워커 chain, PRD/분기 회고 자동 생성, persona evolution narrative, CPO/HR 외 임원 자동 추가

### 인사팀장 (HR Lead)

- **호출 모델:**
  - CPO 의 Task tool 호출 → 자동 채용 진행 (ADR-0004 §3)
  - `/lskun-kit:work hr-lead "..."` 사용자 명시 호출 → 해고 / 평가
- **책임:** 채용 (중복 감지 후 신규 또는 기존 추천), 해고 (archived/ 이동, 사용자 명시 요청만), 평가 (사용자 명시 요청만)
- **금지:** 사용자 미요청 정기 평가, 다른 워커 작업 결과 검수 (결재는 CPO 단독)
- **default model:** `sonnet` (단순 박제·archive 작업)

---

## 10. 작업 규칙

- **커밋:** Conventional Commits (`feat:` / `fix:` / `refactor:` / `docs:` / `test:` / `chore:`)
- **PR:** ≤ 1 feature, ≤ 500 lines
- **언어:** 코드 식별자는 영어, 주석/문서/커밋 메시지는 한국어 허용
- **SRP** 준수
- **금지:** `.env` 편집 / prod config 변경 / 코드 내 secrets / 옛 자산 복붙
- **결정 변경:** ADR-0001 의 §1 정체성, §3 핵심 메커니즘, §4 Storage 추상화, §5 SSOT 분리, §6 Zero-Base, §7 폐기 목록 및 ADR-0002 / ADR-0003 / ADR-0004 의 결정 사항을 변경하려면 새 ADR 박제 필요. CLAUDE.md 만 고치지 말 것.
