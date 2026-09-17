# Backlog — 검토했으나 아직 하지 않은 것

> `phase-roadmap.md` 는 완료된 Phase 의 역사 기록이다. 본 문서는 그 반대편 — 검토한 후보와 보류 사유,
> 다시 볼 조건을 적는다. 항목을 착수하면 여기서 지우고 roadmap 에 기록한다.
> 최초 작성: 2026-09-17 (P127~P133 릴리스 묶음 직후).

## 배포 후 사람이 확인할 것

| 항목 | 확인 방법 | 근거 |
|---|---|---|
| 빙의 건 결재 기록이 다시 나타나는가 | `~/.lskun-companies/<회사>/.audit/decisions.jsonl` 에서 `"reason":"embody:` 로 시작하는 줄을 직접 확인. 자동 집계 금지 | ADR-0027 알려진 한계 |
| `embody-audit` eval 첫 실행 | Bash 샌드박스가 되는 머신에서 `claude plugin eval . --case embody-audit --scaffold --allow-tools Agent Write Edit "Bash(lskun-audit *)"` | ADR-0028 알려진 한계 |
| 기존 회사 반영 | plugin update → 세션 재시작 → 회사당 1회 `/lskun-kit:sync-persona --execute` → 프로젝트마다 마지막 1회 `/lskun-kit:init <회사>` + 외부 import 승인 | CHANGELOG 0.34.0~0.38.0 |
| 승인된 외부 import 의 실제 로드 | 첫 전환 프로젝트를 대화형으로 열어 승인 → "자비스" 로 응답하고 로드 경고가 없는지 확인. headless (`claude -p`) 에서도 같은지 확인 | ADR-0029 알려진 한계 |

## 보류 — 다시 볼 조건이 있는 것

### persona 축소 (코어 200줄 이하 + 절차의 plugin `skills/` 이전)
- **현재 판단: 다음 후보 1순위.** `cpo.md` 는 26,000자 — Claude Code 공식 권고 (지침 파일 200줄 이하) 를 넘어 지시 준수도가 떨어지는 구간이다. 포인터 배포 (ADR-0029) 로 배포 문제는 풀렸고, 이제 크기가 남았다. 코어 (정체성 · 직접 응답 조건 · Delegation Gate · 결재 · 금지) 만 남기고 절차 (dispatch 표준 절차 · 자동 채용 · 외주 시퀀스 · 에스컬레이션 양식) 는 plugin `skills/` 로 옮기면, skill 은 plugin 안에 있어 sync 없이 항상 최신이다.
- **착수 조건:** 새 ADR. eval `embody-gate` 로 축소 전후 행동을 비교한다.

### 워커 명단 주입의 상한 (SessionStart 10,000자)
- **현재 판단: 워커 95명 전에 해야 한다 (2026-09-17 현재 72명, 7,963자).** hook 출력은 10,000자에서 잘려 파일 미리보기로 대체된다 — 명단이 조용히 사라진다. 요약 (인원 · 도메인별 수) 만 주입하고 CPO 가 라우팅 시 `cli_org --domain` 으로 후보를 조회하는 방식으로 바꾼다.
- **착수 조건:** 새 ADR (라우팅 절차 변경).

### `commands/` → `skills/` 이전
- **현재 판단: 단독으로는 하지 않는다 (위 persona 축소와 함께 다시 본다).** 공식 문서상 `commands/` 는 폐기 대상이 아니다 ("Skills as flat Markdown files. Use `skills/` for new plugins"). 이전하면 skill 이름 · persona 의 `/LSKunCompanyKit:work` 참조 · 테스트 · doctor 항목이 대거 바뀌지만 동작상 이득이 없다.
- **다시 볼 조건:** Claude Code 가 `commands/` 폐기를 공지하거나, `skills/` 전용 기능 (`context: fork`, 동적 컨텍스트 주입 `` !`cmd` `` 등) 이 필요한 구체적 요구가 생길 때. 그때는 새 ADR.

### 작업 단위 ledger (다단계 작업의 진행 상황 · CPO 결정 기록 파일)
- **현재 판단: 하지 않는다.** 필요의 상당 부분이 P131 (압축 직후 복구 정보) 로 덮였다. 워커 파일에 누적하면 ADR-0014 (history 금지) 에 저촉되고, 프로젝트 쪽에 두면 "3번째 SSOT" 금지와 닿는다.
- **다시 볼 조건:** 장시간 빙의 작업에서 압축 후 결정이 뒤집히는 사례가 실제로 관찰될 때. 위치 · 수명 (작업 종료 시 폐기) 을 ADR 로 먼저 정한다.

### 규모 적응 트랙 (`/work` 입력 복잡도별 즉시 실행 vs brainstorm → plan)
- **현재 판단: 하지 않는다.** 이미 "직접 응답 조건" (P37) · Delegation Gate (ADR-0025) · 규모 스케일링 (P127) 세 단이 있다. eval `embody-gate` 초안에서 CPO 가 작은 과제에 직접 응답 조건을 올바르게 적용하는 것을 확인했다.
- **다시 볼 조건:** 큰 요청을 계획 없이 바로 구현해 재작업이 반복되는 사례가 관찰될 때.

### audit schema 정리 (`first_pass_score` / `final_score` 제거)
- **현재 판단: 하지 않는다.** reflection 시절의 잔재 필드지만 제거하면 기존 기록과의 호환이 깨진다. `lskun-audit` 가 기본값으로 채운다 (ADR-0027 비채택).
- **다시 볼 조건:** schema 를 다른 이유로 바꿔야 할 때 함께.

## 알려진 한계 — 의도적으로 남긴 것

- **dispatch 워커의 Bash 경유 쓰기는 막지 못한다** (ADR-0026). Bash 를 제거하면 워커가 테스트 실행 · 탐색을 못 한다. persona 규칙 + 결재 R2 가 담당.
- **`subagent_type` 미지정 dispatch 는 allow** (ADR-0017 결정 유지). 기본 agent 로 떨어지며 도구 제한이 없다.
- **결재 기록은 강제되지 않는다** (ADR-0006 §2 — hook 자동화 미도입). `lskun-audit` 는 마찰만 줄인다.
- **Delegation Gate 판정 · 증거 게이트 · 상태코드 분기는 persona 지시다.** 코드로 강제할 수 없는 LLM 판단이며, eval suite 가 회귀를 관찰하는 수단이다.
- **agent teams (실험 기능) 미사용.** teammate 의 dispatch 호출에도 `agent_id` 가 실릴 수 있어 chain deny 대상이 될 수 있다 — agent teams 를 쓰게 되면 그때 확인한다.

## 채택하지 않기로 한 외부 패턴 (재제안 방지)

claude-flow 의 벡터 메모리 · queen 계층 / subagent `memory:` 필드 / SuperClaude 의 점수 추적 · continuous learning /
wshobson 의 orchestrator · marketplace 설치 모델 · 고정 모델 tier / ralph 계열 harness / 다중 persona 토론 —
모두 ADR-0014 · ADR-0004 §8 · ADR-0009 · ADR-0006 · ADR-0025 D4 중 하나 이상에 저촉. 상세는 `docs/p127-execution-quality.md`.
