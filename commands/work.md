---
name: lskun-kit:work
description: 워커 호출 — 자기 history 컨텍스트 주입 + 세션 활성화. 워커 이름 생략 시 CPO 가 라우팅 (ADR-0002 §1).
arguments:
  - name: worker
    description: 호출할 워커 이름. 생략 시 CPO 가 적합 워커를 추천 (Q1=ii)
    required: false
  - name: request
    description: 사용자 요청 본문 (워커 이름 생략 시 CPO 라우팅 컨텍스트에 주입)
    required: false
---

# /lskun-kit:work

워커를 이번 세션의 활성 워커로 지정하고, 자기 history 를 컨텍스트로 주입한다.

## 분기 (ADR-0002 §1, Q1=ii)

| 호출 형태 | 동작 |
|---|---|
| `/lskun-kit:work backend-engineer "..."` | 직통 호출. CPO 경유 안 함. |
| `/lskun-kit:work cpo "..."` | CPO 와 직접 전략 대화. |
| `/lskun-kit:work "..."` (워커 이름 생략) | CPO 가 받아 적합 워커 추천 → 사용자가 다음 명령 실행 |

## 동작

### 직통 (워커 이름 명시)

1. 활성 backend 결정 (`/hire` 와 동일 규칙)
2. `lskun_kit.context.build_worker_context(adapter, <worker>)` 호출 → 컨텍스트 주입
3. `lskun_kit.session.start(<root>, <worker>)` 호출 → 세션 파일 작성
4. 사용자가 자유롭게 일을 시킨다. 종료 시 Stop hook 또는 `/lskun-kit:reflect` 가 1줄 박제.

### CPO 라우팅 (워커 이름 생략)

1. `lskun_kit.routing.decide_target(adapter, requested_worker=None)` 호출
2. CPO 가 hired 되어 있지 않으면 → `/lskun-kit:init` 실행 안내 후 종료
3. `lskun_kit.routing.build_cpo_routing_context(adapter, user_request)` 의 markdown 을 컨텍스트로 주입
4. 세션 활성 워커 = `cpo` 로 등록
5. CPO 응답 안에 "다음 명령: /lskun-kit:work <worker> ..." 형식의 권장이 포함된다 — 사용자가 직접 실행

## 사양

- ADR-0002 §1 — CPO 호출 모델 (Q1=ii)
- ADR-0002 §6 — CPO 가 인사팀장 / 다른 워커를 chain 호출하지 않는다 (사용자 승인 1단계 필수)
- `docs/reflection-spec.md` §4 컨텍스트 주입

## Python 진입점

```python
from pathlib import Path
from lskun_kit.routing import decide_target, build_cpo_routing_context
from lskun_kit.context import build_worker_context
from lskun_kit import session, LocalAdapter

adapter = LocalAdapter(Path.cwd() / ".company")
decision = decide_target(adapter, requested_worker=None)
if decision.mode == "direct":
    ctx = build_worker_context(adapter, decision.target_worker)
elif decision.mode == "cpo":
    ctx = build_cpo_routing_context(adapter, user_request="...")
else:  # missing-cpo
    print(decision.reason)
```
