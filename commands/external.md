---
name: lskun-kit:external
description: 프로젝트별 외주(레드팀·고객) 구성/청취 — CPO 단독 dispatch (ADR-0021)
arguments:
  - name: subcommand
    description: setup | list | consult
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

HR Lead 를 통해 외주를 박제한다. 구성 시퀀스 (CPO 주도):

1. 프로젝트 도메인 판단 → 도메인 워커가 `hired/` 에 있는지 확인.
2. 없으면 기존 자동 채용 (HR Lead dispatch) 으로 도메인 워커 먼저 채용.
3. 도메인 워커를 1회 dispatch → 프로젝트 위험·경쟁구도·급소·타깃 고객 자문 수집.
   **이 워커 세션이 종료(clear)된 뒤** 다음 단계로 진행. PreToolUse hook 이
   활성 워커 세션 중 Task 호출을 deny 하므로 반드시 세션 clear 후 CPO 단독 dispatch.
4. 자문을 brief.md (`external/<project>/brief.md`) 에 합성 (`brief_path`).
5. HR Lead 를 `Task(subagent_type="claude", ...)` 로 dispatch — `templates/redteam.md`,
   `templates/customer.md` (외주 template, `lskun_kit.external.external_template_path`
   로 경로 도출) 기반으로 페르소나를 `external/<project>/{redteam,customers}/` 에 박제.
   - 고객 인원수: brief 기반 CPO 판단, **최대 7명**. 서로 다른 정성 렌즈 1개씩 (페르소나 다양성).
   - 박제는 `lskun_kit.audit_external.record_external_onboard` 로 audit 기록
     (event_type=`onboard_external`).

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
