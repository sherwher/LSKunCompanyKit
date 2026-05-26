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
> - [ADR-0013](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0013-2026-05-20-stable-org-and-reflection-step.md) — ~~조직도 stable markdown table + CPO 결재 절차에 reflection 박제 강제~~ — **부분 supersede by ADR-0014** (조직도 stable table 부분 유지, reflection 박제 강제는 폐기)
> - [ADR-0014](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0014-2026-05-22-reflection-removal-and-jd-driven-identity.md) — **Reflection 메커니즘 완전 폐기 + JD-driven 정체성 박제** (4 전문가 5차 만장일치). 워커 = 채용 시 완성형, 시간 흐름으로 진화하지 않음. 자산 = JD only (정적 단일 차원). ADR-0001 §3, ADR-0011 §6 supersede. ~1,528 LoC + ~80 tests 제거 예정 (P79)
> - [ADR-0015](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0015-2026-05-22-multi-project-company-sharing.md) — **Local SSOT 단일화 (`~/.lskun-companies/<name>/`) + `/init` 멱등성 + Vault Mirror 분리 + 권한 자동 박제 + 워커 해고 결합 해제 (결정 7 머지)**. ADR-0008 supersede (Local/Vault 동등 → Local 단일 SSOT). Phase 15 (P83~P93) 코드 변경 예정. 결정 7 = JD/display_name 분리, archived display_name 재사용 금지, audit log dangling cross-check
> - [ADR-0016](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0016-2026-05-26-omc-fallback-block.md) — ~~**메인 세션 측 OMC fallback 차단 (호출자 측 enforcement)**~~ — **supersede by ADR-0017** (denylist → allowlist 정책 전환). 메커니즘은 계승 (PreToolUse:Task hook), 정책만 갱신. ADR-0016 의 escape hatch (`LSKUN_ALLOW_OMC_FALLBACK=1`) 은 별칭으로 영구 유지. v0.20.0
> - [ADR-0017](../../obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0017-2026-05-26-dispatch-subagent-allowlist.md) — **Dispatch subagent_type Allowlist (정식 dispatch = `claude` 단일)** (사용자 단독 결재). 4회째 OMC fallback 재발 (LSKun 본진, 2026-05-26) 시정. PreToolUse:Task hook 의 denylist → allowlist 반전 (`_ALLOWED_SUBAGENT = {"claude"}`). 차단 범위 확장 (OMC + general-purpose + 외부 plugin subagent vercel/codex/figma 등 + Explore/Plan). Skill 문서 + cpo/hr-lead persona template 에 `subagent_type="claude"` 강제 박제 (4회 재발의 근본 원인 = Skill 문서 미규정 시정). escape hatch 2개 (`LSKUN_ALLOW_NON_CLAUDE_DISPATCH` 신규 정식 + ADR-0016 별칭 영구 유지). doctor [22] [23] 신규. 25 tests (기존 7 + 갱신 10 + 신규 8) 통과, 전체 251 회귀 0. v0.21.0
>
> Plugin 개발자 SSOT 의 물리적 위치는 저자별로 다르다 (ADR-0009 §5). 본 plugin 문서는 저자 개인 SSOT 경로를 박제하지 않는다.

---

## 1. 프로젝트 정체성

- **이름:** LSKunCompanyKit
- **종류:** Claude Code plugin
- **버전:** `.claude-plugin/plugin.json` 의 `version` 필드가 단일 진실원 (ADR-0012). 현재 Phase 17 (0.21.0) — Dispatch subagent_type Allowlist 정책 전환 (ADR-0017, ADR-0016 supersede). PreToolUse:Task hook 의 denylist → allowlist 반전 (`claude` 단일 허용), Skill 문서·persona template 에 `subagent_type="claude"` 강제 박제, escape hatch 2개 (`LSKUN_ALLOW_NON_CLAUDE_DISPATCH` 신규 + `LSKUN_ALLOW_OMC_FALLBACK` 별칭), doctor [22][23] 신규
- **GitHub:** `github.com/sherwher/LSKunCompanyKit`
- **Plugin manifest name:** `LSKunCompanyKit`
- **Slash command namespace:** `/lskun-kit:*` (다른 prefix 사용 금지)
- **라이선스:** MIT

### 한 줄 정체성 (ADR-0014 갱신, 2026-05-22)

> "Claude Code 의 메인 세션 자체가 회사의 CPO 로 동작하여, 사용자 요청마다 도메인 적합 전문가를 매칭·dispatch 한다.
> 워커는 채용 시점에 HR Lead 가 작성한 JD (도메인 날리지 + 전문성) 로 **완성형** 이며, 시간 흐름으로 진화하지 않는다.
> 회사 성장 = 인원 추가 + 도메인 확장. 부재 워커는 JD 기반 자동 채용.
> 저장 위치는 사용자 선택, 마이그레이션은 LSKunCompanyKit 책임."

자산은 **JD only, 정적 단일 차원** (ADR-0014):
- **정적 자산 = persona body (JD inline)** — 채용 시점 1회 박제, 사용자 명시 갱신 외 자동 진화 금지
- ~~동적 자산 = reflection history~~ — **ADR-0014 로 폐기**. "워커가 시간으로 성장한다" 모델 부정

**Stateful Workers 의 재해석**: state = JD (time-invariant). 채용 = 완성형 전문가 박제. 시간 흐름과 무관.

### Slash commands (현재)

| 명령 | 역할 |
|---|---|
| `/lskun-kit:init` | 신규 회사 셋업 + CPO/HR 자동 hire |
| `/lskun-kit:hire` | 신규 워커 박제 (primitive) |
| `/lskun-kit:work` | 워커 호출. 이름 생략 시 CPO 가 라우팅 (ADR-0015 7-E archived 가드) |
| `/lskun-kit:sync-in` | ADR-0015 — 외부 mirror → `~/.lskun-companies/<name>/` (백업 자동) |
| `/lskun-kit:sync-out` | ADR-0015 — `~/.lskun-companies/<name>/` → 외부 mirror (백업 자동) |
| `/lskun-kit:migrate-schema` | 기존 회사 frontmatter 를 현재 schema 로 보강 |
| `/lskun-kit:sync-persona` | CPO/HR Lead persona body 를 plugin 최신 template 와 sync |
| `/lskun-kit:org` | 회사 조직도 read-only view |
| `/lskun-kit:doctor` | 환경 진단 (23개 항목, ADR-0015 7-C/7-D + ADR-0016 [20][21] + ADR-0017 [22][23]) |

---

## 2. 핵심 메커니즘 — 2개 (ADR-0004 + ADR-0003, ADR-0014 갱신)

### 2.1 ~~Reflection~~ — **ADR-0014 로 폐기 (2026-05-22)**

옛 메커니즘: 작업 종료 hook → 워커 markdown 의 `## Project History` 1줄 append → 다음 dispatch context 주입.

폐기 사유 (4 전문가 5차 만장일치):
- 6일 실측: 41명 중 8명만 박제 (누락률 80.5%)
- 박힌 8건 모두 80자 가드 우회 (100~1400자 narrative)
- score 필드 의사결정 미사용 (architect 코드 검증)
- 평가 자산 4 조건 모두 미충족 (analyst 정량)
- 사용자 정체성 박제: "역사를 주입해서 커가는 것이 아니다"

P79 에서 코드 제거 (~1,528 LoC + ~80 tests). 기존 사용자 자산 (LSKun 8명 박힌 narrative) 은 `## Archived History (pre-0.18)` 로 rename, read-only 보존.

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

같은 `role` 이라도 회사 `domain` 별로 JD (persona body) 가 분리 → 채용 시점에 도메인 지식 (예: HIPAA PHI 마스킹, HL7 FHIR 함정) 이 JD 본문에 박제. CPO 라우팅 0순위 = 도메인 일치. 사전 enum 강제 X (자유 입력). ADR-0014 재해석 — "domain 별 history 분리" → "domain 별 JD 분리".

---

## 3. Storage Backend 추상화 (ADR-0015 — Local 단일 backend)

```
LSKunCompanyKit core (interface 만 알고 구현은 모름)
   └── StorageAdapter
         read_worker(name), list_workers(), read_company()
         create_worker / archive_worker(name, archived_at, archived_reason)
         append_audit (default NotImplementedError)
              ↓
       Local (단일 backend, ~/.lskun-companies/<name>/)
              ↕ (사용자 명시 sync 명령만)
       외부 mirror (vault / Obsidian / Notion local / 외장 디스크)
```

ADR-0015 (2026-05-22) — Vault backend 폐기. plugin core 는 `~/.lskun-companies/<name>/` 단일 위치만 참조. 외부 mirror 통합은 `shutil.copytree` 만 사용하는 sync 명령으로:

| 명령 | 방향 | 백업 위치 |
|---|---|---|
| `/lskun-kit:sync-in <name> <source>` | 외부 mirror → Local SSOT | `~/.lskun-companies/.backups/<name>/<YYYYMMDD-HHMMSS>/` |
| `/lskun-kit:sync-out <name> <target>` | Local SSOT → 외부 mirror | `<target>.lskun-backup-<YYYYMMDD-HHMMSS>/` (target 측 sibling) |

권한 박제 (결정 4): `/init` 신규 회사 창설 시 `~/.claude/settings.json` 의 `permissions.allow` 에 5개 패턴 자동 추가 (사용자 confirm 1회).

---

## 4. SSOT 분리 정책 (강제, ADR-0015)

| 영역 | 위치 | 내용 |
|---|---|---|
| **개발자 SSOT** | `02_Projects/LSKunCompanyKit/` (저자별 별도 위치) | ADR / Phase 계획 / interface 설계 |
| **사용자 SSOT** (단일) | `~/.lskun-companies/<name>/` | hired/ / archived/ / company.md / .audit/ |
| 외부 mirror (선택) | 사용자 임의 경로 | sync 명령으로만 동기화. plugin core 는 path 만 알고 SDK 0 |

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

**컨셉만 승계 (ADR-0014 갱신):** JD-driven Workers (time-invariant state) + Storage Abstraction + SSOT 분리. ~~Reflection~~ — ADR-0014 (2026-05-22) 로 폐기.

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
- ~~CPO 결재 절차의 reflection 박제 단계 생략~~ — **ADR-0014 로 폐기** (reflection 메커니즘 자체 폐기)
- ~~워커가 자기 reflection 을 직접 박제하는 경로~~ — **ADR-0014 로 자연 폐기** (reflection 대상 자체 소멸). 워커 → 워커 chain 금지는 유지 (ADR-0004 §8)
- ~~새 hook 으로 자동 reflection 박제 시도~~ — **ADR-0014 로 자연 폐기**. Stop / PostToolUse hook 도 제거됨 (P79-1).
- **reflection / history 메커니즘 재도입** — ADR-0014 로 폐기. 재도입 시 새 ADR + 정체성 재정의 선행 필수
- **워커 진화 narrative** (ADR-0014) — "워커가 시간으로 성장한다" 류 슬로건 박제 금지. ADR-0011 의 "AI 직원 진화" 슬로건 금지와 일관
- **JD 자동 갱신** (ADR-0014) — JD 는 채용 시 1회 박제. 사용자 명시 갱신 (`/lskun-kit:work hr-lead "..."`) 외 자동 진화 금지
- **해고 시 archived 의 frontmatter display_name 자동 익명화 / rewrite** (ADR-0015 결정 7-B) — 역사 자산 불변
- **archived 의 옛 display_name 재사용** (ADR-0015 결정 7-C) — 같은 role 재채용 시 옛 이름 재사용 금지, 혼선 방지
- **audit log (`.audit/decisions.jsonl`) 의 archived 워커 이름 rewrite** (ADR-0015 결정 7-D) — ADR-0006 정신, 역사 기록 불변
- **CPO 라우팅 / SessionStart hook 의 archived 워커 노출** (ADR-0015 결정 7-B/7-E) — hired/ 만 스캔, archived/ 무시
- **`<project>/.company/` 의 모든 형태** (ADR-0015 결정 1-A) — SSOT, cache, mirror 무엇으로도 도입 금지. Local SSOT 는 `~/.lskun-companies/<name>/` 단일 위치
- **`$LSKUN_VAULT` env var 의 plugin core 참조** (ADR-0015 결정 1-A) — sync 명령의 `--target` / `--source` 인자로만 사용
- **`adapters/vault.py` 재도입** (ADR-0015 결정 1-B) — plugin core 가 vault 직접 참조 금지, 파일시스템 복사 sync 만
- **`/found` `/join` `/status` 신규 명령 / `.claude/lskun-link.json`** (ADR-0015 결정 2-A) — `/init` 멱등성으로 충분
- **Skill 실패 시 Task tool 우회** (ADR-0015 결정 3-A) — LLM 의 학습 패턴 차단, 에러 보고 후 중단
- **메모리·CLAUDE.md text instruction 만으로 OMC fallback 차단 재시도** (ADR-0016) — 3회 실패 입증. hook 차단 필수. 신규 차단 경로 추가도 hook 레벨에서
- **Agent 툴의 `subagent_type` 에 `LSKunCompanyKit:work` 추가 시도** (ADR-0016) — Skill 진입이지 subagent 아님. plugin 아키텍처 위반
- **PreToolUse hook 에서 `tool_input` 의 prompt/description 내용 파싱하여 의도 추론** (ADR-0016) — `subagent_type` 문자열 매칭만 허용. prompt 내용 기반 의도 판별은 brittle + false positive 원천
- **`LSKUN_ALLOW_OMC_FALLBACK=1` 의 `.zshrc` / `.bashrc` 영구 export** (ADR-0016 결정 5) — 가드 무력화. 세션 단위 export 권장. doctor [21] 가 검출 + 경고
- **PreToolUse:Skill 가드 추가로 사용자 명시 슬래시 `/oh-my-claudecode:*` 까지 차단** (ADR-0016) — 사용자 의도 무시. 본 ADR 범위는 메인 LLM 의 자의적 Agent → OMC 호출만
- **Denylist 모델 재도입** (ADR-0017) — 4회째 재발 입증. allowlist 단일 정책 유지. 재도입 시 새 ADR + 5회째 재발 증거 필수
- **Skill 문서·persona template 의 dispatch `subagent_type` 미규정** (ADR-0017) — `commands/work.md` / `templates/cpo.md` / `templates/hr-lead.md` 모두 `subagent_type="claude"` 명시 박제 필수. 누락 시 LLM 자의 선택 → ADR-0017 위반
- **`subagent_type="claude"` 외 dispatch 의 silent 통과** (ADR-0017) — 반드시 stderr 안내 + escape hatch 경로 명시
- **plugin 개발자 dogfood 시나리오를 위한 cwd-aware 가드 추가** (ADR-0017) — false positive 우려. escape hatch 1회 set 으로 처리
- **`LSKUN_ALLOW_NON_CLAUDE_DISPATCH=1` / `LSKUN_ALLOW_OMC_FALLBACK=1` 의 `.zshrc` / `.bashrc` 영구 export** (ADR-0017 결정 8) — allowlist 가드 무력화. 세션 단위 export 권장. doctor [23] 가 검출

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
- 단, **history entry 보존 / frontmatter 덮어쓰기 금지 / 백업 강제** 가드는 불변 (ADR-0014 — heading 만 archived 로 rename 가능, entry 불변)

---

## 7. 디렉토리 구조 (현재, ADR-0015 갱신)

```
LSKunCompanyKit/
├── .claude-plugin/
│   ├── plugin.json           # version SSOT (ADR-0012) — 0.21.0
│   └── marketplace.json      # version 필드 없음 — plugin.json 으로 fallback
├── hooks/
│   └── hooks.json            # SessionStart + PreToolUse:Task (ADR-0014 — Stop/PostToolUse 제거. ADR-0016 — denylist (supersede). ADR-0017 — Allowlist 정책 전환)
├── commands/                  # 9개 slash command (ADR-0015 — /migrate 제거, /sync-in /sync-out 신규)
│   ├── init.md               # /lskun-kit:init             (ADR-0015 멱등성 4행)
│   ├── doctor.md             # /lskun-kit:doctor           (19개 진단 항목 — 7C/7D 추가)
│   ├── hire.md               # /lskun-kit:hire             (--domain --model)
│   ├── work.md               # /lskun-kit:work             (메인 세션 = CPO, --model, 7-E 가드)
│   ├── sync_in.md            # /lskun-kit:sync-in          (ADR-0015 — 외부 mirror → Local SSOT)
│   ├── sync_out.md           # /lskun-kit:sync-out         (ADR-0015 — Local SSOT → 외부 mirror)
│   ├── migrate-schema.md     # /lskun-kit:migrate-schema   (ADR-0014 — legacy history rename)
│   ├── sync-persona.md       # /lskun-kit:sync-persona     (cpo/hr-lead body sync)
│   └── org.md                # /lskun-kit:org              (조직도 read-only)
├── src/lskun_kit/             # Python core (stdlib only, 0 외부 의존성)
│   ├── adapters/             # StorageAdapter ABC, MarkdownTreeAdapter, Local, frontmatter
│   │                         # (ADR-0015 — vault.py 폐기, archive_worker 시그니처 확장)
│   ├── hooks/                # session_start (CLAUDE.md marker 기반) + pre_tool_use (chain 차단)
│   ├── templates/            # CPO / HR persona markdown (ADR-0014 + ADR-0015 갱신)
│   ├── models.py             # Worker / Company + REQUIRED_WORKER_FIELDS (6) + MODEL_ALIASES
│   ├── errors.py             # LSKunKitError + ConfirmRequired + WorkerArchivedError (ADR-0015)
│   ├── paths.py              # ADR-0015 — ~/.lskun-companies/<name>/ 단일 진입점
│   ├── permissions.py        # ADR-0015 결정 4 — ~/.claude/settings.json 자동 박제
│   ├── sync.py               # ADR-0015 결정 5 — sync_in / sync_out (shutil.copytree)
│   ├── session.py            # 활성 워커 1명 프로세스 간 공유
│   ├── context.py            # build_worker_context (ADR-0014 — JD only)
│   ├── audit.py              # CPO 결재 audit log (ADR-0006)
│   ├── persona_sync.py       # 메타 워커 body sync — plan/execute (cpo, hr-lead)
│   ├── org.py                # 조직도 read-only view
│   ├── schema_migration.py   # frontmatter 보강 + legacy history rename (ADR-0005 + ADR-0014)
│   ├── hire_audit.py         # HR Lead 자동 채용 rate-limit + audit log
│   ├── init.py               # ADR-0015 멱등성 4행 + ConfirmRequired 패턴
│   ├── persona_injection.py  # CLAUDE.md marker 박제·교체·검출 + extract_company_name
│   ├── routing.py            # CPO 라우팅 + ADR-0015 결정 7-E archived 가드
│   └── cli_org.py            # /lskun-kit:org canonical entrypoint
├── tests/                     # stdlib unittest, 227 tests (ADR-0015 후 +12)
├── docs/                      # storage-adapter-spec, migration-spec
├── CLAUDE.md                 # 본 문서
├── LICENSE                   # MIT
└── README.md                 # P92 — Phase 15 갱신
```

**hired/ 같은 회사 운영 데이터는 본 repo 에 절대 작성 금지.**
사용자 SSOT (`~/.lskun-companies/<name>/`) 에만 존재해야 함 (ADR-0015 결정 1-A).

---

## 8. 로드맵

### Phase 15 (P83~P93 — Local SSOT 단일화 + Sync 분리 + 권한 박제 + 워커 해고 결합 해제, ADR-0015, 0.19.0)

```
P83 ✅ ADR-0015 박제 (4 전문가 만장일치 + 사용자 confirm)
P84 ✅ 기존 vault 사용자 마이그레이션 가이드 박제 (README §"사용 흐름 0)")
P85 ✅ adapters/vault.py + migration.py + tests 폐기 (commit 8b856e8, -938 LoC)
       — plugin core 의 vault 직접 참조 영구 차단
P86 ✅ paths.py 신규 + LocalAdapter.from_company_name (commit e143e24, +345 LoC)
       — ~/.lskun-companies/<name>/ 단일 진입점
       — 회사명 검증 (영문/숫자/_/-/. + 시작 영문/숫자, .backups 예약어)
P87+P88 ✅ init.py 멱등성 4행 + hook marker-based 통일 (commit d85a948, +685/-392 LoC)
       — ConfirmRequired 패턴 (옵션 B — plugin core 가 stdin 안 잡음)
       — CLAUDE.md marker 가 회사-프로젝트 결합의 단일 진실원
       — LSKUN_VAULT env / cwd .company/ 탐색 완전 폐기
P89 ✅ permissions.py 신규 (commit 587c6fa, +412 LoC)
       — ~/.claude/settings.json 의 permissions.allow 에 5개 패턴 자동 박제
       — atomic-ish write (.lskun-tmp → rename), 기존 항목 보존
P90 ✅ sync-in / sync-out 명령 + sync.py 신규 (commit a0a6d7f, +695 LoC)
       — shutil.copytree 만 사용, 외부 SDK 0
       — 백업 위치 분리 (sync-in: ~/.lskun-companies/.backups/, sync-out: target sibling)
P91 ✅ CPO templates 의 Skill 경유 강제 (commit 9537430, +32 LoC)
       — Task tool 의 oh-my-claudecode:* / general-purpose fallback 영구 금지
P93 ✅ 워커 해고 결합 해제 (commit e598097, +240 LoC)
       — WorkerArchivedError + archive_worker(archived_at, archived_reason)
       — routing.py 의 archived 가드 (결정 7-E)
       — doctor 진단 신규 2종 (display_name 중복, audit dangling)
       — display_name 결합 해제 박제 (역사 자산 불변)
P92 ✅ docs 일괄 갱신 + version 0.19.0 (본 phase)
```

핵심 결정: Plugin core 가 회사 자원의 물리적 위치를 결정하는 유일한 모듈 = `paths.py`. 1 회사 N 프로젝트 공유 가능. Vault 통합은 사용자 명시 sync 명령으로만. 폐기 9종 (결정 1-A / 1-B / 2-A / 3-A / 5 정책 / 6 / 7-B/7-C/7-D/7-E) 모두 박제됨.

215 → 227 tests (+12), 회귀 0.

### Phase 17 (P100~P105 — Dispatch subagent_type Allowlist, ADR-0017, 0.21.0)

```
P100 ✅ ADR-0017 박제 — 사용자 단독 결재 (4 전문가 만장일치 시뮬레이션, "정석으로 완벽하게 해결" 지시)
       — 4회째 재발 사실 박제 (LSKun 본진 세션, 2026-05-26)
       — 9 결정 + 인지된 잔존 위험 5건 + 2축 방어 권고
       — ADR-0016 supersede (메커니즘 계승, 정책 갱신: denylist → allowlist)
P101 ✅ pre_tool_use.py 구현 변경 (ADR-0017 결정 1, 2, 7)
       — _OMC_BLOCK_PREFIXES / _OMC_BLOCK_EXACT 제거
       — _ALLOWED_SUBAGENT = frozenset({"claude"}) 신설
       — escape hatch 2개 (LSKUN_ALLOW_NON_CLAUDE_DISPATCH 신규 + LSKUN_ALLOW_OMC_FALLBACK 별칭)
       — 평가 순서 7 → 8단계 (claude 정식 + fallthrough deny)
P102 ✅ tests/test_hooks_pre_tool_use.py 확장 (ADR-0017 결정 9)
       — 기존 7 + 갱신 10 (Explore/Plan/외부 plugin allow → deny) + 신규 8 = 25 케이스
       — 전체 회귀: 243 → 251 tests, 회귀 0
P103 ✅ Skill 문서 + persona template 박제 (ADR-0017 결정 4, 5)
       — commands/work.md §"메인 세션 CPO 라우팅" / §사양 / §"Python 진입점"
       — templates/cpo.md §"Task tool 로 워커 dispatch" + §"폐기·금지"
       — templates/hr-lead.md §채용
       — 모두 subagent_type="claude" 강제 + escape hatch 안내
P104 ✅ doctor [22] [23] 추가 (ADR-0017 결정 8)
       — [22] Dispatch allowlist 가드 활성 (_ALLOWED_SUBAGENT / ENV_ALLOW_NON_CLAUDE / ADR-0017 marker)
       — [23] LSKUN_ALLOW_NON_CLAUDE_DISPATCH / LSKUN_ALLOW_OMC_FALLBACK 영구 export 검출
       — 진단 항목 21 → 23
P105 ✅ docs + version bump 0.20.0 → 0.21.0 (본 phase)
       — plugin.json, CHANGELOG 0.21.0 항목, CLAUDE.md §1/§7/§8/§6 갱신
       — feedback_worker_dispatch_via_lskun_kit.md 메모리 정정 (denylist → allowlist)
```

핵심 결정: ADR-0016 의 denylist 한계가 4회째 재발로 입증. Allowlist 단호 전환으로 4회 패턴 종결. Skill 문서 미규정 = 4회 재발의 근본 원인 → 문서 박제로 정책 시정. Blast radius (외부 plugin subagent 함께 차단) 는 escape hatch 2개로 통제.

243 → 251 tests (+8 신규, 갱신 10 케이스 기대값 반전), 회귀 0.

### Phase 16 (P95~P99 — 메인 세션 측 OMC fallback 차단, ADR-0016, 0.20.0)

```
P95 ✅ ADR-0016 박제 (4 전문가 만장일치 보완 후 승인 — architect / critic / analyst / planner)
       — 3회째 재발 사실 박제 (technicianAPP 세션, 2026-05-26)
       — 9 결정 + 인지된 잔존 위험 5건 + 2축 방어 권고
P96 ✅ pre_tool_use.py 가드 분기 추가 (ADR-0016 결정 1, 2, 3, 4, 5, 7)
       — `_OMC_BLOCK_PREFIXES` (oh-my-claudecode:) + `_OMC_BLOCK_EXACT` (general-purpose)
       — `LSKUN_ALLOW_OMC_FALLBACK=1` escape hatch + stderr 경고
       — `LSKUN_HOOK_DEBUG_DUMP=1` 실측 모드 (구현 phase 첫 작업, 실측 후 unset)
       — marker 검출 2층 (env var O(1) / session_start 재사용 fallback)
       — 평가 순서 7단계 명문화 (chain 차단 > OMC 차단)
P97 ✅ tests/test_hooks_pre_tool_use.py 확장 (ADR-0016 결정 9)
       — 기존 7건 + 신규 10건 = 17 tests 통과
       — `_task_payload(subagent_type)` helper 신규
       — 와일드카드 매칭 / 외부 plugin 허용 / chain 우선순위 모두 검증
P98 ✅ doctor [20] [21] 추가 (ADR-0016 결정 8)
       — [20] OMC fallback 가드 활성 검증 (pre_tool_use.py 상수 + ADR-0016 주석 + 버전 ≥ 0.20.0)
       — [21] shell profile 의 LSKUN_ALLOW_OMC_FALLBACK 영구 export 검출
       — 진단 항목 17개 → 21개 (CLAUDE.md, doctor.md 헤더 갱신)
P99 ✅ docs + version bump 0.19.0 → 0.20.0 (본 phase)
       — plugin.json, CHANGELOG 0.20.0 항목, CLAUDE.md §1/§7/§8/§6 갱신
```

핵심 결정: ADR-0015 결정 3-A 의 plugin core 측 차단을 호출자 측으로 확장. 메인 LLM 의 자의적 Agent → OMC executor dispatch 가 hook 레벨에서 deterministic 차단. 메모리·text instruction 만으로 LLM 행동 강제하던 패턴 종결.

233 → 243 tests (+10), 회귀 0.

### Phase 14 (P78~P82 — Reflection 메커니즘 폐기, ADR-0014 박제)

```
P78 ✅ ADR-0014 박제 + CLAUDE.md/README/plugin.json/marketplace.json/hub 정체성 동기화
       (commit e8dcbde + 63c5c3e + 12c3c40)
P79 ✅ 코드 + tests 제거 (5 sub-commit, 274 → 215 tests, 순 -2316 LoC)
       - P79-1+2: reflection.py / audit_diagnostics.py / Stop hook / PostToolUse hook
                  / HistoryEntry / append_history ABC / context.py 재작성
       - P79-3:   routing.py history tie-break + org.py h=N 카운트
       - P79-4a:  templates/cpo.md + hr-lead.md 재작성 (JD-driven)
       - P79-4b:  commands + docs (work/sync-persona/doctor/migrate-schema/hire/org)
       - P79-5:   migrate-schema 의 legacy `## Project History` →
                  `## Archived History (pre-0.18)` rename + tests
P80 ✅ docs: CLAUDE.md §3/§5/§6/§7/§8 + README ADR 참조 표 갱신 (본 phase)
P81 ❌ Dogfooding 실측 — 폐기 (ADR-0002 §5 + ADR-0014 정책. analyst 4차 정량
       에서 "측정 시도 자체가 정책 위반" 명시. LSKun 사용자 자연 사용으로 위임)
P82 - version 0.18.0-dev → 0.18.0 + 8 commit push (사용자 confirm 게이트)
```

핵심 결정: 워커 = 채용 시 완성형 (time-invariant JD). 자산 = JD only (정적 단일 차원).
회사 성장 = 인원 추가 + 도메인 확장.

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

### Phase 13 (P77 — `/org` env var 의존 제거 + plugin install 단일성 진단)

```
P77 ✅ P74/P75 잔존 결함 (`$CLAUDE_PLUGIN_ROOT` 미주입 → canonical 1줄 실패
       → LLM 이 plugin install 경로 hardcode → 옛 버전 16개 누적 → 매번 다른
       버전 선택) 의 근본 해결.

       표면 증상: env 미주입 환경에서 `python3 "$CLAUDE_PLUGIN_ROOT/.../cli_org.py"`
       가 `python3 "/src/.../cli_org.py"` 로 빈 변수 expand → 파일 없음 → LLM
       이 fallback 으로 `~/.claude/plugins/cache/.../<version>/...` 을 매번
       다르게 hardcode (P74 의 hardcode 금지 박제로도 차단 실패).

       근본 원인: P75 의 self-bootstrap 은 `sys.path` 만 보정. **파일 경로 자체**
       를 못 찾으면 무용. canonical 1줄이 `$CLAUDE_PLUGIN_ROOT` env var 라는
       외부 계약에 의존하는데, Claude Code 가 활성 plugin 1개에만 env 를 set
       하는 환경 다수 (실측: CLAUDE_PLUGIN_DATA 가 다른 plugin 값으로 set).

       해결 (2축):
       1. commands/org.md canonical 1줄을 **셸 자체가 경로를 resolve** 하도록
          재박제. fallback chain 을 1줄에 inline:
          - `$CLAUDE_PLUGIN_ROOT/src/lskun_kit/cli_org.py` (env 주입 시)
          - `~/.claude/plugins/cache/LSKunCompanyKit/LSKunCompanyKit/*/src/.../cli_org.py`
            (sort -V tail -1 로 최신 자동 선택)
          - `<cwd>/src/lskun_kit/cli_org.py` (repo clone 직접 실행)
          LLM 이 매번 다른 path 를 hardcode 할 여지 0. `PYTHONPATH` / 버전
          hardcode / `python3 -m` 금지를 명시 박제.
       2. 옛 plugin install 디렉토리 15개 (`0.1.0-dev` ~ `0.15.0`) 즉시 정리.
          0.16.0 만 잔존 → sort -V tail -1 결과 안정화.

       진단 (doctor 17번):
       - `$CLAUDE_PLUGIN_ROOT` 주입 여부 (미주입은 정상, 정보성 ℹ️)
       - plugin install 디렉토리 개수 (0=❌, 1=✅, 2+=⚠️ "옛 버전 잔존")
       - canonical resolve chain 이 단일 파일에 도달하는지 시뮬레이션 검증
       - 16개 → 17개 항목으로 확장. backend 무관하게 항상 수행.

       검증: env 미주입 상태에서 canonical 1줄 실행 → fallback 으로
       `~/.claude/plugins/cache/.../0.16.0/.../cli_org.py` 자동 resolve →
       조직도 정상 출력. 274 tests 회귀 0건.

       제약:
       - 셸이 zsh / bash 가정 (`${VAR:-}` / `[ -f ]` / 명령치환). fish 미지원
         이나 Claude Code Bash tool 은 zsh 사용으로 무관
       - sort -V 는 macOS/Linux coreutils 가정. 동일 환경에서만 보장
```

### Phase 13 (P76 — reflection 입력 방식 재설계 + 강제 메커니즘, 4 에이전트 합의안)

```
P76 ✅ DcodeJob 세션 실측 사건 (CPO 가 4명 워커 dispatch 후 reflection 박제 4건
       모두 skip + 사용자 지적 후 사후 bulk 박제, 1줄당 200~530자 narrative)
       의 근본 해결. P0~P71 + P75 = 3회 반복된 dead code 화 패턴 종결.

       4 에이전트 (critic / architect / analyst / planner) 합의 + 사용자
       추천안 7개 박제:

       1. dispatch 단위 = Task tool 호출 1회 = history 1줄 (audit request_id 정합)
       2. cpo.md 결재 절차 §3/§4 순서 뒤집기 — reflection 박제가 사용자 결과
          전달의 *선행 조건*. "결과 후 작업 완료 인식 → §4 skip" 패턴 차단
       3. HistoryEntry 에 outcome (approved|rework|rejected) + request_id 필드 추가.
          h=N 카운트가 audit log 와 1:1 cross-check 가능해짐
       4. topic / pattern 길이 가드 (HISTORY_FIELD_MAX_LEN=80) + 줄바꿈 금지.
          530자 narrative 재발 방지
       5. reflection.record_from_report() 신규 API — 워커 보고 markdown 의
          ## reflection 후보 섹션을 plugin core 가 자동 파싱. CPO 가 entry 를
          직접 짜지 않음 → narrative 변질 원천 차단. 옛 record() 는 deprecated
          (사용자 정정 경로 /lskun-kit:reflect 용 하위호환)
       6. PostToolUse:Task hook 신규 — Task dispatch 직후 reminder 1줄 stdout
          주입. *자동 박제가 아닌* nudge (ADR-0013 §"자동 박제 금지" 와 구분).
          비활성화: LSKUN_SKIP_REFLECTION_REMINDER=1
       7. /lskun-kit:doctor 에 audit ↔ reflection cross-check 진단 항목 0번
          추가 — audit approved 인데 history 박제 누락된 request_id 검출.
          coverage % + 누락 목록 표시. 자동 복구 X

       신규 모듈: src/lskun_kit/audit_diagnostics.py, hooks/post_tool_use.py
       신규 테스트: tests/test_reflection_p76.py (15) + test_audit_diagnostics_p76.py (5)
       총 274 tests 통과 (기존 256 + 신규 18).

       제약:
       - record_from_report 가 보고 양식 ## reflection 후보 섹션을 못 찾으면
         ReportParseError. CPO 는 워커에게 양식 재작업을 지시해야 함
       - PostToolUse hook 은 "자동 박제 alert" 라 ADR-0013 §"자동 박제 금지" 와
         분리. 별도 ADR 박제 불필요 (architect 판단)
```

### Phase 12 (P75 — `/org` self-bootstrap + 필터/export, 4 에이전트 합의안)

```
P75 ✅ P74 잔존 결함 (PYTHONPATH 의존, 출력 길이) 근본 해결.
       사용자 제안 (`org-chart.md` 정적 인덱스 + h=N auto-increment) 을 4
       에이전트 (critic / architect / analyst / planner) 합의로 폐기:
       - SSOT 이중화 (워커 md frontmatter ↔ org-chart.md)
       - reflection.record() SRP 위반 + dual-write 비원자성
       - ADR-0009 self-contained 원칙 위반 위험
       - 41명 1인 운영 규모에 over-engineering

       합의안 (P75-1 ~ P75-4) 박제:
       - cli_org.py self-bootstrap: 파일 자기 위치 기반 sys.path 보정.
         PYTHONPATH / $CLAUDE_PLUGIN_ROOT env var 의존 0. 직접 실행 가능.
       - commands/org.md: `python3 "$CLAUDE_PLUGIN_ROOT/src/lskun_kit/cli_org.py"`
         1줄로 박제. PYTHONPATH 제거.
       - --domain DOM: prefix 매칭 필터 (예: --domain tech → tech-* 8명).
         출력 길이 제어 — 41명 전체 대신 도메인별 부분 조회.
       - --export PATH: stdout 대신 파일에 dump. Obsidian/GitHub 외부 렌더링.
         사용자 명시 실행, 자동 sync 아님.

       org.py 동적 산출 + ADR-0013 stable markdown table SSOT 유지.
       256 tests 통과.
```

### Phase 12 (P74 — `/org` compact 기본 + paste 변형 금지 박제)

```
P74 ✅ P73 후속. dogfooding 결과 두 가지 잔존 결함 박제:
       (1) LLM 이 commands/org.md 의 canonical 1줄을 무시하고 `PLUGIN_ROOT=...0.X.Y`
           로 버전 hardcode 한 옛 패턴 답습 → 실패 → 재시도
       (2) markdown table 출력을 LLM 이 직접 paste 옮겨 적는 단계에서 행 중복 재발생
       해결:
       - cli_org 의 기본 format 을 compact 1줄로 전환 (ADR-0013 stable table 은
         `--full` 명시 시만). 1줄 short 포맷은 paste 변형 내성 강함.
       - commands/org.md 에 "옛 patterns (PLUGIN_ROOT hardcode, heredoc, -c)"
         금지 명시 + "출력은 그대로, paste 변형 금지" 박제. 호출 → 출력 양쪽 가드.
       256 tests 통과.
```

### Phase 12 (P73 — `/org` canonical entrypoint + compact add-on)

```
P73 ✅ `/lskun-kit:org` 운영 개선. 신규 모듈 `src/lskun_kit/cli_org.py` 추가
       (canonical entrypoint `python3 -m lskun_kit.cli_org`). backend
       auto-detect 는 hooks/session_start 의 `_find_active_company_root` 와
       동일 규칙 (LSKUN_VAULT+COMPANY → cwd 상향 .company). commands/org.md
       를 "이 1줄만 실행" 으로 박제해 LLM 이 매번 다른 Python heredoc 을 짜는
       우회 차단 (두 번 호출 / 출력 paste 오류 재발 방지). `OrgReport.render()`
       에 `compact: bool = False` 인자 추가 — 기본은 ADR-0013 stable markdown
       table 그대로 유지 (SSOT 미파괴), `--compact` 시 1줄 포맷
       `[C/H/W] name (display) · role · domain · model · h=N` (role==name 시
       role 생략) 로 가독성 확보. 256 tests 통과.
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
