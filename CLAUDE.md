# LSKunCompanyKit — Claude Code Instructions

> 본 문서는 LSKunCompanyKit 저장소에서 Claude Code 가 따라야 할 프로젝트 헌법.
> 상위 결정문 전체 인덱스: [`docs/internals/adr-index.md`](docs/internals/adr-index.md)
> 본문 결정 인용은 ADR 번호 (ADR-NNNN) 만 사용. 저자 SSOT 물리적 위치는 박제하지 않음 (ADR-0009 §5).

---

## 1. 프로젝트 정체성

- **이름:** LSKunCompanyKit
- **종류:** Claude Code plugin
- **버전:** `.claude-plugin/plugin.json` 의 `version` 필드가 단일 진실원 (ADR-0012). 현재 Phase 28 (0.34.0) — Worker Agent: 도구 권한으로 쓰기 단일화·chain 금지 강제 (P129, ADR-0026). 버전별 변경 상세는 CHANGELOG 가 SSOT (본 필드에 이전 버전 서술을 누적하지 말 것 — CLAUDE.md 크기 가드, P109-C).
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
| `/lskun-kit:doctor` | 환경 진단 (36개 항목, 라벨 [1]~[38] 중 18·19 결번 — 라벨별 근거 ADR 은 `commands/doctor.md` 참조) |
| `/lskun-kit:external` | 프로젝트별 외주(레드팀·고객) 구성/청취/cancel (ADR-0021 + ADR-0022 자동 시퀀스) |

---

## 2. 핵심 메커니즘 — 2개 (ADR-0004 + ADR-0003, ADR-0014 갱신)

### 2.1 ~~Reflection~~ — **ADR-0014 로 폐기 (2026-05-22)**

옛 메커니즘 (작업 종료 hook → 워커 markdown 에 history append → 다음 dispatch 주입) 을 4 전문가 5차 만장일치로 폐기 — 실측 누락률 80.5%, score 미사용, 사용자 정체성 ("역사를 주입해서 커가는 것이 아니다"). P79 에서 코드 제거, 기존 자산은 `## Archived History (pre-0.18)` 로 read-only 보존. 상세 근거는 ADR-0014.

### 2.2 Leader–Worker, 메인 세션 = CPO (ADR-0004)

```
사용자
  ↓
메인 세션 = CPO persona (CLAUDE.md inline 박제 + SessionStart hook 으로 회사 컨텍스트)
  ↓ Delegation Gate (ADR-0025) — ①컨텍스트 보호 ②병렬 탐색 ③독립 검증 시에만 dispatch
  ├─ 미충족 (기본) → 빙의(embody): CPO 가 워커 JD 주입받아 직접 수행
  └─ 충족 → Task tool
       워커 (agent=LSKunCompanyKit:worker — 쓰기·하위 dispatch 도구 없음 (ADR-0026), model 상속, persona = hired/<name>.md)
         ↑ 보고 (작업 결과 + 산출물 원본 / 자가 평가, ADR-0014 + ADR-0024 + ADR-0025)
메인 세션 = CPO 가 산출물 확인 결재 → 사용자 응답
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

### 개발자 SSOT 위치 (본 저장소 저자 로컬 — 운영 메모)

> 본 절은 **이 저장소를 작업하는 저자(sherwher)의 로컬 환경 메모**다. plugin 배포물·코드는 본 경로를 박제하지 않는다 (ADR-0009 §5 — "저자 SSOT 물리적 위치 비박제" 불변). 다른 LSKun 프로젝트(ilsaek/ImageChecker/DcodeJob 등)의 vault 연동 규약과 동일 패턴.

- **vault 루트:** `/Users/sk.lee/Documents/private-workspaces/obsidian-vault/`
- **프로젝트 허브:** `02_Projects/LSKunCompanyKit/LSKunCompanyKit-hub.md` (개발자 SSOT 인덱스, `ssot_role: developer`)
- **ADR 본문 SSOT:** `02_Projects/LSKunCompanyKit/decisions/ADR-NNNN-<date>-<title>.md` (repo 는 ADR 번호 인용만, 본문은 vault)
- **링크 방향 단일:** vault → repo 경로 참조 OK. repo 는 vault 를 빌드/런타임 의존하지 않음. 본문 복사 금지(이중 SSOT 금지).

### 동기화 관행 (변경·결정 시)

repo 에서 **결정/변경(ADR-급)** 이 생기면 vault 에 동기화한다 — repo 는 코드·spec·plan, vault 는 ADR 본문 SSOT + hub:
1. ADR 본문을 vault `decisions/ADR-NNNN-<date>-<title>.md` 에 박제 (repo 의 spec/CHANGELOG/forbidden 을 근거로 기존 ADR 형식 따름).
2. `LSKunCompanyKit-hub.md` 의 `related_adr` frontmatter + `## 현재 상태` 갱신.
3. repo 의 `docs/internals/adr-index.md` 는 ADR 번호·상태만 (본문 비박제, ADR-0009 §5).

### 강제 규칙

- 두 SSOT 위치를 plugin 본체가 명시적으로 다른 path 로 처리한다.
- 개발자 SSOT 에 회사 운영 데이터 (hired/ 등) 쓰지 말 것.
- 사용자 SSOT 에 plugin 알고리즘 ADR 쓰지 말 것.
- 위 "개발자 SSOT 위치" 경로는 **운영 메모일 뿐 plugin core/배포물 코드에 hardcode 금지** (ADR-0009 §5).
- `/lskun-kit:doctor` 가 cross-contamination 을 검증한다.

---

## 5. Zero-Base 원칙

이전 ai-company / claude-company-kit 의 어떤 자산도 **승계 금지** — 옛 코드/scripts/templates/manifest/hooks/release.sh 는 0 승계·전부 새로 작성, git history 도 새 repo. 옛 GitHub repo (`claude-company-kit`) 는 방치 (archive 표시 안 함).

**컨셉만 승계 (ADR-0014 갱신):** JD-driven Workers (time-invariant state) + Storage Abstraction + SSOT 분리. ~~Reflection~~ — ADR-0014 (2026-05-22) 로 폐기.

---

## 6. 절대 만들지 말 것 (요약)

**핵심 금지 항목** (전체 누적 목록은 [`docs/internals/forbidden-history.md`](docs/internals/forbidden-history.md) 참조):

- persona evolution narrative (워커가 시간으로 자동 진화) — ADR-0014 폐기
- 워커 → 워커 chain (sub-leader 출현) — ADR-0004 §8, PreToolUse hook 차단
- CPO/HR 외 임원 자동 추가 — ADR-0002 §1~§2
- audit log 위 자동 평가·대시보드·KPI — ADR-0006
- archive 메커니즘 재도입 — ADR-0019 (2026-05-27 폐기)
- 외부 harness (cmux/ralph/ultrawork) plugin core 도입 — ADR-0009 self-contained
- plugin 제공 agent (`LSKunCompanyKit:worker` / `:hr-lead`) 외 dispatch, dispatch 워커에 쓰기 가능 agent 부여 — ADR-0017 + ADR-0026
- plugin core 안에서 외부 시스템 SDK / API 호출 — ADR-0009
- skill marketplace/원격 다운로드 (네트워크 접촉) — ADR-0020 미채택 (생성만, 로컬 파일 Write)
- 외주 의견 위 집계·다수결·KPI / 레드팀 destructive 행위 — ADR-0021
- 외주 setup hook 의 marker 외 입력 파싱 / `stop_hook_active` 무시 / enum 미강제 / 일반 dispatch 침투 — ADR-0022
- frontmatter name ↔ 파일명 stem 불일치 / 파일 없는 채용 audit (유령참조) — ADR-0023
- 판정 게이트 없는 무조건 dispatch / dispatch 워커에 파일 쓰기 위임 / dispatch 시 sonnet 자동 강등 — ADR-0025

> 새 금지 항목 추가 시 [`docs/internals/forbidden-history.md`](docs/internals/forbidden-history.md) 갱신 필수.

## 7. 디렉토리 구조

전체 구조는 [`docs/internals/directory-structure.md`](docs/internals/directory-structure.md) 참조. 핵심:

- `src/lskun_kit/` — Python core (stdlib only, 0 외부 의존성)
- `commands/` — slash command 본체 (markdown)
- `agents/` — dispatch 전용 agent 2종, 도구 권한으로 쓰기·chain 제한 (ADR-0026)
- `hooks/` — SessionStart + PreToolUse:Task hook
- `tests/` — stdlib unittest
- `docs/internals/` — 본 plugin 의 분리된 내부 문서 (P109-C)

**hired/ 같은 회사 운영 데이터는 본 repo 에 절대 작성 금지** (사용자 SSOT `~/.lskun-companies/<name>/` 에만).

## 8. 로드맵

Phase 전체 기록은 [`docs/internals/phase-roadmap.md`](docs/internals/phase-roadmap.md) 참조. 현재 Phase 는 §1 버전 필드 (plugin.json SSOT) 를 따른다 — 본 절에 Phase 번호를 중복 박제하지 말 것 (이중 SSOT 방지).

## 9. CPO / 인사팀장 동작 사양 (ADR-0002 + ADR-0004)

### CPO (Chief Product Officer)

- **호출 모델:** 메인 Claude Code 세션 자체가 CPO persona 로 동작 (ADR-0004 §1, CLAUDE.md inline 박제)
  - `/lskun-kit:work "..."` (이름 생략) → CPO 가 받아 라우팅 → 결재 → 응답
  - `/lskun-kit:work backend-engineer "..."` → 직통, CPO 결재 생략 (cheap path)
  - `/lskun-kit:work cpo "..."` → CPO 와 전략 대화
- **책임:**
  - 요청 분석 → 적합 워커 라우팅 (도메인 일치 우선)
  - **Delegation Gate 판정 (ADR-0025)** — ①컨텍스트 보호 ②병렬 탐색 ③독립 검증 시에만 dispatch, 그 외 빙의 (워커 JD 주입 직접 수행). dispatch 워커는 read-only 기여, 쓰기는 CPO 단일 스레드
  - Task tool 로 워커 dispatch (model 결정 = `--model` / frontmatter / 미지정=메인 세션 상속, ADR-0025 D4)
  - 워커 보고 결재 (산출물 원본 확인, ADR-0025 D6 / 재작업 최대 2회)
  - **부재 워커 자동 채용** — HR Lead 를 Task tool 로 호출 + 사용자 알림 1줄 (차단 X)
  - 결재 audit 박제 — 결재 1건마다 `audit.record()` (ADR-0006. ~~reflection.record~~ 는 ADR-0014 폐기)
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
