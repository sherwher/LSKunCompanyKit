---
name: lskun-kit:reflect
description: 명시적 Reflection — 활성 워커 history 에 1줄 append
arguments:
  - name: project
    required: true
  - name: topic
    required: true
  - name: pattern
    required: true
  - name: first_pass_score
    description: 1차 통과율 0..100
    required: true
---

# /lskun-kit:reflect

이번 작업의 Reflection 을 워커 history 에 1줄 박제한다.

## 동작

1. `lskun_kit.session.read(<root>)` 로 활성 워커 확인 — 없으면 ❌ 후 `/lskun-kit:work` 호출 안내
2. `lskun_kit.reflection.record(adapter, worker, project, topic, pattern, first_pass_score)` 호출
3. 결과 1줄을 사용자에게 표시:

```
✅ 기록됨: alice
- 2026-05-15 / music-pay / refund-flow / saga / first-pass 88%
```

4. 세션 상태 정리 (`session.clear`).

## 입력 규칙

- `project`, `topic`, `pattern` 에 `/` 포함 금지 — grep 친화 포맷 보호
- `first_pass_score` 는 0..100 정수
- 위반 시 `ValueError` → 사용자에게 메시지 표시 후 종료

## 위상 (ADR-0013)

본 명령은 **사용자 수동 정정 경로**다. 메인 자동 박제 경로는 **CPO 결재 6단계의 §4/§5** (cpo.md SSOT) — 즉 `/lskun-kit:work` 로 워커를 dispatch 하면 CPO 가 결재 직후 `lskun_kit.reflection.record()` 를 1줄 호출. 본 명령은 그 경로가 누락된 케이스 (직통 `/lskun-kit:work <name>` 후 사용자가 직접 박고 싶을 때, 또는 과거 누락 복구) 에 사용.

## Stop hook 과의 관계

Stop hook 은 **`/lskun-kit:work <worker>` 직통 경로의 안전망**이다. 사용자가 환경변수 (`LSKUN_PROJECT`, `LSKUN_TOPIC`, `LSKUN_PATTERN`, `LSKUN_FIRST_PASS`) 로 사전 제공한 경우만 발동. **메인 세션 = CPO 의 Task dispatch 경로에서는 동작하지 않는다** (CPO 가 위 env 를 설정하는 메커니즘 없음 — ADR-0013 §"컨텍스트 2"). 따라서 메인 박제 경로는 cpo.md 결재 6단계가 단일 SSOT.

### Reflection 진실성 가드 (`LSKUN_OUTCOME`)

작업이 실패·중단됐는데 환경변수가 채워져 있어 박제되는 오염을 막기 위해 Stop hook 은 `LSKUN_OUTCOME` 을 읽는다:

- `LSKUN_OUTCOME=success` (default, 환경변수 부재 시 동일) → 정상 박제
- `LSKUN_OUTCOME=aborted` → **박제 skip, 세션만 정리.** 워커 history 변경 없음.

CPO/워커가 작업 실패를 인지하면 본 변수를 `aborted` 로 export 후 종료한다.

`docs/reflection-spec.md` §5 자동 vs 명시 reflection 참조.
