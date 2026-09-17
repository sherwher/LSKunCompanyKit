# P129 — Worker Agent: 도구 권한으로 쓰기 단일화·chain 금지 강제 (ADR-0026, v0.34.0)

> 결정 본문 SSOT 는 ADR-0026 (저자 vault). 본 문서는 plugin repo 측 구현 spec.

## 1. 문제

ADR-0025 D3 (dispatch 워커는 read-only 기여, 쓰기는 CPO 단일 스레드) 는 persona 지시뿐이었다.
ADR-0025 는 도구 수준 강제를 "Task tool 하위 도구 제어 불가 — 구현 불가" 로 비채택했다.
forbidden-history 의 교훈 ("프롬프트만으로 차단 재시도 3회 실패 — hook 레벨 강제 필수") 대로,
프롬프트 의존 규칙은 이 프로젝트에서 반복 실패해 왔다.

## 2. 실측 (Claude Code v2.1.274, 일회용 probe plugin)

| 확인 항목 | 결과 |
|---|---|
| plugin `agents/<name>.md` | `<plugin>:<name>` 타입으로 등록 |
| `disallowedTools: Write, Edit, NotebookEdit` | subagent 도구 목록에서 제거됨, 파일 생성 실패 |
| `model: inherit` | 메인 세션 모델 상속. 호출 시 model 지정이 우선 |
| hook payload | subagent 내부 호출에만 `agent_id` / `agent_type` 실림 (메인 세션은 null) |
| 기본 subagent | `Agent` 도구 보유 (중첩 dispatch 가능) — `disallowedTools` 로 제거 가능 |
| plugin agent 제약 | `hooks` / `mcpServers` / `permissionMode` frontmatter 무시 |

## 3. 결정 (D1~D6)

- **D1** `agents/worker.md` — `disallowedTools: Write, Edit, NotebookEdit, Agent`, `model: inherit`. 본문은 역할 경계만, JD 는 dispatch prompt 로.
- **D2** `agents/hr-lead.md` — `disallowedTools: Agent`. 쓰기 허용 (ADR-0020 skill 파일, ADR-0023 채용 파일).
- **D3** allowlist = `{LSKunCompanyKit:worker, LSKunCompanyKit:hr-lead}` (ADR-0017 결정 1 supersede). `claude` 는 유예 없이 deny, 사유가 새 타입 안내.
- **D4** chain 차단 이중화 — 도구 제거 + hook 의 `agent_id` 판정. 세션 파일 판정은 직통 경로용으로 유지.
- **D5** 외주 consult = worker agent, 외주 구성 = hr-lead agent.
- **D6** doctor [38] agent 등록 점검, forbidden 6항.

## 4. hook 평가 순서 (변경분)

```
1~4. (변경 없음) dispatch tool 아님 / chain bypass / allowlist bypass / 회사 marker 부재 → allow
5.   payload 에 agent_id 존재 → chain deny (신규, ADR-0026 D4)
     활성 워커 세션 존재 → chain deny (기존)
6.   subagent_type 미지정 → allow (변경 없음)
7.   subagent_type ∈ {LSKunCompanyKit:worker, LSKunCompanyKit:hr-lead} → allow (교체)
8.   fallthrough → deny (사유에 새 타입 2종 안내)
```

## 5. 비채택

hook 기반 Write 차단 (예외 경로 하드코딩 + 도구가 보인 채 거부되어 재시도 토큰 낭비) /
`claude` 유예 기간 / 워커별 agent 파일 동적 생성 (SSOT 혼합, reload 필요) / `memory:` 필드 /
`tools:` allowlist 방식 (MCP·WebFetch·Skill 차단) / worker 에서 Bash 제거.

## 6. 알려진 한계

- Bash 경유 쓰기는 막지 못한다. persona 규칙 + 결재 R2 (산출물 원본 확인) 가 담당.
- `subagent_type` 미지정 호출은 계속 allow (ADR-0017 결정 유지).
- escape hatch 활성 시 전체 우회 (의도된 동작, doctor [23]).

## 7. 적용 지점

- `agents/worker.md`, `agents/hr-lead.md` (신설)
- `src/lskun_kit/hooks/pre_tool_use.py` — allowlist 교체, `agent_id` chain 판정, deny 사유
- `src/lskun_kit/templates/{cpo,hr-lead}.md`, `commands/{work,external}.md`, `src/lskun_kit/routing.py` — dispatch 타입 안내
- `commands/doctor.md` [38], `docs/internals/{forbidden-history,adr-index,phase-roadmap}.md`, `CLAUDE.md` §1·§2.2·§6
- tests: `test_plugin_agents.py` (12), `test_p129_worker_agent_docs.py` (3), `test_hooks_pre_tool_use.py` (+6)

## 8. 검증

- stdlib unittest 490 OK
- 실제 세션 (`claude -p --plugin-dir <repo>`, `LSKUN_SSOT_ROOT` 지정):
  `claude` deny + 안내 문구 / worker agent 도구 목록에 Write·Agent 없음·파일 미생성 /
  hr-lead agent Write 성공·Agent 없음

## 9. 마이그레이션

1. plugin update → v0.34.0, 세션 재시작 또는 `/reload-plugins` (`agents/` 는 live reload 대상 아님)
2. `/lskun-kit:sync-persona --execute`
3. 일반 워커 JD 변경 불필요
