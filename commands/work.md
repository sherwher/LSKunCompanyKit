---
name: lskun-kit:work
description: 워커 호출 — JD 컨텍스트 주입 + 세션 활성화. 워커 이름 생략 시 메인 세션 = CPO 가 직접 라우팅·자동 채용·결재 수행 (ADR-0014)
arguments:
  - name: worker
    description: 호출할 워커 이름. 생략 시 메인 세션의 CPO persona 가 처리
    required: false
  - name: request
    description: 사용자 요청 본문
    required: false
  - name: model
    description: 워커 dispatch 모델 override ("sonnet" / "opus" / 모델 ID). 생략 시 워커 frontmatter.model → CPO 동적 판단 → default(sonnet)
    required: false
---

# /lskun-kit:work

워커를 활성화하고 JD (persona body) 를 컨텍스트로 주입한다. ADR-0014 (2026-05-22) — 워커 history 주입 폐기, JD only.

## 분기

| 호출 형태 | 동작 |
|---|---|
| `/lskun-kit:work backend-engineer "..."` | **직통 호출.** 메인 세션 (CPO persona) 이 결재 생략하고 워커 직통 dispatch. cheap path. |
| `/lskun-kit:work cpo "..."` | CPO 와 직접 전략 대화 (CPO 가 워커 dispatch 안 하고 직접 응답). |
| `/lskun-kit:work hr-lead "..."` | HR Lead 직접 호출 (해고 명시 요청용). |
| `/lskun-kit:work "..."` (워커 이름 생략) | **메인 세션 = CPO** 가 받아 라우팅 → 결재 → 응답. 부재 워커 시 자동 채용. |

## 동작

### 직통 (워커 이름 명시)

1. 활성 backend 결정 (`/hire` 와 동일 규칙)
2. **dispatch 가드 (ADR-0019)** — 옛 ADR-0015 결정 7-E (archived 가드) 폐기. `build_worker_context` 가 hired 부재 시 `WorkerNotFoundError` 만 raise. caller (LLM) 가 사용자에게 다음 메시지 출력 후 중단:
   ```
   [Skill 실패] worker '<name>' not found in hired/.
   재채용은 /lskun-kit:work hr-lead "<role> 신규 채용" 으로 진행하세요.
   ```
   **Task tool 우회 / fallback 금지** (ADR-0015 결정 3-A 정합).
3. `lskun_kit.context.build_worker_context(adapter, <worker>)` 호출 → JD 컨텍스트 주입 (ADR-0014 — history 섹션 주입 폐기)
4. `lskun_kit.session.start(<root>, <worker>)` 호출 → 세션 파일 작성
5. `--model` 옵션이 있으면 해당 모델로 dispatch; 없으면 워커 frontmatter `model` → default(`sonnet`)
6. 사용자가 자유롭게 일을 시킨다.

### 메인 세션 CPO 라우팅 (워커 이름 생략)

1. 메인 세션은 **이미 CPO persona** 로 동작 중 (CLAUDE.md 박제 + SessionStart hook 으로 활성 회사 컨텍스트 주입)
2. CPO 가 요청을 받아:
   - `hired/` 워커 검색 (frontmatter 의 `role`, `domain` 기준)
   - 적합 워커 있음 → `Task` tool 로 dispatch — **반드시 `subagent_type="claude"`** (ADR-0017 결정 1 — Allowlist). model 결정 = frontmatter / CPO 판단 / default.
   - 없음 → `Task(subagent_type="claude", ...)` 로 HR Lead 호출 → 자동 채용 → `[채용 알림]` 1줄 → 신규 워커 dispatch
3. CPO 가 워커 보고를 받아 **결재** (자가 평가 통과 → 승인 / 재작업 최대 2회)
4. CPO 결재 audit 박제 (`audit.record`, ADR-0006)
5. 사용자에게 결재된 결과 전달

> 자동 채용은 **사용자 알림만** — 차단 없음. 해고만 사용자 명시 요청 필수.

> **dispatch 강제 (ADR-0017)**: Task tool 호출 시 반드시 `subagent_type="claude"`. OMC executor / general-purpose / 외부 plugin subagent (vercel/codex/figma 등) / Explore / Plan 호출은 PreToolUse hook 이 deny. 회사 외 작업으로 다른 plugin subagent 가 정당 필요하면 세션 단위로 `export LSKUN_ALLOW_NON_CLAUDE_DISPATCH=1` 후 사용 (`.zshrc`/`.bashrc` 영구 export 금지, doctor [23] 가 검출).

## 사용 예

```bash
# CPO 라우팅 (default, 자동 채용 포함)
/lskun-kit:work "병원 EMR 의 환자 검색 API 만들어줘"

# 직통 + Opus override
/lskun-kit:work security-architect "OAuth flow 리뷰" --model=opus

# CPO 와 전략 대화
/lskun-kit:work cpo "이번 분기에 어떤 워커가 더 필요해?"

# HR Lead 명시 호출 (해고)
/lskun-kit:work hr-lead "alice 해고 — 사유=role 중복"
```

## 사양

- CPO 호출 — 워커 이름 생략 시 메인 세션의 CPO 가 받음
- Leader-Worker dispatch — Task tool + 보고 양식 + `subagent_type="claude"` 강제 (ADR-0017)
- 자동 채용 — 사용자 알림만, 차단 X
- 모델 라우팅 — 워커 default=sonnet, override=opus
- Dispatch allowlist — `claude` 외 subagent 는 PreToolUse hook 이 deny (ADR-0017). escape hatch=`LSKUN_ALLOW_NON_CLAUDE_DISPATCH=1` (별칭 `LSKUN_ALLOW_OMC_FALLBACK=1`).

## Python 진입점

```python
from lskun_kit.routing import decide_target, build_cpo_routing_context
from lskun_kit.context import build_worker_context
from lskun_kit import session, LocalAdapter
from lskun_kit.errors import WorkerNotFoundError

# ADR-0015 — 회사 이름으로 adapter 생성 (~/.lskun-companies/<name>/)
adapter = LocalAdapter.from_company_name("LSKun")
decision = decide_target(adapter, requested_worker=None)
# ADR-0019 — archived 가드 폐기. hired 부재 시 후속 build_worker_context 가
# WorkerNotFoundError raise. fallback 금지 (ADR-0015 결정 3-A 유지).

if decision.mode == "direct":
    ctx = build_worker_context(adapter, decision.target_worker)
elif decision.mode == "cpo":
    # 메인 세션이 이미 CPO 인 경우 본 컨텍스트는 보조용:
    ctx = build_cpo_routing_context(adapter, user_request="...")
else:  # missing-cpo
    print(decision.reason)

# dispatch 직전 (ADR-0017 결정 1 — subagent_type="claude" 강제).
# Task tool 호출은 host (메인 LLM) 측이므로 plugin core 가 직접 호출하지 않는다.
# 호출자는 반드시 다음 형식으로 dispatch:
#
#   Task(
#       subagent_type="claude",   # Allowlist 단일 허용 — claude 외는 PreToolUse hook 이 deny
#       prompt=f"{ctx}\n\n{user_request}",
#       description="<short>",
#   )
#
# `subagent_type` 을 OMC executor / general-purpose / vercel:* / codex:* / Explore / Plan
# 등으로 지정하면 hook 이 deny + stderr 안내. 회사 외 작업 의도면:
#   export LSKUN_ALLOW_NON_CLAUDE_DISPATCH=1
# 세션 단위 권장 (.zshrc/.bashrc 영구 export 금지, doctor [23] 가 검출).
```
