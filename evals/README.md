# evals — plugin 행동 회귀 suite (ADR-0028)

`claude plugin eval` 용 케이스 모음. stdlib unittest 가 볼 수 없는 것 — hook 이 실제 Claude Code 에서
발화하는지, agent 도구 제한이 실제로 걸리는지, CPO persona 가 실제로 그렇게 행동하는지 — 를 확인한다.

**개발 도구다.** plugin 런타임은 이 디렉토리를 읽지 않는다 (ADR-0009). 점수는 plugin 변경의 회귀 신호로만
쓰고, 워커 · 회사 · audit 에 대한 KPI 로 쓰지 않는다 (ADR-0002 §5, ADR-0006).

## 실행

```bash
# 핵심 케이스 (Bash 권한 불필요)
claude plugin eval . --tag core --scaffold --allow-tools Agent Write Edit

# 전체 (결재 기록 케이스 포함 — Bash 샌드박스 필요)
claude plugin eval . --scaffold --allow-tools Agent Write Edit "Bash(lskun-audit *)"
```

- `--scaffold` 필수 — 각 케이스의 `fixture.sh` 가 임시 HOME 에 회사 `EvalCo` 를 만든다 (`_fixtures/company.sh`).
- 비용이 든다 (케이스 × runs × 2 arm). 빠른 확인은 `--runs 1 --ablation none --model sonnet`.
- 머신의 `~/.docker` 안에 심볼릭 링크가 있으면 Bash 권한을 준 실행이 통째로 거부된다 → `--tag core` 를 쓴다.

## 케이스

| 케이스 | 태그 | 확인하는 것 | 근거 |
|---|---|---|---|
| `session-context` | core, smoke, hooks | SessionStart hook 이 회사 · hired 목록을 주입 | ADR-0004 |
| `allowlist-deny` | core, hooks, guard | allowlist 외 `subagent_type` 이 deny 되고 사유가 새 타입을 안내 | ADR-0017, ADR-0026 |
| `worker-readonly` | core, agents, guard | `LSKunCompanyKit:worker` 로 dispatch 된 워커가 파일을 쓰지 못함 | ADR-0026 D1 |
| `embody-gate` | core, behavior, cpo | 게이트 미충족 순차 작업을 dispatch 없이 빙의로 수행하고 알림 1줄을 냄 | ADR-0025 D1 · D2 |
| `embody-audit` | behavior, cpo, bash | 빙의 작업 후 `lskun-audit record … --embody` 를 실행하려 함 | ADR-0027 |

## 케이스를 쓸 때 알아둘 것 (실측)

- eval 세션은 **workspace 의 지침 파일 (`CLAUDE.md` · `CLAUDE.local.md`) 을 로드하지 않는다.** CPO persona 가 필요한
  행동 케이스는 prompt 가 먼저 `./CLAUDE.local.md` 와 그 import 대상 (`hired/cpo.md`, ADR-0029) 을 Read 하도록
  요청한다 (persona 본문을 케이스에 복제하지 않는다).
- scaffold 의 `$HOME` 은 실행용 임시 HOME 과 같다 → `~/.lskun-companies/` fixture 가 hook 에 보인다.
- `env` 는 `EVAL_*` 키만 허용 — `LSKUN_SSOT_ROOT` 를 쓸 수 없으므로 회사 검출은 CLAUDE.md marker 경로로만 된다.
- `target: trace` 는 SessionStart 주입문과 Read 결과까지 포함한다. 워커 이름만 찾는 패턴은 항상 통과한다 →
  모델이 직접 말해야만 나오는 조합 (`Bora Eval…관점으로 직접 수행`) 으로 좁힌다.
- 과제가 너무 작으면 CPO 가 "직접 응답 조건" 을 적용해 빙의 자체를 건너뛴다 (올바른 행동). 빙의를 보려면
  여러 파일에 걸친 순차 작업을 준다.
- `tool_used` 는 권한이 없어 모델에게 제공되지 않은 도구의 호출을 셀 수 없다.
