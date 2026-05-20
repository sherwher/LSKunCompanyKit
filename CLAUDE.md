# LSKunCompanyKit — Claude Code Instructions

> 본 문서는 LSKunCompanyKit 저장소에서 Claude Code 가 따라야 할 프로젝트 헌법.
> 상위 결정문:
> - [ADR-0001](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0001-2026-05-15-stateful-workers-clean-slate.md) — 창설
> - [ADR-0002](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0002-2026-05-18-cpo-hr-pivot.md) — CPO/HR pivot (Phase 2 진입)
> - [ADR-0003](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0003-2026-05-18-domain-aware-workers.md) — 도메인 인지 워커 (`role × domain`)
> - [ADR-0004](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0004-2026-05-18-leader-worker-pivot.md) — **메인 세션 = CPO (Leader-Worker, 자동 채용)**
> - [ADR-0005](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0005-2026-05-18-schema-migration.md) — Schema 마이그레이션 (`/lskun-kit:migrate-schema`)
> - [ADR-0006](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0006-2026-05-18-cpo-decision-audit.md) — CPO 결재 audit log (`.audit/decisions.jsonl`)
> - ~~[ADR-0007](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0007-2026-05-19-ssot-3axis-and-project-link.md)~~ — SSOT 3축 + `.claude/lskun-kit.json` (**superseded by ADR-0008**)
> - [ADR-0008](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0008-2026-05-19-local-first-no-link.md) — Local-first, vault optional, link 미도입 (ADR-0007 폐기, ADR-0001 §4 + ADR-0004 §1 유지)
> - [ADR-0009](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0009-2026-05-19-self-contained-default.md) — **Self-contained default** + 외부 통합은 명시 opt-in. "future: Notion" 약속 폐기. plugin core 는 외부 SDK / API 미보유
> - [ADR-0010](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0010-2026-05-19-persona-sync-and-provenance.md) — Persona sync (`/lskun-kit:sync-persona`) + provenance + 조직도 view (`/lskun-kit:org`)
> - [ADR-0011](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0011-2026-05-20-jd-based-hiring.md) — **JD 기반 채용 + 정체성 보강** (persona body 의 JD inline + 자산 누적 2 차원)
> - [ADR-0012](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0012-2026-05-20-single-source-version.md) — Plugin version single-source SSOT (`plugin.json` 단일 진실원)
> - [ADR-0013](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0013-2026-05-20-stable-org-and-reflection-step.md) — **조직도 stable markdown table + CPO 결재 절차에 reflection 박제 강제** (워커 history dead code 화 결함 해결)
>
> Plugin 개발자 SSOT 의 물리적 위치는 저자별로 다르다 (ADR-0009 §5). 본 plugin 문서는 저자 개인 SSOT 경로를 박제하지 않는다.

---

## 1. 프로젝트 정체성

- **이름:** LSKunCompanyKit
- **종류:** Claude Code plugin
- **버전:** `.claude-plugin/plugin.json` 의 `version` 필드가 단일 진실원 (ADR-0012). 현재 Phase 12 — P72 ADR-0013 조직도 stable format + reflection 박제 강제
- **GitHub:** `github.com/sherwher/LSKunCompanyKit`
- **Plugin manifest name:** `LSKunCompanyKit`
- **Slash command namespace:** `/lskun-kit:*` (다른 prefix 사용 금지)
- **라이선스:** MIT

### 한 줄 정체성 (ADR-0011 갱신)

> "Claude Code 의 메인 세션 자체가 회사의 CPO 로 동작하여, 사용자 요청마다 최적 전문가를 매칭·dispatch 한다.
> 채용 시 HR Lead 가 작성한 JD (persona body) 와 작업 이력 (reflection history) 이 회사 자산으로 누적된다.
> 사용자 요청 → CPO 라우팅 → 워커 dispatch → 결재 → 응답. 부재 워커는 JD 기반 자동 채용.
> 저장 위치는 사용자 선택, 마이그레이션은 LSKunCompanyKit 책임."

자산은 두 차원으로 정의된다 (ADR-0011 §6):
- **정적 자산 = persona body (JD inline)** — 채용 시점 1회 박제, 자동 갱신 금지
- **동적 자산 = reflection history** — 매 작업 종료 시 1줄 append (ADR-0001 §3)

### Slash commands (현재)

| 명령 | 역할 |
|---|---|
| `/lskun-kit:init` | 신규 회사 셋업 + CPO/HR 자동 hire |
| `/lskun-kit:hire` | 신규 워커 박제 (primitive) |
| `/lskun-kit:work` | 워커 호출. 이름 생략 시 CPO 가 라우팅 |
| `/lskun-kit:reflect` | 작업 종료 1줄 기록 (수동) |
| `/lskun-kit:migrate` | Local ↔ Vault 무결성 이동 |
| `/lskun-kit:migrate-schema` | 기존 회사 frontmatter 를 현재 schema 로 보강 |
| `/lskun-kit:sync-persona` | CPO/HR Lead persona body 를 plugin 최신 template 와 sync |
| `/lskun-kit:org` | 회사 조직도 read-only view |
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
       Local (default, self-contained) | Vault (Optional Integration)
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

## 6. 절대 만들지 말 것 (ADR-0001 §7 + ADR-0002 §6 + ADR-0004 §8 + ADR-0006 §"폐기/금지" + ADR-0008 §"폐기/금지" + ADR-0009 §"폐기/금지" 누적)

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
- **audit log 위에 자동 분석 / 대시보드 / KPI / 통계 시각화** — ADR-0006 + ADR-0002 §5 위반
- **audit log 기반 워커 자동 평가·해고** — HR Lead 사용자 명시 호출 원칙 위반 (ADR-0006)
- **분기 / 월간 audit 자동 회고 보고서** — persona evolution narrative 금지와 동일 결 (ADR-0006)
- **결재 위원회 / 다단계 승인 / 부 결재자** — ADR-0004 §8 + ADR-0006 위반
- **audit log 외부 자동 전송** — 사용자 명시 동의 없는 외부 전송 금지 (ADR-0006)
- **`.claude/lskun-kit.json` 등 프로젝트→회사 link 파일** — ADR-0007 실패 패턴. multi-project 단일 회사 케이스가 **실증된 후** 에만 새 ADR 박제 가능 (ADR-0008)
- **CLAUDE.md marker 의 "캐시" 강등** — marker = 진실원 (ADR-0004 §1). drift 발생 시 자동 갱신 X, 사용자 알림만 (ADR-0008)
- **SSOT 3축 모델** — 2축 (개발자 / 사용자 회사) 으로 충분. 사용자 프로젝트는 작업 위치이며 별도 SSOT 아님 (ADR-0008)
- **vault default 격상** — Local 과 Vault 동등. vault 강제 금지 (ADR-0008)
- **"future: Notion" 등 외부 통합 promise** — plugin 본 repo 어디서도 박제 금지. 실제 도입 시점에 별도 ADR + add-on package (ADR-0009)
- **plugin core 안에서 외부 시스템 (Obsidian, Notion 등) SDK / API 호출** — 영원히 금지. 외부 통합은 별도 add-on 책임 (ADR-0009)
- **plugin 본 문서에 사용자 vault 절대경로·외부 도구 컨벤션 박제** — 추상 placeholder (`<your-vault>/`, `<your-project>/`) 만 허용 (ADR-0009)
- **JD 자동 정기 갱신** — 채용 시점 1회 inline 박제. 사용자 미요청 자동 갱신 금지 (ADR-0011 §"폐기/금지")
- **별도 JD 파일** (`jd/<name>.md` 등) — JD 는 워커 body inline 만 (ADR-0011)
- **plugin core 의 JD schema 박제** — `body_override` 는 단순 string passthrough. dataclass / 검증 / 도메인 사전 도입 금지 (ADR-0011 + ADR-0009)
- **role 미세 분화 우회** — JD 가 정교해진다고 `backend-engineer-payment` 같은 role 분할 채용 금지. rate-limit 단위 `role × domain` 유지 (ADR-0011)
- **JD 외부 전송** — JD 가 외부 시스템 (Notion / Slack 등) 으로 자동 전송 금지 (ADR-0011 + ADR-0009)
- **"고밀도 워크포스" / "최대한 밀도" / "AI 직원 진화" 등 슬로건성 narrative** — CLAUDE.md / README / ADR / persona template 어디에도 박지 않음 (ADR-0011)
- **JD 측정 지표** — "밀도" / "Context Coverage Rate" / "First-pass Approval Rate" 등 KPI 자동 산출 금지 (ADR-0011 + ADR-0002 §5)
- **`org.render()` 의 컬럼 폭 동적 계산 재도입** — markdown table 단일 SSOT. ASCII 정렬 미려함 추구로 동적 padding 복귀 금지 (ADR-0013)
- **조직도 출력에 한글 폭 보정 (`east_asian_width`) 도입** — markdown table 로 회피한 의도 위반. 다른 format 필요 시 별도 ADR (ADR-0013)
- **CPO 결재 절차의 reflection 박제 단계 생략** — 1건 dispatch = 1 `reflection.record()`. 일괄 / batch / 비동기 / "나중에" 금지 (ADR-0013)
- **워커가 자기 reflection 을 직접 박제하는 경로** — reflection 박제는 CPO 결재 절차의 일부, 워커 → 워커 chain 금지와 동일 결 (ADR-0004 §8 + ADR-0013)
- **새 hook (PostToolUse / SubagentStop 등) 으로 자동 reflection 박제 시도** — Claude Code hook spec 의존 자동 박제는 silent failure 누적 위험. 절차 박제 + 기존 `reflection.record()` 로 충분 (ADR-0013)

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
│   ├── plugin.json           # version SSOT (ADR-0012)
│   └── marketplace.json      # version 필드 없음 — plugin.json 으로 fallback
├── hooks/
│   └── hooks.json            # SessionStart hook 등록 (P24)
├── commands/                  # 6개 slash command
│   ├── init.md               # /lskun-kit:init
│   ├── doctor.md             # /lskun-kit:doctor          (16개 진단 항목)
│   ├── hire.md               # /lskun-kit:hire            (--domain --model)
│   ├── work.md               # /lskun-kit:work            (메인 세션 = CPO, --model)
│   ├── reflect.md            # /lskun-kit:reflect
│   ├── migrate.md            # /lskun-kit:migrate         (Local ↔ Vault)
│   ├── migrate-schema.md     # /lskun-kit:migrate-schema
│   ├── sync-persona.md       # /lskun-kit:sync-persona    (cpo/hr-lead body sync)
│   └── org.md                # /lskun-kit:org             (조직도 read-only)
├── src/lskun_kit/             # Python core (stdlib only, 0 외부 의존성)
│   ├── adapters/             # StorageAdapter ABC, MarkdownTreeAdapter, Local, Vault, frontmatter
│   ├── hooks/                # stop_reflect (P6) + session_start (P24)
│   ├── templates/            # CPO / HR persona markdown — P25 본문 (Leader-Worker dispatch)
│   ├── models.py             # Worker / HistoryEntry / Company + REQUIRED_WORKER_FIELDS (6) + MODEL_ALIASES
│   ├── errors.py             # LSKunKitError 계층
│   ├── session.py            # 활성 워커 1명 프로세스 간 공유
│   ├── context.py            # build_worker_context (history 컨텍스트 주입)
│   ├── reflection.py         # record (history 1줄 append)
│   ├── audit.py              # CPO 결재 audit log — AuditEntry/record/new_request_id
│   ├── persona_sync.py       # 메타 워커 body sync — plan/execute (cpo, hr-lead)
│   ├── org.py                # 조직도 read-only view — OrgReport.render()
│   ├── migration.py          # plan / execute (Local ↔ Vault)
│   ├── schema_migration.py   # v0.2/v0.3 → v0.4 frontmatter 보강 (P50/ADR-0005)
│   ├── hire_audit.py         # HR Lead 자동 채용 rate-limit + audit log
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

### Phase 10 (P70 — JD 기반 채용 + 정체성 보강)

```
P70 ✅ ADR-0011 박제. CLAUDE.md §1 정체성 한 줄 갱신 (JD persona body +
       reflection history 2차원 자산). render_default_worker 에 body_override
       string passthrough 인자 추가 (기존 호출자 0 변경). HR Lead persona
       채용 알고리즘 6단계 → 7단계 (4.5 JD body 작성). 핵심 책임에
       "keywords 일괄 보강" (#6) / "역량 갱신" (#7) 추가. CLAUDE.md §6
       금지 목록에 JD 관련 7개 항목 박제 (자동 갱신 / 별도 파일 / schema /
       role 미세 분화 / 외부 전송 / 슬로건 / KPI). 측정 지표 비도입.
       4 에이전트 검토 합의 (architect / critic / analyst / planner).
       기존 회사 / 기존 워커 0 변경.
```

### Phase 9 (P69 — 라우팅 정확도 보강)

```
P69 ✅ workers frontmatter 에 optional `keywords` (콤마 구분 string) 도입.
       routing.py 가 후보 1줄에 keywords raw 노출 + user_request fence 처리
       (markdown injection 가드). cpo.md Routing Heuristics 를 자연어 4줄
       → 결정 절차 5단계 (의도 파악 → keywords/domain 매칭으로 상위 3명 압축
       → history tie-break → 동률 시 사용자 1줄 확인 → 부재 시 자동 채용)
       로 재작성. hr-lead.md 채용 절차에 keywords 1줄 제안 (optional, ceremony 0).
       plugin core 는 매칭/정렬을 하지 않음 — CPO LLM 이 매 호출 시 직접 수행
       (ADR-0009 self-contained 유지). 회사별 lookup table 0. 기존 회사 0
       변경으로 동작 (optional 필드). plugin 업데이트는 회사별 `/sync-persona`
       1회로 전파.
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
