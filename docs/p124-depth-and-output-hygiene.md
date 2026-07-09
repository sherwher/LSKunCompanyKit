# P124 — 결과물 깊이 프로토콜 + 출력 위생 (ADR-0024)

> 2026-07-09. 사용자 실사용 피드백 2건에 대한 구조 개선.
> ADR 본문 SSOT 는 vault `decisions/ADR-0024-2026-07-09-depth-and-output-hygiene.md`.

## 문제 진단

### 1. `<invoke>` tool 구문 텍스트 누출

- `cpo.md` / `work.md` 가 `Task(subagent_type="claude", ...)` 형태 의사코드 블록을
  "반드시 다음 형식으로 dispatch" 라고 지시 → 메인 세션 LLM 이 이를
  "이 구문을 텍스트로 출력하라" 로 오해석, tool call XML (`<invoke>` 등) 을
  응답 본문에 그대로 흘리는 priming 발생.
- 출력 위생 (tool 호출은 실제 tool call 로만) 규칙이 어떤 persona/command 에도 없음.

### 2. CPO 판단·워커 결과물 깊이 부족

- **JD 분량 100~300자 권장** (hr-lead.md §6) — 워커 전문성이 불릿 몇 줄 수준.
  도메인 함정·안티패턴 지식이 JD 에 박히지 않음.
- **워커 보고 양식이 깊이를 캡핑** — "작업 결과 3~5줄 요약 + 자가 평가 1줄" 이
  전부라, 워커가 깊게 일해도 보고 단계에서 근거·대안·검증이 소실.
- **CPO 결재 = 양식 존재 확인** — "2 섹션 모두 존재? 통과면 승인" 수준의
  도장 찍기. 실질 rubric (요청 대조 / 검증 증거 / 도메인 함정) 부재.
- **dispatch prompt 에 사고 지시 부재** — 재해석·가정 명시·대안 검토·검증 등
  깊이를 끌어내는 프로토콜이 주입되지 않음.

## 결정 (ADR-0024)

### D1. 출력 위생 (Output Hygiene)

`cpo.md` / `work.md` / `hr-lead.md` 에 공통 규칙 박제:

- 도구 호출은 **실제 tool call 로만**. `<invoke>` / `<function_calls>` /
  `Task(...)` 등 tool 구문을 응답 텍스트로 출력 금지.
- 문서 내 `Task(...)` / `invoke_skill(...)` 코드 블록은 **개념 설명용 의사코드**
  라벨 명시 — 재출력 금지.
- dispatch 서술은 자연어 1줄 ("<워커> 에게 위임") 만.

### D2. Deep Work Protocol — dispatch prompt 표준 주입 블록

모든 워커 dispatch prompt 에 다음 4단계 프로토콜을 주입 (직통·CPO 라우팅·자동
채용 후 dispatch 일괄):

1. 착수 전 — 요청 재해석 1~2줄 + 암묵 가정·성공 기준 명시
2. 수행 — 핵심 결정마다 근거, 배제한 대안 1줄
3. 검증 — 주장 전 실행/테스트/재독 확인, 미확인은 "미검증" 표시
4. 보고 — 요약에 그치지 않고 상세 근거 포함

### D3. 보고 양식 심화 (ADR-0014 의 2섹션 구조는 유지)

`## 작업 결과` = 요약 3~5줄 **+ 상세** (핵심 결정·근거·배제 대안·트레이드오프·
검증 증거, 분량 제한 없음). `## 자가 평가` 에 미검증 항목 명시 의무.
섹션 수는 2개 그대로 — ADR-0014 결정 변경 아님.

### D4. CPO 결재 rubric 실질화

양식 검증에 더해 3항목 실질 점검. 하나라도 미달이면 구체 사유와 함께 rework:

- **R1 요청 대조** — 사용자 요청의 각 요구가 결과 어디에 대응되는지 확인
- **R2 검증 증거** — 실행·테스트·근거 없는 "완료" 주장은 미달
- **R3 도메인 함정** — 워커 JD 의 도메인 관점에서 누락·함정 점검

### D5. JD 분량 상향

100~300자 → **300~800자**. `## 핵심 역량` 에 도메인 함정·안티패턴 지식
(하지 말아야 할 것) 포함 권장.

### D6. 모델·사고 라우팅

복잡·다단계·보안·아키텍처 작업은 opus dispatch + prompt 에 깊은 사고 지시
포함 (기존 opus 권장 기준 유지, 사고 지시 문구만 추가).

## 비변경 (스코프 밖)

- ADR-0014 (JD only, 2섹션 보고) / ADR-0017 (allowlist) / ADR-0023 결정 유지.
- plugin core 코드 로직 변경 없음 — `routing.py` 의 컨텍스트 문자열에
  출력 위생 + 프로토콜 hint 줄 추가만.
- hook 추가 없음 (출력 위생은 persona 지침으로 충분, 위반 재발 시 후속 Phase 에서
  Stop hook 검출 검토).

## 적용 파일

| 파일 | 변경 |
|---|---|
| `src/lskun_kit/templates/cpo.md` | 출력 위생 절 + Deep Work Protocol + 보고 양식 심화 + 결재 rubric |
| `src/lskun_kit/templates/hr-lead.md` | JD 분량 상향 + 함정 지식 + 출력 위생 1줄 |
| `commands/work.md` | 출력 위생 절 + dispatch prompt 프로토콜 주입 지시 + 의사코드 라벨 |
| `commands/hire.md` | JD 분량 문구 갱신 |
| `src/lskun_kit/routing.py` | 라우팅 컨텍스트에 출력 위생 + 프로토콜 hint |
| `.claude-plugin/plugin.json` | 0.31.0 |

기존 회사 적용: `/lskun-kit:sync-persona` 로 CPO/HR persona 갱신 (frontmatter 보존).
