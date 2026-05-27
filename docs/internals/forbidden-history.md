# 폐기·금지 목록 누적 (Forbidden History)

> 본 문서는 LSKunCompanyKit 의 ADR 별 누적 금지 항목. CLAUDE.md 의 §6 에서 분리 (P109-C, 2026-05-27).
> 정보 손실 0 — 단순 위치 이동. CLAUDE.md 에는 핵심 금지만 요약.

## 6. 절대 만들지 말 것 (ADR-0001 §7 + ADR-0002 §6 + ADR-0004 §8 + ADR-0006 §"폐기/금지" + ADR-0008 §"폐기/금지" + ADR-0009 §"폐기/금지" 누적)

다음을 도입하려는 충동이 들면 **즉시 멈추고 ADR 우선 작성:**

- PRD 사이클 강제 / 분기 회고 자동 생성
- persona evolution narrative (워커가 시간에 따라 자동 진화하는 서사)
- CLI (`company` 명령) — slash command 만 허용
- cmux / tmux / sequential runner harness
- 정적 26 워커 사전 정의 (자동 채용은 CPO 의 실시간 판단 기반, 사전 정의 X)
- scaffold 의 11 디렉토리 강제
- Workload Budget 강제
- "회사 운영 OS" / "Growing Company" 같은 비대화 슬로건 narrative
- COO / CTO / Brainstormer / Strategist / PM 등 임원 자동 추가 (CPO/HR 외)
- **워커 → 워커 chain (sub-leader 출현)** — chain 권한은 CPO 단독 (ADR-0004 §8)
- **결재 라인 확장** — 부 결재자 / 위원회 / 다단계 승인 (CPO 단독)
- ~~CPO 가 인사팀장을 자동 chain 호출 (사용자 승인 1단계 필수)~~ — **ADR-0004 §3 로 폐기**, 자동 채용 허용
- **audit log 위에 자동 분석 / 대시보드 / KPI / 통계 시각화** — ADR-0006 + ADR-0002 §5 위반
- **audit log 기반 워커 자동 평가·해고** — HR Lead 사용자 명시 호출 원칙 위반 (ADR-0006)
- **분기 / 월간 audit 자동 회고 보고서** — persona evolution narrative 금지와 동일 결 (ADR-0006)
- **결재 위원회 / 다단계 승인 / 부 결재자** — ADR-0004 §8 + ADR-0006 위반
- **audit log 외부 자동 전송** — 사용자 명시 동의 없는 외부 전송 금지 (ADR-0006)
- **`.claude/lskun-kit.json` 등 프로젝트→회사 link 파일** — ADR-0007 실패 패턴. multi-project 단일 회사 케이스가 **실증된 후** 에만 새 ADR 박제 가능 (ADR-0008)
- **CLAUDE.md marker 의 "캐시" 강등** — marker = 진실원 (ADR-0004 §1). drift 발생 시 자동 갱신 X, 사용자 알림만 (ADR-0008)
- **SSOT 3축 모델** — 2축 (개발자 / 사용자 회사) 으로 충분. 사용자 프로젝트는 작업 위치이며 별도 SSOT 아님 (ADR-0008)
- **vault default 격상** — Local 과 Vault 동등. vault 강제 금지 (ADR-0008)
- **"future: Notion" 등 외부 통합 promise** — plugin 본 repo 어디서도 박제 금지. 실제 도입 시점에 별도 ADR + add-on package (ADR-0009)
- **plugin core 안에서 외부 시스템 (Obsidian, Notion 등) SDK / API 호출** — 영원히 금지. 외부 통합은 별도 add-on 책임 (ADR-0009)
- **plugin 본 문서에 사용자 vault 절대경로·외부 도구 컨벤션 박제** — 추상 placeholder (`<your-vault>/`, `<your-project>/`) 만 허용 (ADR-0009)
- **JD 자동 정기 갱신** — 채용 시점 1회 inline 박제. 사용자 미요청 자동 갱신 금지 (ADR-0011 §"폐기/금지")
- **별도 JD 파일** (`jd/<name>.md` 등) — JD 는 워커 body inline 만 (ADR-0011)
- **plugin core 의 JD schema 박제** — `body_override` 는 단순 string passthrough. dataclass / 검증 / 도메인 사전 도입 금지 (ADR-0011 + ADR-0009)
- **role 미세 분화 우회** — JD 가 정교해진다고 `backend-engineer-payment` 같은 role 분할 채용 금지. rate-limit 단위 `role × domain` 유지 (ADR-0011)
- **JD 외부 전송** — JD 가 외부 시스템 (Notion / Slack 등) 으로 자동 전송 금지 (ADR-0011 + ADR-0009)
- **"고밀도 워크포스" / "최대한 밀도" / "AI 직원 진화" 등 슬로건성 narrative** — CLAUDE.md / README / ADR / persona template 어디에도 박지 않음 (ADR-0011)
- **JD 측정 지표** — "밀도" / "Context Coverage Rate" / "First-pass Approval Rate" 등 KPI 자동 산출 금지 (ADR-0011 + ADR-0002 §5)
- **`org.render()` 의 컬럼 폭 동적 계산 재도입** — markdown table 단일 SSOT. ASCII 정렬 미려함 추구로 동적 padding 복귀 금지 (ADR-0013)
- **조직도 출력에 한글 폭 보정 (`east_asian_width`) 도입** — markdown table 로 회피한 의도 위반. 다른 format 필요 시 별도 ADR (ADR-0013)
- ~~CPO 결재 절차의 reflection 박제 단계 생략~~ — **ADR-0014 로 폐기** (reflection 메커니즘 자체 폐기)
- ~~워커가 자기 reflection 을 직접 박제하는 경로~~ — **ADR-0014 로 자연 폐기** (reflection 대상 자체 소멸). 워커 → 워커 chain 금지는 유지 (ADR-0004 §8)
- ~~새 hook 으로 자동 reflection 박제 시도~~ — **ADR-0014 로 자연 폐기**. Stop / PostToolUse hook 도 제거됨 (P79-1).
- **reflection / history 메커니즘 재도입** — ADR-0014 로 폐기. 재도입 시 새 ADR + 정체성 재정의 선행 필수
- **워커 진화 narrative** (ADR-0014) — "워커가 시간으로 성장한다" 류 슬로건 박제 금지. ADR-0011 의 "AI 직원 진화" 슬로건 금지와 일관
- **JD 자동 갱신** (ADR-0014) — JD 는 채용 시 1회 박제. 사용자 명시 갱신 (`/lskun-kit:work hr-lead "..."`) 외 자동 진화 금지
- **해고 시 archived 의 frontmatter display_name 자동 익명화 / rewrite** (ADR-0015 결정 7-B) — 역사 자산 불변
- **archived 의 옛 display_name 재사용** (ADR-0015 결정 7-C) — 같은 role 재채용 시 옛 이름 재사용 금지, 혼선 방지
- **audit log (`.audit/decisions.jsonl`) 의 archived 워커 이름 rewrite** (ADR-0015 결정 7-D) — ADR-0006 정신, 역사 기록 불변
- **CPO 라우팅 / SessionStart hook 의 archived 워커 노출** (ADR-0015 결정 7-B/7-E) — hired/ 만 스캔, archived/ 무시
- **`<project>/.company/` 의 모든 형태** (ADR-0015 결정 1-A) — SSOT, cache, mirror 무엇으로도 도입 금지. Local SSOT 는 `~/.lskun-companies/<name>/` 단일 위치
- **`$LSKUN_VAULT` env var 의 plugin core 참조** (ADR-0015 결정 1-A) — sync 명령의 `--target` / `--source` 인자로만 사용
- **`adapters/vault.py` 재도입** (ADR-0015 결정 1-B) — plugin core 가 vault 직접 참조 금지, 파일시스템 복사 sync 만
- **`/found` `/join` `/status` 신규 명령 / `.claude/lskun-link.json`** (ADR-0015 결정 2-A) — `/init` 멱등성으로 충분
- **Skill 실패 시 Task tool 우회** (ADR-0015 결정 3-A) — LLM 의 학습 패턴 차단, 에러 보고 후 중단
- **메모리·CLAUDE.md text instruction 만으로 OMC fallback 차단 재시도** (ADR-0016) — 3회 실패 입증. hook 차단 필수. 신규 차단 경로 추가도 hook 레벨에서
- **Agent 툴의 `subagent_type` 에 `LSKunCompanyKit:work` 추가 시도** (ADR-0016) — Skill 진입이지 subagent 아님. plugin 아키텍처 위반
- **PreToolUse hook 에서 `tool_input` 의 prompt/description 내용 파싱하여 의도 추론** (ADR-0016) — `subagent_type` 문자열 매칭만 허용. prompt 내용 기반 의도 판별은 brittle + false positive 원천
- **`LSKUN_ALLOW_OMC_FALLBACK=1` 의 `.zshrc` / `.bashrc` 영구 export** (ADR-0016 결정 5) — 가드 무력화. 세션 단위 export 권장. doctor [21] 가 검출 + 경고
- **PreToolUse:Skill 가드 추가로 사용자 명시 슬래시 `/oh-my-claudecode:*` 까지 차단** (ADR-0016) — 사용자 의도 무시. 본 ADR 범위는 메인 LLM 의 자의적 Agent → OMC 호출만
- **Denylist 모델 재도입** (ADR-0017) — 4회째 재발 입증. allowlist 단일 정책 유지. 재도입 시 새 ADR + 5회째 재발 증거 필수
- **Skill 문서·persona template 의 dispatch `subagent_type` 미규정** (ADR-0017) — `commands/work.md` / `templates/cpo.md` / `templates/hr-lead.md` 모두 `subagent_type="claude"` 명시 박제 필수. 누락 시 LLM 자의 선택 → ADR-0017 위반
- **`subagent_type="claude"` 외 dispatch 의 silent 통과** (ADR-0017) — 반드시 stderr 안내 + escape hatch 경로 명시
- **plugin 개발자 dogfood 시나리오를 위한 cwd-aware 가드 추가** (ADR-0017) — false positive 우려. escape hatch 1회 set 으로 처리
- **`LSKUN_ALLOW_NON_CLAUDE_DISPATCH=1` / `LSKUN_ALLOW_OMC_FALLBACK=1` 의 `.zshrc` / `.bashrc` 영구 export** (ADR-0017 결정 8) — allowlist 가드 무력화. 세션 단위 export 권장. doctor [23] 가 검출

### ADR-0002 로 **허용된 예외 (2명 한정)**

- **CPO** — 메인 세션 자체가 CPO persona 로 동작 (ADR-0004 §1). 결재 라인 + 단독 채용 권한.
- **인사팀장 (HR Lead)** — CPO 가 Task tool 로 호출 시 자동 채용 진행. 사용자 명시 호출은 해고·평가 전용.

> 이 2명 외의 임원 컨셉을 추가하려면 새 ADR 박제 필요. 본 예외는 ADR-0002 §1~§2 및 ADR-0004 §1~§3 이 정의한다.

### ADR-0004 가 폐기한 ADR-0002 단서 조항

ADR-0002 의 다음 조항은 ADR-0004 가 supersede 했다:

- ~~"CPO 가 인사팀장을 chain 호출하지 않는다 / 사용자 승인 1단계 필수"~~ → CPO 자동 채용 허용 (사용자 알림만)
- ~~"CPO 는 결재 라인이 아니다 / 다른 워커의 작업 결과를 검수·승인하지 않는다"~~ → CPO 가 결재 라인
- ~~"HR Lead 는 사용자 명시 호출만 받는다"~~ → CPO 의 Task dispatch 도 수용 (해고만 명시 요청 유지)

### ADR-0005 가 폐기한 ADR-0004 §6 조항

- ~~"frontmatter 5→6 자동 마이그레이션 X / 사용자가 display_name 1줄 수동 추가"~~ → `/lskun-kit:migrate-schema` 로 사용자 confirm 기반 plugin 책임 마이그레이션 (ADR-0005)
- 단, **history entry 보존 / frontmatter 덮어쓰기 금지 / 백업 강제** 가드는 불변 (ADR-0014 — heading 만 archived 로 rename 가능, entry 불변)

---

