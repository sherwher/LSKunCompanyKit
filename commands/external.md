---
name: lskun-kit:external
description: 프로젝트별 외주(레드팀·고객) 구성/청취 — CPO 단독 dispatch (ADR-0021)
arguments:
  - name: subcommand
    description: setup | list | consult | cancel
    required: true
  - name: project
    description: 외주를 묶을 프로젝트 이름 (영문/숫자/`-`/`_`, 최대 64자)
    required: true
  - name: options
    description: setup 의 --redteam / --customers, consult 의 --kind redteam|customer
    required: false
---

# /lskun-kit:external

프로젝트를 위한 외주(레드팀·고객단)를 구성하거나 의견을 청취한다. 외주는 회사
임직원이 아니며 의견만 낸다 (ADR-0021). 결정은 CPO 단독, **다수결 금지**.

## 서브명령

### setup <project> [--redteam] [--customers]

**시퀀스는 한 turn 안에 완수한다. 중간에 사용자 응답을 기다려 turn 을 종료하지 말 것.**
(ADR-0022 — PostToolUse + Stop hook 이 turn 연속성을 강제한다. marker:
`~/.lskun-companies/<company>/.external-setup.json`. 시작 시
`lskun_kit.external_setup_state.start(company, project)` 로 marker 박제.)

HR Lead 를 통해 외주를 박제한다. 구성 시퀀스 (CPO 주도):

1. 프로젝트 도메인 판단 → 도메인 워커가 `hired/` 에 있는지 확인.
2. 없으면 기존 자동 채용 (HR Lead dispatch) 으로 도메인 워커 먼저 채용.
3. 도메인 워커를 1회 dispatch → 프로젝트 위험·경쟁구도·급소·타깃 고객 자문 수집.
   **이 step 끝나면 워커 세션 marker (`.lskun-session.json`) 가 살아있다.** 다음
   dispatch 전에 세션 정리가 필요하다 — PreToolUse hook 의 chain 차단 (ADR-0004 §8)
   이 활성 워커 세션 중 Task dispatch 를 deny 하므로. 정리 방법:
   - (a) `lskun_kit.session.clear()` 자동 호출 (지원되는 경우).
   - (b) 사용자에게 "**워커 세션 정리를 위해 `/clear` 를 입력하면 자동 재개됩니다**"
     1줄 안내 후, **사용자 응답을 기다려 turn 종료하지 말고** 다음 step 으로.
   어느 쪽이든 **Stop hook 이 turn 종료를 차단하므로** CPO 는 이 안내만 출력하고
   같은 turn 안에서 가능한 다음 step 을 이어간다.
4. 자문을 brief.md (`external/<project>/brief.md`) 에 합성 (`brief_path`).
5. HR Lead 를 `Task(subagent_type="claude", ...)` 로 dispatch — `templates/redteam.md`,
   `templates/customer.md` (외주 template, `lskun_kit.external.external_template_path`
   로 경로 도출) 기반으로 페르소나를 `external/<project>/{redteam,customers}/` 에 박제.
   - 고객 인원수: brief 기반 CPO 판단, **최대 7명**. 서로 다른 정성 렌즈 1개씩 (페르소나 다양성).
   - 박제는 `lskun_kit.audit_external.record_external_onboard` 로 audit 기록
     (event_type=`onboard_external`).
6. 완료 시 `lskun_kit.external_setup_state.finalize(company)` 호출 → marker 자동 삭제.

시작 시 CPO 는 사용자에게 다음 1줄 안내한다:
> "외주 setup 자동 시퀀스 시작 (project=<project>). 도중에 `/clear` 안내가 나오면
> 입력해주세요. 그 외엔 자동 진행됩니다 (보통 30~60초). 중단하려면
> `/lskun-kit:external cancel <project>` 또는 `LSKUN_ALLOW_EXTERNAL_HALT=1`."

### cancel <project>

진행 중인 외주 setup 을 중단한다. `lskun_kit.external_setup_state.cancel(company)`
로 marker 파일을 atomic unlink + audit entry 박제
(`event_type="external_setup_cancelled"`). 새 setup 즉시 가능.

긴급 중단이 필요하면 env var: `export LSKUN_ALLOW_EXTERNAL_HALT=1` (세션 단위만,
`.zshrc` 영구 export 는 doctor [34] 가 검출).

### list <project>

`external/<project>/` 의 구성된 레드팀·고객 목록을 read-only 표시.
`lskun_kit.external.list_external_personas(company, project, kind)` 사용.

### consult <project> [--kind redteam|customer]

**워커 세션이 종료된 상태에서만** CPO 가 외주를 각각 `Task` dispatch (반드시
`subagent_type="claude"`, ADR-0017 Allowlist).

- 각 외주 body 는 `lskun_kit.external_context.build_external_context(kind, body)` 로
  **untrusted fence 격리** 주입 (security H1 — prompt injection 방어).
- 외주 dispatch context 는 해당 project 의 brief + 본인 페르소나만 (`hired/` JD
  미주입, 타 프로젝트 external 미주입 — 데이터 격리 security H3).
- 수집된 의견을 CPO 가 종합 판단. 외주 의견은 참고 데이터, 결정은 CPO 단독.
- 자문 사실은 CPO 결재 entry 의 `reason` 필드에 산문으로만 기록 (별도 집계
  필드/대시보드 금지 — ADR-0006 정신, spec §5.4 경량안).

## dispatch 강제 (ADR-0017 정합)

외주 dispatch 도 워커 dispatch 와 동일하게 `subagent_type="claude"` 만 허용.
`description` 포맷 = `<외주명·kind · 작업요약>` (예: `r1·redteam · 보안 비평 청취`).

## 금지 (ADR-0021)

- 워커 세션 활성 중 외주 dispatch — PreToolUse hook deny. 세션 clear 후 필수.
- 외주 의견의 다수결 / 퍼센트 / 시계열 집계 (고객 ≤ 7명, 정성 다양성만).
- 레드팀의 파일 삭제 / exploit 실행 (텍스트 비평만).
- 워커 → 외주 직접 chain (CPO 단독 호출, sub-leader 출현 방지).
- 외주 JD 의 자동 진화 (ADR-0014 — JD only, time-invariant).
