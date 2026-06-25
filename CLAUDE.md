# LSKunCompanyKit — Claude Code Instructions

> 본 문서는 LSKunCompanyKit 저장소에서 Claude Code 가 따라야 할 프로젝트 헌법.
> 상위 결정문 전체 인덱스: [`docs/internals/adr-index.md`](docs/internals/adr-index.md)
> 본문 결정 인용은 ADR 번호 (ADR-NNNN) 만 사용. 저자 SSOT 물리적 위치는 박제하지 않음 (ADR-0009 §5).

---

## 1. 프로젝트 정체성

- **이름:** LSKunCompanyKit
- **종류:** Claude Code plugin
- **버전:** `.claude-plugin/plugin.json` 의 `version` 필드가 단일 진실원 (ADR-0012). 현재 Phase 21 (0.28.0) — **외주 setup 자동 시퀀스 결정론 강제 (ADR-0022)**. 멀티-step CPO 시퀀스(외주 setup)의 중간 멈춤을 PostToolUse:Task + Stop hook 이중 강제(push)로 차단, `/clear` 강제 break 는 command 본문 안내(pull)로 보완. marker(`.external-setup.json`) 존재 시에만 동작, enum allowlist + 24h TTL + `stop_hook_active` invariant + `LSKUN_ALLOW_EXTERNAL_HALT` escape hatch. **이전 (0.27.0)** = 외주(레드팀·고객) 도입 (ADR-0021). 외주는 회사 임직원이 아니며 회사 SSOT 하위 `external/<project>/` 에 거주(3번째 SSOT 금지), 워커 세션 clear 후 CPO 단독 dispatch, 외주 body 는 untrusted fence 격리. 옛 버전 상세는 CHANGELOG 참조.
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
| `/lskun-kit:doctor` | 환경 진단 (라벨 [1]~[37] 중 18·19 결번 — ADR-0015 7-C/7-D + ADR-0016 [20][21] + ADR-0017 [22][23] + ADR-0020 [31] + ADR-0021 [32] + ADR-0022 [33][34] + ADR-0023 [35][36][37]) (35개 항목) |
| `/lskun-kit:external` | 프로젝트별 외주(레드팀·고객) 구성/청취/cancel (ADR-0021 + ADR-0022 자동 시퀀스) |

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

## 6. 절대 만들지 말 것 (요약)

**핵심 금지 항목** (전체 누적 목록은 [`docs/internals/forbidden-history.md`](docs/internals/forbidden-history.md) 참조):

- persona evolution narrative (워커가 시간으로 자동 진화) — ADR-0014 폐기
- 워커 → 워커 chain (sub-leader 출현) — ADR-0004 §8, PreToolUse hook 차단
- CPO/HR 외 임원 자동 추가 — ADR-0002 §1~§2
- audit log 위 자동 평가·대시보드·KPI — ADR-0006
- archive 메커니즘 재도입 — ADR-0019 (2026-05-27 폐기)
- 외부 harness (cmux/ralph/ultrawork) plugin core 도입 — ADR-0009 self-contained
- subagent_type="claude" 외 dispatch — ADR-0017 Allowlist
- plugin core 안에서 외부 시스템 SDK / API 호출 — ADR-0009
- skill marketplace/원격 다운로드 (네트워크 접촉) — ADR-0020 미채택 (생성만, 로컬 파일 Write)
- 외주 의견 위 집계·다수결·KPI / 레드팀 destructive 행위 — ADR-0021
- 외주 setup hook 의 marker 외 입력 파싱 / `stop_hook_active` 무시 / enum 미강제 / 일반 dispatch 침투 — ADR-0022

> 새 금지 항목 추가 시 [`docs/internals/forbidden-history.md`](docs/internals/forbidden-history.md) 갱신 필수.

## 7. 디렉토리 구조

전체 구조는 [`docs/internals/directory-structure.md`](docs/internals/directory-structure.md) 참조. 핵심:

- `src/lskun_kit/` — Python core (stdlib only, 0 외부 의존성)
- `commands/` — slash command 본체 (markdown)
- `hooks/` — SessionStart + PreToolUse:Task hook
- `tests/` — stdlib unittest
- `docs/internals/` — 본 plugin 의 분리된 내부 문서 (P109-C)

**hired/ 같은 회사 운영 데이터는 본 repo 에 절대 작성 금지** (사용자 SSOT `~/.lskun-companies/<name>/` 에만).

## 8. 로드맵

Phase 1~21 전체 기록은 [`docs/internals/phase-roadmap.md`](docs/internals/phase-roadmap.md) 참조. 현재 Phase 21 (0.28.0) — 외주 setup 자동 시퀀스 결정론 강제 (P121, ADR-0022).

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
