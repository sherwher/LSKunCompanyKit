# 설계 — 외주 setup 자동 시퀀스 (ADR-0022)

> Phase 21. ADR-0022 (Multi-step CPO 시퀀스 결정론 강제 — 외주 setup 한정).
> 본 문서는 brainstorming + 3 전문가 점검 (architect/critic/security) 결과 전부 반영한 확정 설계.
> 사용자 결정: "Hook + 전문가 제안 보강 적용" (2026-05-28).
> 본 spec 은 plugin repo 의 spec. 저자 SSOT 위치는 박제하지 않음 (ADR-0009 §5).

---

## 0. 한 줄 요약

`/lskun-kit:external setup` 의 multi-step 시퀀스에서 LLM 이 중간에 turn 을 종료해
사용자가 매번 "계속" 입력으로 재가동해야 했던 두 프로젝트 재현 문제를, **PostToolUse +
Stop hook 이중 강제** (push) + **commands/external.md 본문 강화** (pull) 양 갈래로
결정론 보장. 단, hook 으로 못 푸는 `/clear` 강제 break 구간은 문서 명시 안내로
보완 (B1 해소).

---

## 1. 문제와 의사결정 맥락

### 1.1 사용자 호소 (사실)

두 프로젝트에서 같은 현상 재현:

1. `/lskun-kit:external setup <project>` 실행
2. CPO 가 도메인 워커 자문 Task 1회 dispatch → 완료
3. **CPO 가 "잘 정리해서 보고하고 다음 단계 안내" 로 turn 종료**
4. 사용자가 1분+ 침묵 후 "끊긴 거 아니야?" 입력해야 다음 step 진행

사용자 평가: "두 번 겪었으니 plugin 차원에서 해결되어야 함."

### 1.2 3 전문가 점검 합의

**architect:** Stop hook 의 `stop_hook_active` payload 미처리 시 무한 lockup. ADR-0014
폐기는 reflection 한정이지 hook event 자체가 아님 (재해석 명문화 필요).

**critic (REJECT 권고):** ADR-0018 ("실증 후 박제") 정신 위반. n=2 는 ADR-0016 의
"3회 실패 후 hook" 기준 미달. **가장 큰 실망 지점: step 3↔4 사이 `/clear` 강제
break 는 hook 으로 못 푼다** — PreToolUse 의 chain 차단 (ADR-0004 §8) 이 활성 워커
세션 중 Task dispatch 를 deny 하므로 사용자가 `/clear` 직접 입력해야 함.

**security (HIGH risk):** `.external-setup.json` 이 `sync-in` 으로 외부 mirror
유입 가능 → 악성 markdown 이 PostToolUse stdout 으로 LLM context 에 raw 주입 →
CPO 컨텍스트 오염 (C1, CRITICAL).

### 1.3 사용자 결재 결정 (2026-05-28)

"Hook + 전문가 제안 보강 전부 적용" — 즉 hook 메커니즘은 유지하되, BLOCKER 3건 +
MAJOR 3건을 spec 레벨에서 사전 차단.

---

## 2. ADR-0022 신규 결정

### 2.1 한 줄 정체성

> 외주 setup 같은 **multi-step CPO 시퀀스**는 marker 파일 존재 시 hook 이 turn
> 연속성을 강제한다. 단 hook 은 LLM push 만 담당하고, `/clear` 같은 사용자 액션이
> 본질적으로 필요한 break 는 문서로 pull 한다. ADR-0014 가 폐기한 것은 reflection
> 메커니즘이며, hook event(Stop/PostToolUse) 자체 도입은 허용된다.

### 2.2 forbidden-history.md 갱신 (supersede 명시)

기존 줄 (`forbidden-history.md:45`):
> ~~새 hook 으로 자동 reflection 박제 시도~~ — **ADR-0014 로 자연 폐기**.
> Stop / PostToolUse hook 도 제거됨 (P79-1).

→ ADR-0022 박제 시 다음으로 갱신:
> ~~새 hook 으로 자동 reflection 박제 시도~~ — **ADR-0014 로 자연 폐기**.
> ~~Stop / PostToolUse hook 도 제거됨 (P79-1)~~ — **ADR-0022 로 supersede**:
> reflection 메커니즘 폐기는 유지, hook event 자체 도입은 marker 파일 기반 좁은
> 트리거에 한해 허용.

### 2.3 새 금지 (ADR-0022 신규)

- Stop hook 의 `stop_hook_active=true` payload 무시 (무한 lockup)
- PostToolUse/Stop hook 에서 `.external-setup.json` 외 입력 (Task description/prompt
  내용 파싱) 으로 시퀀스 의도 추론 — forbidden-history.md:60 계승
- marker 파일 schema 의 enum 미강제 (자유 string 박제로 prompt 인젝션 표면 확장)
- marker 파일 wall-clock TTL 부재 (영구 stuck)
- escape hatch env var (`LSKUN_ALLOW_EXTERNAL_HALT`) 의 `.zshrc/.bashrc` 영구 export
- hook 의 trigger 범위 확장 (외주 setup 외 일반 dispatch 로 침투)

---

## 3. 아키텍처

### 3.1 양 갈래 메커니즘

**Push (hook):** marker 파일 존재 시 PostToolUse 는 다음 step 안내 주입, Stop 은
turn 종료 차단.

**Pull (문서):** `commands/external.md` 본문에 (a) "1턴 안에 모든 step 완수, 중간
사용자 응답 대기 금지", (b) "step 3 의 워커 세션 clear 가 필요한 시점은 사용자에게
명시 안내 (`/clear` 입력 요청) 후 자동 재개" 박제.

이 두 갈래로 사용자가 호소한 stuck 의 두 원인 (LLM 자율 종료 + `/clear` 강제 break)
을 양쪽 다 해소한다.

### 3.2 컴포넌트

```
사용자
   ↓ /lskun-kit:external setup <project>
CPO (메인 세션)
   ↓ external_setup_state.start(company, project)  ← marker 파일 생성
   ↓ Task dispatch (도메인 워커 자문)
PreToolUse hook (기존)        ← chain 차단 (ADR-0004 §8)
   ↓ allow (워커 세션 없음)
워커 Task 실행
   ↓ 완료
PostToolUse hook (신규)       ← marker 파일 존재 + stop_hook_active != true
   ↓ 다음 step 안내 stdout 주입 (CONTINUE 마커)
   ↓ allow
CPO 가 같은 turn 안에 다음 step 진행
   ↓ ...
   ↓ external_setup_state.finalize(company, project)  ← marker 파일 자동 삭제
                                                       (예: external/<project>/redteam 디렉토리 박혔는지 검사)
turn 정상 종료
Stop hook (신규)              ← marker 부재 또는 stop_hook_active=true → allow
   ↓ end
```

### 3.3 핵심 invariant

| Invariant | 보장 방법 |
|---|---|
| 일반 워커 dispatch 영향 0 | marker 파일 부재 시 두 hook 모두 즉시 allow + 종료 |
| 무한 lockup 불가 | `stop_hook_active=true` → 무조건 allow + marker auto-unlink |
| Wall-clock 영구 stuck 불가 | marker 의 `started_at` 24h 초과 시 hook 자동 unlink |
| Step count 폭주 불가 | `step_count_so_far` 가 `max_step_count` (=10) 초과 시 자동 unlink |
| 프롬프트 인젝션 불가 | `next_action`/`current_step` 은 enum allowlist 만 |
| 외부 mirror 신뢰 분리 | sync-in 이 `.external-setup.json` 발견 시 명시 confirm |
| CPO 결재권 보존 | hook 의 `blockReason` 문구는 "강제" 가 아니라 "CPO 다음 판단 step 이어서 수행" |
| escape hatch 항상 작동 | hook 최상단에서 env 검사, 다른 모든 가드보다 우선 |

---

## 4. 데이터 구조

### 4.1 Marker 파일 — `~/.lskun-companies/<company>/.external-setup.json`

```json
{
  "started_at": "2026-05-28T14:00:00+00:00",
  "company": "Acme",
  "project": "lskun-kit",
  "current_step": "fetch_advice",
  "next_action": "synthesize_brief",
  "step_count_so_far": 2,
  "max_step_count": 10
}
```

### 4.2 Enum allowlist (security C1 해소 — CRITICAL)

```python
_STEP_ENUM = frozenset({
    "init",              # external_setup_state.start() 직후
    "domain_assessment", # CPO 도메인 판단
    "hire_domain_worker",# 도메인 워커 자동 채용 (필요 시)
    "fetch_advice",      # 도메인 워커 자문 dispatch
    "synthesize_brief",  # brief.md 합성
    "dispatch_hr_lead",  # HR Lead 가 페르소나 박제
    "finalize",          # marker 삭제 직전
})
```

`current_step`/`next_action` 둘 다 위 enum 만 허용. 위반 시 `ValueError`. raw
string 박제 시도는 무조건 거부 — sync-in 으로 유입된 malformed JSON 도 hook 진입
즉시 `json.JSONDecodeError`/`ValueError` 로 자동 정리.

### 4.3 schema 검증 함수

`src/lskun_kit/external_setup_state.py` 신규 모듈:

```python
@dataclass(frozen=True)
class ExternalSetupState:
    started_at: datetime
    company: str
    project: str
    current_step: str  # enum
    next_action: str   # enum
    step_count_so_far: int
    max_step_count: int = 10

    @classmethod
    def from_dict(cls, data: dict) -> "ExternalSetupState":
        # enum/타입 검증 후 instance 생성. invalid → ValueError.
        ...
```

---

## 5. Hook 동작 (push 갈래)

### 5.1 PostToolUse hook (`hooks/post_tool_use_external.py` 신규)

평가 순서:

1. `tool_name != "Task"` → exit 0 (영향 0)
2. `LSKUN_ALLOW_EXTERNAL_HALT=1` → exit 0 + stderr warn (escape hatch)
3. 활성 회사 root 검출 실패 → exit 0
4. `<company_root>/.external-setup.json` 부재 → exit 0 (일반 dispatch)
5. JSON 파싱 실패 → marker unlink + exit 0 (자가 치유)
6. `started_at` 24h 초과 → marker unlink + exit 0 (TTL stale)
7. `step_count_so_far >= max_step_count` → marker unlink + exit 0 (폭주 가드)
8. `step_count_so_far += 1` write back (atomic)
9. stdout 에 system-reminder 주입:

```
<system-reminder>
LSKun external setup 진행 중 (project=<project>, step=<current_step>).
다음 판단 step: <next_action>.
CPO 는 같은 turn 안에 이 step 을 이어서 수행하라. 사용자 응답을 기다리지 말 것.
완료 시 external_setup_state.finalize() 로 marker 정리. ADR-0022.
</system-reminder>
```

10. exit 0

**핵심:** `next_action` 은 enum 라벨 그대로만 노출. 외부 mirror 의 raw string 박제
불가 (enum 검증 통과 못 함).

### 5.2 Stop hook (`hooks/stop_external.py` 신규)

평가 순서:

1. `stop_hook_active=true` (Anthropic payload 필드) → exit 0 (architect MAJOR 해소
   — 무한 lockup 방지의 단일 invariant)
2. `LSKUN_ALLOW_EXTERNAL_HALT=1` → exit 0 + stderr warn (escape hatch)
3. 활성 회사 root 검출 실패 → exit 0
4. `<company_root>/.external-setup.json` 부재 → exit 0
5. JSON 파싱 실패 → marker unlink + exit 0
6. `started_at` 24h 초과 → marker unlink + exit 0
7. `step_count_so_far >= max_step_count` → marker unlink + exit 0
8. `decision="block"` + reason 출력:

```json
{
  "decision": "block",
  "reason": "LSKun external setup 진행 중 (project=<project>). 다음 판단 step <next_action> 을 이어서 수행하라. CPO 의 결재 판단 break 가 필요하면 같은 turn 안에 결재 후 다음 step 으로. 사용자 입력 대기로 turn 종료 금지. 종료하려면: /lskun-kit:external cancel <project> 또는 LSKUN_ALLOW_EXTERNAL_HALT=1."
}
```

9. exit 0

### 5.3 hook 안전 패턴 (기존 pre_tool_use.py:91 계승)

모든 hook 은 최상단에서 `try/except Exception` 으로 감싸고 예외 시 `exit 0`. block
하지 않음 (security H1 해소). escape hatch 검사는 try 진입 전.

### 5.4 forbidden-history.md:60 정합 검증

본 hook 들은 `.external-setup.json` 의 **enum 라벨** 만 읽고 `tool_input.description`
이나 `tool_input.prompt` 는 절대 안 봅니다. enum allowlist 통과만 검증. ADR-0016 의
"prompt 내용 파싱 금지" 와 정합.

---

## 6. 문서 강화 (pull 갈래) — critic B1 해소

### 6.1 commands/external.md 본문 보강

기존 setup 시퀀스 (5 step) 의 문구를 다음과 같이 갱신:

```markdown
### setup <project> [--redteam] [--customers]

**시퀀스는 한 turn 안에 완수한다. 중간에 사용자 응답을 기다려 turn 을 종료하지 말 것.**
(ADR-0022 — PostToolUse + Stop hook 이 turn 연속성을 강제한다.)

1. CPO 가 프로젝트 도메인 판단.
2. 도메인 워커가 hired/ 에 부재면 자동 채용 (HR Lead dispatch).
3. CPO 가 도메인 워커를 1회 dispatch → 자문 수집.
   **이 step 끝나면 워커 세션 marker 가 살아있다. 다음 dispatch 전에 세션을 정리해야
   PreToolUse hook 의 chain 차단 (ADR-0004 §8) 을 통과한다.**
   - 정리는 (a) `session.clear(company_root)` 자동 호출 (구현 예정) 또는 (b) 사용자에게
     "`/clear` 입력 후 자동 재개됩니다" 1줄 안내. 어느 쪽이든 **CPO 가 turn 을 종료하지
     않는다 — Stop hook 이 block 한다.**
4. 자문을 brief.md 합성.
5. HR Lead dispatch → external/<project>/{redteam,customers}/ 페르소나 박제.
6. `external_setup_state.finalize()` 호출 → marker 자동 삭제.
```

### 6.2 사용자 안내 강화

setup 시작 시 CPO 가 사용자에게 1줄 안내:

> "외주 setup 자동 시퀀스 시작. 도중에 `/clear` 안내가 나오면 입력해주세요. 그 외엔
> 자동 진행됩니다 (보통 30~60초). 중단하려면 `/lskun-kit:external cancel <project>`."

---

## 7. lifecycle 관리 (critic MAJOR 해소)

### 7.1 marker 생성 — `external_setup_state.start(company, project)`

- `/lskun-kit:external setup` 진입 시 호출
- 기존 marker 존재 시 stale 체크 (24h 초과면 자동 unlink + 신규 박제, 미만이면 ValueError)
- atomic write (`tmp + os.replace`, `session.py` 패턴 재사용)

### 7.2 marker 갱신 — `external_setup_state.advance(company, project, next_step, next_action)`

- 각 step 시작 시 CPO 가 호출 (LLM 자율 — but enum allowlist 강제)
- `current_step` / `next_action` enum 검증
- atomic write

### 7.3 marker 삭제 — `external_setup_state.finalize(company, project)`

- 최종 step (`dispatch_hr_lead` 완료 후) CPO 가 호출
- atomic unlink
- audit entry `event_type="external_setup_completed"` 1줄 (단발 — ADR-0006 정합)

### 7.4 stale 자동 정리 (architect/critic MAJOR 해소)

- hook 들이 stale (24h 초과) 발견 시 자동 unlink (§5.1 평가 6, §5.2 평가 6)
- `/lskun-kit:doctor` 신규 항목 [33] — stale `.external-setup.json` 검출 (read-only).
  남아있으면 ℹ️ 표시 + 처리 안내. ADR-0006 정신 — 자동 평가/삭제 0.

### 7.5 cancel — `/lskun-kit:external cancel <project>`

- `.external-setup.json` atomic unlink
- audit entry `event_type="external_setup_cancelled"`
- 새 setup 즉시 가능 (cooldown 없음 — critic M2 의 cooldown 제안은 YAGNI, marker
  자체가 SSOT 라 race 없음)

---

## 8. sync-in 보안 보강 (security C1 — CRITICAL)

### 8.1 sync.py 가드

`sync.py` 의 `_walk_size` 단계에서 `.external-setup.json` 발견 시:
- `notes` 에 경고 append: "외부 mirror 의 .external-setup.json 발견 — 외주 setup
  진행 상태 파일. 인젝션 가능성 있음."
- 사용자 명시 confirm 추가 (기존 덮어쓰기 confirm 과 별도)
- 사용자가 거부 시 해당 파일만 skip 하고 나머지 sync 계속

### 8.2 enum allowlist (재강조)

`.external-setup.json` 의 모든 string 필드 (`current_step`/`next_action`/`company`/`project`)
는 **이미 존재하는 검증 함수** 통과 필수:
- `company` → `paths.validate_company_name()`
- `project` → `external.validate_project_name()` (dot 전면 금지)
- `current_step`/`next_action` → `_STEP_ENUM` allowlist

위반 시 무조건 ValueError → hook 이 marker unlink.

### 8.3 사용자 가시성 (security H2 해소)

`/lskun-kit:doctor` 신규 항목 [34] — `~/.zshrc`/`~/.bashrc`/`~/.zshenv`/`~/.profile`
에서 `LSKUN_ALLOW_EXTERNAL_HALT` grep, 발견 시 WARN. ADR-0017 결정 8 ([23]) 의
재사용 패턴.

---

## 9. 테스트 전략

### 9.1 신규 테스트 파일

- `tests/test_external_setup_state.py` — schema 검증, atomic write, stale TTL
- `tests/test_hooks_post_tool_use_external.py` — marker 부재/존재/stale/폭주/escape hatch/system-reminder 출력 형식
- `tests/test_hooks_stop_external.py` — `stop_hook_active=true` 무조건 allow/marker 부재 allow/stale unlink/block 시 reason 메시지
- `tests/test_hooks_manifest.py` 확장 — Stop/PostToolUse hook 등록 확인 (기존 `test_reflection_hooks_removed` 갱신: reflection 폐기는 유지, 외주 setup 한정 hook 허용)
- `tests/test_external_doctor_setup.py` — doctor [33] stale 검출, [34] env grep

### 9.2 회귀

- 기존 `test_hooks_manifest.py:32-35` 의 `test_reflection_hooks_removed` 를
  `test_only_external_setup_hooks_allowed_beyond_pre_tool_use` 같은 의도 명시 테스트로
  갱신. reflection 메커니즘 자체 폐기는 그대로 검증하되, 외주 setup 한정 hook 은 허용.
- 전체 unittest 무회귀.

---

## 10. ADR / 문서 박제

### 10.1 신규 ADR-0022

`docs/internals/adr-index.md` 끝에 행 추가:

```markdown
| ADR-0022 | **Multi-step CPO 시퀀스 결정론 강제 (외주 setup hook)** | 활성 (v0.28.0+, ADR-0021 보강 / ADR-0014 reflection 폐기와 분리 / forbidden-history.md:45 supersede — spec: `docs/superpowers/specs/2026-05-28-external-setup-auto-sequence-design.md`) |
```

Supersede chain 시각화에 추가:
```
forbidden-history.md:45 (P79 의 Stop/PostToolUse 폐기 표현) → ADR-0022 부분 supersede
```

### 10.2 forbidden-history.md 갱신

- `:45` 줄 갱신 (§2.2)
- ADR-0022 신규 금지 섹션 추가 (§2.3 의 6개 항목)

### 10.3 CLAUDE.md 갱신

- §1 Phase 21 / 0.28.0 갱신
- §1 slash command 표에 `/lskun-kit:external cancel` 행 추가 (subcommand)
- §6 금지 요약 1줄: "외주 setup hook 의 marker 외 입력 파싱 / stop_hook_active 무시 — ADR-0022"
- §8 로드맵 갱신
- doctor 항목 수 갱신 (+2: [33] [34])

### 10.4 plugin.json

`version: 0.27.0` → `0.28.0`.

---

## 11. 범위 (Phase 21)

**구현 (전부 한 PR):**
- `src/lskun_kit/external_setup_state.py` — schema + start/advance/finalize + stale TTL
- `src/lskun_kit/hooks/post_tool_use_external.py` — PostToolUse hook
- `src/lskun_kit/hooks/stop_external.py` — Stop hook
- `hooks/hooks.json` 갱신 — PostToolUse:Task / Stop 등록
- `commands/external.md` 보강 — setup 시퀀스 명시 + cancel 서브명령
- `src/lskun_kit/sync.py` — `.external-setup.json` 발견 시 confirm
- doctor 항목 [33][34] 추가
- ADR-0022 박제, forbidden-history 갱신, CLAUDE.md 갱신, plugin.json 0.28.0
- 전체 신규 테스트 5개 + manifest 갱신

**실증 (운영):**
- 구현 후 실제 외주 setup 실사용으로 검증 (사용자 두 프로젝트 + 추가 dogfood)
- 재발 시 ADR-0022 부록으로 root cause 박제

**제외 (YAGNI):**
- 일반화된 sequence-runner 프레임워크 (B 옵션 — critic 합의로 배제)
- LLM 자유 텍스트 next_action 필드 (security C1 위반)
- 외주 setup 외 다른 multi-step 시퀀스 hook 확장 (실증 후 별도 phase)
- audit log 위 자동 분석 (ADR-0006)
