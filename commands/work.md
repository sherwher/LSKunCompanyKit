---
name: lskun-kit:work
description: 워커 호출 — 자기 history 를 컨텍스트에 자동 주입하고 세션 상태에 활성 워커로 등록
arguments:
  - name: worker
    description: 호출할 워커 이름 (hired/<name>.md 가 존재해야 함)
    required: true
---

# /lskun-kit:work

워커를 이번 세션의 활성 워커로 지정하고, 자기 history 를 컨텍스트로 주입한다.

## 동작

1. 활성 backend 결정 (`/hire` 와 동일 규칙)
2. `lskun_kit.context.build_worker_context(adapter, <worker>)` 호출 → 다음 markdown 을 응답에 주입:

```markdown
# Worker: <worker> (<role>)
Hired: <hired_at> · Backend: <local|vault>

## Past Patterns (recent 10)
- 2026-05-10 / payment-svc / idempotency / stripe-key-as-idem / first-pass 92%
- ...
```

3. `lskun_kit.session.start(<root>, <worker>)` 호출 → `<root>/.lskun-session.json` 작성:

```json
{"active_worker": "<worker>", "started_at": "<ISO>"}
```

4. 이후 사용자가 자유롭게 일을 시킨다. 작업 종료 시 Stop hook 이 자동 Reflection (있을 경우) 또는 사용자가 명시적으로 `/lskun-kit:reflect` 를 호출.

## 사양

ADR-0001 §3 의 "다음 작업 → 워커가 자기 history 자동 주입받음" 단계의 구현. 컨텍스트 포맷은 사용자가 직접 읽어도 의미가 통하도록 markdown 으로 유지.

`docs/reflection-spec.md` §4 컨텍스트 주입 참조.
