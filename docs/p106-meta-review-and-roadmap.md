# P106 — 메타 리뷰 + 발전 방향 로드맵

> **작성:** 2026-05-27
> **방식:** 4 페르소나 다자 토론 (skillers-suda 스타일, 4 round)
> **참여 페르소나:** 실사용자 (U) / Plugin·Agent 아키텍트 (A) / 신규 도입자·보안 (D) / Critic·ADR 감사관 (C)
> **상태:** Draft — 사용자 결재 대기. ADR-0018 박제 + P107~P109 구현은 본 design 승인 후

---

## 1. 검토 목적

사용자 요청: "실제 plugin 사용자 입장과 plugin 전문가 등 필요한 인원을 많이 소집해서, 현재 plugin 이 목표에 맞는 역할을 하는지, 추가적으로 harness 도입이 필요한지 체크하고, 발전 방향을 모색."

본 문서는 brainstorming session 의 결론을 박제하고, 후속 ADR / Phase 의 입력으로 사용된다.

## 2. 4 페르소나 토론 결과

### 2.1 합의 (전원 동의)

| # | 결론 | 근거 |
|---|---|---|
| 1 | **목표 부합도 = 부합** | Leader-Worker (CPO 메인 세션) + JD-driven (time-invariant) + storage abstraction 3축이 ADR-0001/0004/0014/0015 의 정체성과 일치 |
| 2 | **외부 harness 도입 = 불필요** | cmux/ralph/ultrawork 도입은 ADR-0009 (self-contained) + ADR-0014 (시간 진화 부정) 위반. plugin 자체가 이미 harness (PreToolUse:Task hook + SessionStart + doctor 23개 진단) |
| 3 | **부족한 것 = 자기관찰 도구** | 외부 자동화가 아니라 "회사 상태를 사용자가 한눈에 보는" 능력 부재 |
| 4 | **ADR 17개 인플레이션 우려 = 무근거** | supersede chain 은 정체성 정립의 건강한 신호 (4 전문가 시뮬레이션으로 만장일치 받아 ADR-0014 실행 = -2316 LoC) |

### 2.2 핵심 발견 (실측 기반)

토론 중 U (실사용자) 가 `ls ~/.lskun-companies/LSKun/hired/` 출력에서 발견한 **즉각 시정 필요 사항:**

```
cpo.md
cpo.md.lskun-pre-sync.bak
cpo.md.lskun-pre-sync.bak.1779780562
cpo.md.lskun-pre-sync.bak.1779786151
... (7개+ 백업 파일이 hired/ 에 섞여있음)
```

- `/sync-persona` 가 누적 백업을 청소하지 않음
- `/org` 라우팅 / 카운트가 백업 파일 노이즈를 무시하는지 불확실 (확인 필요)
- doctor 가 이 오염을 검출하지 않음

### 2.3 boundary 합의 (D 가 정리, C 가 수긍)

ADR-0002 §5 + ADR-0006 의 "KPI / 자동 평가 / 대시보드 금지" 와 **자기관찰 도구** 의 경계:

| 금지 (불변) | 허용 (도입 가능) |
|---|---|
| 자동 평가 / 점수화 | 사실 표시 (dispatch count) |
| 정기 자동 산출 (월간/분기) | 사용자 명시 옵션 (`--usage`) |
| 외부 자동 전송 | 로컬 stdout 만 |
| 워커 자동 해고·평가 | 사용자가 보고 판단 |
| KPI / 대시보드 / 시각화 | audit log 의 단순 view |

이 boundary 가 후속 ADR-0018 의 핵심 조항.

## 3. 우선순위 로드맵

### P0 — 즉시 (1~2 일)

#### P0-1. 백업 파일 청소

- **문제:** `/sync-persona` 가 `<name>.md.lskun-pre-sync.bak.<timestamp>` 를 timestamp 별로 누적. 7개+ 발견
- **해결:**
  - `persona_sync.py` 에 `--cleanup-backups [--keep N]` 옵션 추가 (기본 keep=3, 사용자 명시)
  - 자동 청소 X (역사 자산 불변 원칙, ADR-0015 정신)
- **doctor 신규 [24]:** `hired/` 에 `*.lskun-pre-sync.bak*` 가 3개 초과 시 ⚠️ + cleanup 명령 안내
- **테스트:** 신규 5개 (cleanup, --keep, 멱등성, 빈 디렉토리, audit log 무영향)

#### P0-2. `/org` 의 백업 파일 무시 검증

- **문제:** `org.py` / `routing.py` 가 hired/ 의 `*.md` glob 시 backup 파일도 워커로 인식할 가능성
- **해결:** 명시적 필터 — `name.endswith('.md') and not '.lskun-pre-sync.bak' in name`
- **doctor 신규 [25]:** hired/ 스캔 시 backup 파일이 워커로 카운트되는지 시뮬레이션 검증
- **테스트:** 신규 3개

**P0 합계 = +8 tests, 진단 21 → 25**

### P1 — 단기 (1~2 주)

#### P1-1. `/org --usage` (audit log view)

- **문제:** 사용자가 41명 중 실제 dispatch 되는 워커가 누구인지 모름 (long tail 의심)
- **해결:** `cli_org.py` 에 `--usage` 옵션 — `.audit/decisions.jsonl` 을 파싱하여 워커별 dispatch count + 마지막 dispatch 일자 표시
  - 사용자 명시 옵션 (자동 산출 X)
  - 기본 출력 (옵션 없을 때) 은 ADR-0013 stable markdown table 그대로
  - 평가·점수·랭킹 없음 — 단순 count + last_seen
- **포맷:**
  ```
  | name      | role          | dispatches | last_seen   |
  |-----------|---------------|-----------:|-------------|
  | cpo       | cpo           |        342 | 2026-05-27  |
  | hr-lead   | hr-lead       |         18 | 2026-05-26  |
  | tech-be   | backend       |         42 | 2026-05-25  |
  | aimbti-pe | product-expert|          2 | 2026-04-12  |
  ```
- **테스트:** 신규 8개

#### P1-2. audit log 회전 (사용자 명시)

- **문제:** `.audit/decisions.jsonl` 1년 후 수십 MB 우려 (D 지적)
- **해결:**
  - `/lskun-kit:audit-rotate` 신규 명령 (사용자 명시만)
  - `decisions.jsonl` → `decisions.YYYY-MM.jsonl.gz` 로 회전 (현재 월 제외)
  - 자동 회전 X (ADR-0006 정신)
  - `/org --usage` 는 회전된 파일도 읽음
- **doctor 신규 [26]:** `decisions.jsonl` 크기 > 10 MB 시 ℹ️ 회전 안내
- **테스트:** 신규 6개

#### P1-3. CLAUDE.md slim

- **문제:** CLAUDE.md 47KB 가 매 세션 컨텍스트 주입 (토큰 비용)
- **해결:**
  - CLAUDE.md 를 핵심 5~8KB 로 압축 (§1 정체성 / §2 핵심 메커니즘 요약 / §6 폐기 목록 / §10 작업 규칙)
  - 상세 (Phase 1~17 로드맵 / ADR 전문 인용) 은 `docs/internals/` 로 분리
  - 분리 기준: **신규 세션 LLM 이 봐야 하는 것** 만 CLAUDE.md, **개발 시 참조** 는 docs/
- **검증:** 토큰 카운트 측정 (전후 비교), 47KB → 목표 8KB 이하
- **회귀:** 251 tests 회귀 0건 보장 (코드 변경 0)

**P1 합계 = +14 tests, 진단 25 → 26, CLAUDE.md -39KB**

### P2 — 중기 (1~3 개월)

#### P2-1. ADR-0018 박제 — "No external harness, doctor is the harness"

- **결정 문구 초안:**
  1. plugin core 는 외부 harness (cmux/ralph/ultrawork/CI 자동화) 를 도입하지 않는다
  2. plugin 자체가 harness 다 — PreToolUse:Task hook (dispatch 검증) + SessionStart (컨텍스트 주입) + doctor (환경 진단)
  3. 부족한 자기관찰 능력은 **doctor 확장** + **사용자 명시 view 명령** (`/org --usage`) 으로 보완
  4. 자동 평가·KPI·대시보드는 ADR-0006 정신을 유지하되, "사용자 명시 view" 는 허용 (boundary §2.3)
- **escape hatch:** 없음 (외부 harness 는 사용자가 별도 add-on 으로 자유롭게 사용 가능, plugin core 만 미도입)
- **재도입 조건:** 5회째 같은 결론 (no harness) 을 재발견하면 그때 새 ADR

#### P2-2. 회사 상태 health check (doctor 확장)

- **신규 진단 [27]~[30]:**
  - [27] 30일+ 미 dispatch 워커 목록 (단순 정보, 해고 권유 X)
  - [28] 도메인 분포 — 빈 도메인 / 1명만 있는 도메인 표시
  - [29] hired/ 의 비-`.md` 파일 / 비-worker `.md` 파일 검출 (P0-1/P0-2 연장)
  - [30] archived/ 의 옛 display_name 충돌 검사 (ADR-0015 결정 7-C)

#### P2-3. 신규 도입자 onboarding

- README §"5분 첫 사용" 시나리오 박제
  - 1단계: `/lskun-kit:init` → 회사명 + 도메인 입력
  - 2단계: 권한 박제 confirm
  - 3단계: CPO/HR 자동 hire 확인 (`/org`)
  - 4단계: 첫 dispatch (`/lskun-kit:work "Spring Boot 의 ApplicationContext 설명해줘"`)
  - 5단계: `/doctor` 로 환경 확인
- CLAUDE.md 47 → 8KB 와 짝지어 진입장벽 완화

### P3 — 장기 (보류, 실증 후)

| 항목 | 보류 사유 |
|---|---|
| Multi-project 팀 운영 시나리오 | ADR-0008 교훈 — 실증된 후에만 새 ADR. 현재 단일 사용자 (사용자 1명) 시점 |
| 외부 통합 (Notion / Slack) | ADR-0009 self-contained 원칙 유지. add-on 별도 repo, plugin core 의존 X |
| 워커 promotion (sonnet → opus) UI | 현재 frontmatter 수동 편집으로 충분, 별도 명령 X |
| LLM-as-judge 자동 평가 | ADR-0014 폐기 결정과 일관 — 영구 금지 |

## 4. ADR-0014 / ADR-0017 의 정합성 확인

본 로드맵의 모든 항목이 기존 ADR 과 충돌하지 않는지 확인:

| 항목 | 충돌 ADR | 정합성 |
|---|---|---|
| P0-1 backup cleanup | ADR-0015 (역사 자산 불변) | ✅ 사용자 명시 옵션, keep=N 보존 |
| P0-2 backup 필터 | — | ✅ 버그 시정 |
| P1-1 `/org --usage` | ADR-0002 §5, ADR-0006 | ✅ §2.3 boundary 의 "허용" 범주 |
| P1-2 audit rotate | ADR-0006 | ✅ 사용자 명시만, 자동 X |
| P1-3 CLAUDE.md slim | ADR-0014 (정체성 박제) | ✅ 정체성 압축, 정보 손실 0 (docs/ 로 이동) |
| P2-1 ADR-0018 | ADR-0009 (self-contained) | ✅ ADR-0009 강화 |
| P2-2 health check | ADR-0002 §5, ADR-0006 | ✅ 정보 표시, 평가 X |
| P2-3 onboarding | ADR-0009 | ✅ self-contained 유지 |

## 5. 작업 순서 (구현 phase 박제 예정)

```
P106 (본 design)  → 사용자 결재 후 commit
P107 (P0)         → backup cleanup + /org 필터 (+8 tests, 진단 25)
P108 (P1)         → /org --usage + audit rotate + CLAUDE.md slim (+14 tests, -39KB)
P109 (P2-1)       → ADR-0018 박제 (4 전문가 시뮬레이션 만장일치 후)
P110 (P2-2,2-3)   → health check 진단 4종 + README onboarding
```

각 phase 의 사용자 결재 게이트 유지 (ADR-0006 정신).

## 6. 자기 검토 (spec self-review)

- **Placeholder:** 없음. 모든 항목 구체적
- **내부 일관성:** §2.3 boundary 가 P1-1 / P2-1 의 근거. 충돌 없음
- **Scope:** P0 + P1 = 단일 implementation plan 가능. P2~P3 는 별도 phase
- **Ambiguity:** P0-1 의 "keep N" 기본값을 3으로 고정 명시. P1-3 의 "8KB 목표" 는 측정 후 조정 여지 명시

## 7. 사용자 결재 대기 항목

본 design 을 commit 하기 전 사용자 결정 필요:

1. **P0~P2 우선순위 동의 여부** — 다른 순서 선호 시 알려주세요
2. **P0-1 의 keep 기본값** — 3개가 적절한지 (1개 / 5개도 가능)
3. **P1-3 의 CLAUDE.md slim 목표** — 8KB 가 과도하면 15KB 도 가능
4. **P2-1 ADR-0018 박제 시점** — P0/P1 완료 후 vs 즉시
5. **본 design 을 docs/p106-...md 로 commit 할지** — 또는 ADR 디렉토리 형식 선호 여부

---

**다음 단계:** 사용자 결재 → P106 design commit → P107 writing-plans (P0 구현 계획)
