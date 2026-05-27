# Phase Roadmap (역사 기록)

> 본 문서는 LSKunCompanyKit 의 Phase 1~18 진행 기록. CLAUDE.md 의 §8 에서 분리 (P109-C, 2026-05-27).
> 정보 손실 0 — 단순 위치 이동.

## 8. 로드맵

### Phase 15 (P83~P93 — Local SSOT 단일화 + Sync 분리 + 권한 박제 + 워커 해고 결합 해제, ADR-0015, 0.19.0)

```
P83 ✅ ADR-0015 박제 (4 전문가 만장일치 + 사용자 confirm)
P84 ✅ 기존 vault 사용자 마이그레이션 가이드 박제 (README §"사용 흐름 0)")
P85 ✅ adapters/vault.py + migration.py + tests 폐기 (commit 8b856e8, -938 LoC)
       — plugin core 의 vault 직접 참조 영구 차단
P86 ✅ paths.py 신규 + LocalAdapter.from_company_name (commit e143e24, +345 LoC)
       — ~/.lskun-companies/<name>/ 단일 진입점
       — 회사명 검증 (영문/숫자/_/-/. + 시작 영문/숫자, .backups 예약어)
P87+P88 ✅ init.py 멱등성 4행 + hook marker-based 통일 (commit d85a948, +685/-392 LoC)
       — ConfirmRequired 패턴 (옵션 B — plugin core 가 stdin 안 잡음)
       — CLAUDE.md marker 가 회사-프로젝트 결합의 단일 진실원
       — LSKUN_VAULT env / cwd .company/ 탐색 완전 폐기
P89 ✅ permissions.py 신규 (commit 587c6fa, +412 LoC)
       — ~/.claude/settings.json 의 permissions.allow 에 5개 패턴 자동 박제
       — atomic-ish write (.lskun-tmp → rename), 기존 항목 보존
P90 ✅ sync-in / sync-out 명령 + sync.py 신규 (commit a0a6d7f, +695 LoC)
       — shutil.copytree 만 사용, 외부 SDK 0
       — 백업 위치 분리 (sync-in: ~/.lskun-companies/.backups/, sync-out: target sibling)
P91 ✅ CPO templates 의 Skill 경유 강제 (commit 9537430, +32 LoC)
       — Task tool 의 oh-my-claudecode:* / general-purpose fallback 영구 금지
P93 ✅ 워커 해고 결합 해제 (commit e598097, +240 LoC)
       — WorkerArchivedError + archive_worker(archived_at, archived_reason)
       — routing.py 의 archived 가드 (결정 7-E)
       — doctor 진단 신규 2종 (display_name 중복, audit dangling)
       — display_name 결합 해제 박제 (역사 자산 불변)
P92 ✅ docs 일괄 갱신 + version 0.19.0 (본 phase)
```

핵심 결정: Plugin core 가 회사 자원의 물리적 위치를 결정하는 유일한 모듈 = `paths.py`. 1 회사 N 프로젝트 공유 가능. Vault 통합은 사용자 명시 sync 명령으로만. 폐기 9종 (결정 1-A / 1-B / 2-A / 3-A / 5 정책 / 6 / 7-B/7-C/7-D/7-E) 모두 박제됨.

215 → 227 tests (+12), 회귀 0.

### Phase 17 (P100~P105 — Dispatch subagent_type Allowlist, ADR-0017, 0.21.0)

```
P100 ✅ ADR-0017 박제 — 사용자 단독 결재 (4 전문가 만장일치 시뮬레이션, "정석으로 완벽하게 해결" 지시)
       — 4회째 재발 사실 박제 (LSKun 본진 세션, 2026-05-26)
       — 9 결정 + 인지된 잔존 위험 5건 + 2축 방어 권고
       — ADR-0016 supersede (메커니즘 계승, 정책 갱신: denylist → allowlist)
P101 ✅ pre_tool_use.py 구현 변경 (ADR-0017 결정 1, 2, 7)
       — _OMC_BLOCK_PREFIXES / _OMC_BLOCK_EXACT 제거
       — _ALLOWED_SUBAGENT = frozenset({"claude"}) 신설
       — escape hatch 2개 (LSKUN_ALLOW_NON_CLAUDE_DISPATCH 신규 + LSKUN_ALLOW_OMC_FALLBACK 별칭)
       — 평가 순서 7 → 8단계 (claude 정식 + fallthrough deny)
P102 ✅ tests/test_hooks_pre_tool_use.py 확장 (ADR-0017 결정 9)
       — 기존 7 + 갱신 10 (Explore/Plan/외부 plugin allow → deny) + 신규 8 = 25 케이스
       — 전체 회귀: 243 → 251 tests, 회귀 0
P103 ✅ Skill 문서 + persona template 박제 (ADR-0017 결정 4, 5)
       — commands/work.md §"메인 세션 CPO 라우팅" / §사양 / §"Python 진입점"
       — templates/cpo.md §"Task tool 로 워커 dispatch" + §"폐기·금지"
       — templates/hr-lead.md §채용
       — 모두 subagent_type="claude" 강제 + escape hatch 안내
P104 ✅ doctor [22] [23] 추가 (ADR-0017 결정 8)
       — [22] Dispatch allowlist 가드 활성 (_ALLOWED_SUBAGENT / ENV_ALLOW_NON_CLAUDE / ADR-0017 marker)
       — [23] LSKUN_ALLOW_NON_CLAUDE_DISPATCH / LSKUN_ALLOW_OMC_FALLBACK 영구 export 검출
       — 진단 항목 21 → 23
P105 ✅ docs + version bump 0.20.0 → 0.21.0 (본 phase)
       — plugin.json, CHANGELOG 0.21.0 항목, CLAUDE.md §1/§7/§8/§6 갱신
       — feedback_worker_dispatch_via_lskun_kit.md 메모리 정정 (denylist → allowlist)
```

핵심 결정: ADR-0016 의 denylist 한계가 4회째 재발로 입증. Allowlist 단호 전환으로 4회 패턴 종결. Skill 문서 미규정 = 4회 재발의 근본 원인 → 문서 박제로 정책 시정. Blast radius (외부 plugin subagent 함께 차단) 는 escape hatch 2개로 통제.

243 → 251 tests (+8 신규, 갱신 10 케이스 기대값 반전), 회귀 0.

### Phase 16 (P95~P99 — 메인 세션 측 OMC fallback 차단, ADR-0016, 0.20.0)

```
P95 ✅ ADR-0016 박제 (4 전문가 만장일치 보완 후 승인 — architect / critic / analyst / planner)
       — 3회째 재발 사실 박제 (technicianAPP 세션, 2026-05-26)
       — 9 결정 + 인지된 잔존 위험 5건 + 2축 방어 권고
P96 ✅ pre_tool_use.py 가드 분기 추가 (ADR-0016 결정 1, 2, 3, 4, 5, 7)
       — `_OMC_BLOCK_PREFIXES` (oh-my-claudecode:) + `_OMC_BLOCK_EXACT` (general-purpose)
       — `LSKUN_ALLOW_OMC_FALLBACK=1` escape hatch + stderr 경고
       — `LSKUN_HOOK_DEBUG_DUMP=1` 실측 모드 (구현 phase 첫 작업, 실측 후 unset)
       — marker 검출 2층 (env var O(1) / session_start 재사용 fallback)
       — 평가 순서 7단계 명문화 (chain 차단 > OMC 차단)
P97 ✅ tests/test_hooks_pre_tool_use.py 확장 (ADR-0016 결정 9)
       — 기존 7건 + 신규 10건 = 17 tests 통과
       — `_task_payload(subagent_type)` helper 신규
       — 와일드카드 매칭 / 외부 plugin 허용 / chain 우선순위 모두 검증
P98 ✅ doctor [20] [21] 추가 (ADR-0016 결정 8)
       — [20] OMC fallback 가드 활성 검증 (pre_tool_use.py 상수 + ADR-0016 주석 + 버전 ≥ 0.20.0)
       — [21] shell profile 의 LSKUN_ALLOW_OMC_FALLBACK 영구 export 검출
       — 진단 항목 17개 → 21개 (CLAUDE.md, doctor.md 헤더 갱신)
P99 ✅ docs + version bump 0.19.0 → 0.20.0 (본 phase)
       — plugin.json, CHANGELOG 0.20.0 항목, CLAUDE.md §1/§7/§8/§6 갱신
```

핵심 결정: ADR-0015 결정 3-A 의 plugin core 측 차단을 호출자 측으로 확장. 메인 LLM 의 자의적 Agent → OMC executor dispatch 가 hook 레벨에서 deterministic 차단. 메모리·text instruction 만으로 LLM 행동 강제하던 패턴 종결.

233 → 243 tests (+10), 회귀 0.

### Phase 14 (P78~P82 — Reflection 메커니즘 폐기, ADR-0014 박제)

```
P78 ✅ ADR-0014 박제 + CLAUDE.md/README/plugin.json/marketplace.json/hub 정체성 동기화
       (commit e8dcbde + 63c5c3e + 12c3c40)
P79 ✅ 코드 + tests 제거 (5 sub-commit, 274 → 215 tests, 순 -2316 LoC)
       - P79-1+2: reflection.py / audit_diagnostics.py / Stop hook / PostToolUse hook
                  / HistoryEntry / append_history ABC / context.py 재작성
       - P79-3:   routing.py history tie-break + org.py h=N 카운트
       - P79-4a:  templates/cpo.md + hr-lead.md 재작성 (JD-driven)
       - P79-4b:  commands + docs (work/sync-persona/doctor/migrate-schema/hire/org)
       - P79-5:   migrate-schema 의 legacy `## Project History` →
                  `## Archived History (pre-0.18)` rename + tests
P80 ✅ docs: CLAUDE.md §3/§5/§6/§7/§8 + README ADR 참조 표 갱신 (본 phase)
P81 ❌ Dogfooding 실측 — 폐기 (ADR-0002 §5 + ADR-0014 정책. analyst 4차 정량
       에서 "측정 시도 자체가 정책 위반" 명시. LSKun 사용자 자연 사용으로 위임)
P82 - version 0.18.0-dev → 0.18.0 + 8 commit push (사용자 confirm 게이트)
```

핵심 결정: 워커 = 채용 시 완성형 (time-invariant JD). 자산 = JD only (정적 단일 차원).
회사 성장 = 인원 추가 + 도메인 확장.

### Phase 1 (P0~P7 완료, P8/P9 폐기 by ADR-0002)

```
P0~P7 ✅ ADR-0001 → manifest → storage adapter → reflection → migration
P8/P9 ❌ Dogfooding / KPI 측정 — 폐기 (ADR-0002 §5)
```

### Phase 2 (P10~P16 완료)

```
P10 ✅ ADR-0002 박제
P11 ✅ CLAUDE.md 갱신
P12 ✅ CPO / HR 워커 템플릿
P13 ✅ /lskun-kit:init
P14 ✅ /lskun-kit:work 라우팅
P15 ✅ /lskun-kit:doctor 갱신
P16 ✅ README 갱신
```

### Phase 3 (완료)

```
P17 ✅ ADR-0003 박제 (도메인 인지 워커)
P18 ✅ ADR-0003 코드 (domain 필드 + CPO 라우팅 0단계)        (#12)
P21 ✅ ADR-0004 박제 (메인 세션 = CPO, Leader-Worker)
P22 ✅ display_name + model 필드                            (#13)
P23 ✅ init 인터뷰 + CLAUDE.md inline CPO persona 박제       (#14)
P24 ✅ SessionStart hook 으로 활성 회사 dynamic context 주입 (#15)
P25 ✅ CPO/HR persona 본문 재작성 (Leader-Worker dispatch)   (#16)
P26 ✅ 모델 라우팅 + hire/work --model --domain 옵션        (#17)
P27 ✅ README / CLAUDE.md / docs 갱신 + version bump        (본 PR)
P28 - 일상 사용. KPI 검증 없음 (ADR-0002 §5 정책 유지).
```

### Phase 13 (P77 — `/org` env var 의존 제거 + plugin install 단일성 진단)

```
P77 ✅ P74/P75 잔존 결함 (`$CLAUDE_PLUGIN_ROOT` 미주입 → canonical 1줄 실패
       → LLM 이 plugin install 경로 hardcode → 옛 버전 16개 누적 → 매번 다른
       버전 선택) 의 근본 해결.

       표면 증상: env 미주입 환경에서 `python3 "$CLAUDE_PLUGIN_ROOT/.../cli_org.py"`
       가 `python3 "/src/.../cli_org.py"` 로 빈 변수 expand → 파일 없음 → LLM
       이 fallback 으로 `~/.claude/plugins/cache/.../<version>/...` 을 매번
       다르게 hardcode (P74 의 hardcode 금지 박제로도 차단 실패).

       근본 원인: P75 의 self-bootstrap 은 `sys.path` 만 보정. **파일 경로 자체**
       를 못 찾으면 무용. canonical 1줄이 `$CLAUDE_PLUGIN_ROOT` env var 라는
       외부 계약에 의존하는데, Claude Code 가 활성 plugin 1개에만 env 를 set
       하는 환경 다수 (실측: CLAUDE_PLUGIN_DATA 가 다른 plugin 값으로 set).

       해결 (2축):
       1. commands/org.md canonical 1줄을 **셸 자체가 경로를 resolve** 하도록
          재박제. fallback chain 을 1줄에 inline:
          - `$CLAUDE_PLUGIN_ROOT/src/lskun_kit/cli_org.py` (env 주입 시)
          - `~/.claude/plugins/cache/LSKunCompanyKit/LSKunCompanyKit/*/src/.../cli_org.py`
            (sort -V tail -1 로 최신 자동 선택)
          - `<cwd>/src/lskun_kit/cli_org.py` (repo clone 직접 실행)
          LLM 이 매번 다른 path 를 hardcode 할 여지 0. `PYTHONPATH` / 버전
          hardcode / `python3 -m` 금지를 명시 박제.
       2. 옛 plugin install 디렉토리 15개 (`0.1.0-dev` ~ `0.15.0`) 즉시 정리.
          0.16.0 만 잔존 → sort -V tail -1 결과 안정화.

       진단 (doctor 17번):
       - `$CLAUDE_PLUGIN_ROOT` 주입 여부 (미주입은 정상, 정보성 ℹ️)
       - plugin install 디렉토리 개수 (0=❌, 1=✅, 2+=⚠️ "옛 버전 잔존")
       - canonical resolve chain 이 단일 파일에 도달하는지 시뮬레이션 검증
       - 16개 → 17개 항목으로 확장. backend 무관하게 항상 수행.

       검증: env 미주입 상태에서 canonical 1줄 실행 → fallback 으로
       `~/.claude/plugins/cache/.../0.16.0/.../cli_org.py` 자동 resolve →
       조직도 정상 출력. 274 tests 회귀 0건.

       제약:
       - 셸이 zsh / bash 가정 (`${VAR:-}` / `[ -f ]` / 명령치환). fish 미지원
         이나 Claude Code Bash tool 은 zsh 사용으로 무관
       - sort -V 는 macOS/Linux coreutils 가정. 동일 환경에서만 보장
```

### Phase 13 (P76 — reflection 입력 방식 재설계 + 강제 메커니즘, 4 에이전트 합의안)

```
P76 ✅ DcodeJob 세션 실측 사건 (CPO 가 4명 워커 dispatch 후 reflection 박제 4건
       모두 skip + 사용자 지적 후 사후 bulk 박제, 1줄당 200~530자 narrative)
       의 근본 해결. P0~P71 + P75 = 3회 반복된 dead code 화 패턴 종결.

       4 에이전트 (critic / architect / analyst / planner) 합의 + 사용자
       추천안 7개 박제:

       1. dispatch 단위 = Task tool 호출 1회 = history 1줄 (audit request_id 정합)
       2. cpo.md 결재 절차 §3/§4 순서 뒤집기 — reflection 박제가 사용자 결과
          전달의 *선행 조건*. "결과 후 작업 완료 인식 → §4 skip" 패턴 차단
       3. HistoryEntry 에 outcome (approved|rework|rejected) + request_id 필드 추가.
          h=N 카운트가 audit log 와 1:1 cross-check 가능해짐
       4. topic / pattern 길이 가드 (HISTORY_FIELD_MAX_LEN=80) + 줄바꿈 금지.
          530자 narrative 재발 방지
       5. reflection.record_from_report() 신규 API — 워커 보고 markdown 의
          ## reflection 후보 섹션을 plugin core 가 자동 파싱. CPO 가 entry 를
          직접 짜지 않음 → narrative 변질 원천 차단. 옛 record() 는 deprecated
          (사용자 정정 경로 /lskun-kit:reflect 용 하위호환)
       6. PostToolUse:Task hook 신규 — Task dispatch 직후 reminder 1줄 stdout
          주입. *자동 박제가 아닌* nudge (ADR-0013 §"자동 박제 금지" 와 구분).
          비활성화: LSKUN_SKIP_REFLECTION_REMINDER=1
       7. /lskun-kit:doctor 에 audit ↔ reflection cross-check 진단 항목 0번
          추가 — audit approved 인데 history 박제 누락된 request_id 검출.
          coverage % + 누락 목록 표시. 자동 복구 X

       신규 모듈: src/lskun_kit/audit_diagnostics.py, hooks/post_tool_use.py
       신규 테스트: tests/test_reflection_p76.py (15) + test_audit_diagnostics_p76.py (5)
       총 274 tests 통과 (기존 256 + 신규 18).

       제약:
       - record_from_report 가 보고 양식 ## reflection 후보 섹션을 못 찾으면
         ReportParseError. CPO 는 워커에게 양식 재작업을 지시해야 함
       - PostToolUse hook 은 "자동 박제 alert" 라 ADR-0013 §"자동 박제 금지" 와
         분리. 별도 ADR 박제 불필요 (architect 판단)
```

### Phase 12 (P75 — `/org` self-bootstrap + 필터/export, 4 에이전트 합의안)

```
P75 ✅ P74 잔존 결함 (PYTHONPATH 의존, 출력 길이) 근본 해결.
       사용자 제안 (`org-chart.md` 정적 인덱스 + h=N auto-increment) 을 4
       에이전트 (critic / architect / analyst / planner) 합의로 폐기:
       - SSOT 이중화 (워커 md frontmatter ↔ org-chart.md)
       - reflection.record() SRP 위반 + dual-write 비원자성
       - ADR-0009 self-contained 원칙 위반 위험
       - 41명 1인 운영 규모에 over-engineering

       합의안 (P75-1 ~ P75-4) 박제:
       - cli_org.py self-bootstrap: 파일 자기 위치 기반 sys.path 보정.
         PYTHONPATH / $CLAUDE_PLUGIN_ROOT env var 의존 0. 직접 실행 가능.
       - commands/org.md: `python3 "$CLAUDE_PLUGIN_ROOT/src/lskun_kit/cli_org.py"`
         1줄로 박제. PYTHONPATH 제거.
       - --domain DOM: prefix 매칭 필터 (예: --domain tech → tech-* 8명).
         출력 길이 제어 — 41명 전체 대신 도메인별 부분 조회.
       - --export PATH: stdout 대신 파일에 dump. Obsidian/GitHub 외부 렌더링.
         사용자 명시 실행, 자동 sync 아님.

       org.py 동적 산출 + ADR-0013 stable markdown table SSOT 유지.
       256 tests 통과.
```

### Phase 12 (P74 — `/org` compact 기본 + paste 변형 금지 박제)

```
P74 ✅ P73 후속. dogfooding 결과 두 가지 잔존 결함 박제:
       (1) LLM 이 commands/org.md 의 canonical 1줄을 무시하고 `PLUGIN_ROOT=...0.X.Y`
           로 버전 hardcode 한 옛 패턴 답습 → 실패 → 재시도
       (2) markdown table 출력을 LLM 이 직접 paste 옮겨 적는 단계에서 행 중복 재발생
       해결:
       - cli_org 의 기본 format 을 compact 1줄로 전환 (ADR-0013 stable table 은
         `--full` 명시 시만). 1줄 short 포맷은 paste 변형 내성 강함.
       - commands/org.md 에 "옛 patterns (PLUGIN_ROOT hardcode, heredoc, -c)"
         금지 명시 + "출력은 그대로, paste 변형 금지" 박제. 호출 → 출력 양쪽 가드.
       256 tests 통과.
```

### Phase 12 (P73 — `/org` canonical entrypoint + compact add-on)

```
P73 ✅ `/lskun-kit:org` 운영 개선. 신규 모듈 `src/lskun_kit/cli_org.py` 추가
       (canonical entrypoint `python3 -m lskun_kit.cli_org`). backend
       auto-detect 는 hooks/session_start 의 `_find_active_company_root` 와
       동일 규칙 (LSKUN_VAULT+COMPANY → cwd 상향 .company). commands/org.md
       를 "이 1줄만 실행" 으로 박제해 LLM 이 매번 다른 Python heredoc 을 짜는
       우회 차단 (두 번 호출 / 출력 paste 오류 재발 방지). `OrgReport.render()`
       에 `compact: bool = False` 인자 추가 — 기본은 ADR-0013 stable markdown
       table 그대로 유지 (SSOT 미파괴), `--compact` 시 1줄 포맷
       `[C/H/W] name (display) · role · domain · model · h=N` (role==name 시
       role 생략) 로 가독성 확보. 256 tests 통과.
```

### Phase 10 (P70 — JD 기반 채용 + 정체성 보강)

```
P70 ✅ ADR-0011 박제. CLAUDE.md §1 정체성 한 줄 갱신 (JD persona body +
       reflection history 2차원 자산). render_default_worker 에 body_override
       string passthrough 인자 추가 (기존 호출자 0 변경). HR Lead persona
       채용 알고리즘 6단계 → 7단계 (4.5 JD body 작성). 핵심 책임에
       "keywords 일괄 보강" (#6) / "역량 갱신" (#7) 추가. CLAUDE.md §6
       금지 목록에 JD 관련 7개 항목 박제 (자동 갱신 / 별도 파일 / schema /
       role 미세 분화 / 외부 전송 / 슬로건 / KPI). 측정 지표 비도입.
       4 에이전트 검토 합의 (architect / critic / analyst / planner).
       기존 회사 / 기존 워커 0 변경.
```

### Phase 9 (P69 — 라우팅 정확도 보강)

```
P69 ✅ workers frontmatter 에 optional `keywords` (콤마 구분 string) 도입.
       routing.py 가 후보 1줄에 keywords raw 노출 + user_request fence 처리
       (markdown injection 가드). cpo.md Routing Heuristics 를 자연어 4줄
       → 결정 절차 5단계 (의도 파악 → keywords/domain 매칭으로 상위 3명 압축
       → history tie-break → 동률 시 사용자 1줄 확인 → 부재 시 자동 채용)
       로 재작성. hr-lead.md 채용 절차에 keywords 1줄 제안 (optional, ceremony 0).
       plugin core 는 매칭/정렬을 하지 않음 — CPO LLM 이 매 호출 시 직접 수행
       (ADR-0009 self-contained 유지). 회사별 lookup table 0. 기존 회사 0
       변경으로 동작 (optional 필드). plugin 업데이트는 회사별 `/sync-persona`
       1회로 전파.
```

---

