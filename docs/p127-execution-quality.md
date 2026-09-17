# P127 — 실행 품질 규격화: 브리프·보고·검증 접점 (ADR-0025/0024 보강, v0.33.0)

> 새 ADR 없음 — ADR-0025 (Delegation Gate) / ADR-0024 (결과물 깊이) 의 절차 구체화.
> 기존 결정을 뒤집는 항목이 없다. 본 문서는 plugin repo 측 구현 spec.

## 1. 문제 — 조사 결과

2026-09-17, "더 많은 일을 더 정교하게" 를 목표로 세 갈래를 조사했다: 현재 플러그인 기준선,
외부 플러그인 생태계, Claude Code 공식 기능.

- **기준선**: 거버넌스 (chain 차단·allowlist·채용 불변식·외주 시퀀스) 는 hook 으로 강제되어
  강하다. 실행 품질 (게이트 판정·결재·검증) 은 전부 persona 프롬프트 의존이다.
- **외부 증거**: Anthropic 의 위임 기준은 ADR-0025 3조건과 사실상 동일 — 설계 방향은 맞다.
  개선 여지는 새 메커니즘이 아니라 세 접점의 규격에 있다.
  - Anthropic 멀티에이전트 연구: 모호한 위임 지시가 subagent 중복·누락의 주원인. 브리프에
    목표·출력 형식·도구/소스 가이드·작업 경계가 필요. 멀티에이전트는 토큰 약 15배.
  - obra/superpowers `verification-before-completion`: 새 검증 증거 없이 완료 주장 금지.
  - obra/superpowers `subagent-driven-development`: 보고 상태코드 4종으로 후속 분기 고정.

### 기존 구현과의 간극

| 접점 | P126 까지 | 간극 |
|---|---|---|
| 브리프 | Handoff Brief 5필드 | 출력 형식·도구/소스 가이드 없음 |
| 검증 | 결재 R2 (dispatch 건만) | 기본 경로인 빙의에 완료 주장 규율 없음 |
| 보고 | 자가 평가 "통과 / 부분 통과 / 불확실" | 무엇이 부족한지로 분기할 수 없음 |
| 게이트 | dispatch 여부만 판정 | 몇 명을 보낼지 기준 없음 |

## 2. 결정 (Q1~Q4)

- **Q1 Handoff Brief 7필드** — `기대 출력 형식` / `도구·소스 가이드` 추가. 기존 5필드 유지.
- **Q2 증거 게이트** — 빙의 건도 이번 턴의 새 검증 증거 (실행 출력·테스트 결과·재독 확인)
  없이 완료 주장 금지. 없으면 "미검증" 보고. 결재 루프 적용 범위 = dispatch 또는 빙의 1건당.
  rationalization 표 4행을 CPO persona 에 박제.
- **Q3 보고 상태코드** — `## 자가 평가` 첫 줄 =
  `상태: DONE | DONE_WITH_CONCERNS | NEEDS_CONTEXT | BLOCKED`. 2섹션 구조 불변 (ADR-0014).
  분기: DONE → R1~R3 / DONE_WITH_CONCERNS → 우려 판단 / NEEDS_CONTEXT → 브리프 보강 후
  재dispatch (rework 횟수 포함) / BLOCKED → 원인 해소 또는 사용자 보고 (재작업 아님).
  상태코드는 자기 신고이며 결재를 대체하지 않는다. audit verdict enum 불변 (ADR-0006).
- **Q4 규모 스케일링** — 게이트 통과 후: ① 1명 / ② 독립 서브태스크 수만큼 상한 4, 브리프
  작업 경계 비중첩 시에만 / ③ verifier 1명.

## 3. 비채택

- 상태코드의 audit 박제·집계 — audit 위 통계·KPI 금지 (ADR-0006) 와 충돌.
- 워커별 도구 권한 강제 (`disallowedTools`) — ADR-0017 allowlist 변경이 필요해 별도 ADR 로 분리.
- 결재 audit 누락의 hook 강제 (`SubagentStop`) — 코드 변경 범위가 달라 후속 Phase 로 분리.
- subagent `memory:` 필드 — ADR-0014 정면 저촉.

## 4. 적용 지점

- `src/lskun_kit/templates/cpo.md` — §Delegation Gate 하위 2절 신설 (규모 스케일링 / 증거 게이트),
  §Handoff Brief 2필드, §Deep Work Protocol 4단계 (상태 줄 — 워커에게 전달되는 유일한 경로),
  §보고 양식 상태 줄 + §상태코드별 분기, §결재 머리말
- `src/lskun_kit/templates/hr-lead.md` — 채용 보고 양식의 자가 평가에 상태 줄
- `commands/work.md` — 라우팅 3단계·규모 스케일링 안내·사양 목록
- `src/lskun_kit/routing.py` — CPO 라우팅 컨텍스트 안내문
- `tests/test_p127_execution_quality.py` — 회귀 가드 14건

## 5. 마이그레이션 (기존 배포 사용자)

1. plugin update → v0.33.0 수신
2. `/lskun-kit:sync-persona --execute` — CPO / HR Lead persona 갱신 + CLAUDE.md marker 재박제
3. 일반 워커 JD 변경 불필요 — 상태코드는 모든 dispatch 에 주입되는 Deep Work Protocol 블록으로 전달된다
