# P130 — 결재 기록 진입점 `lskun-audit record` (ADR-0027, v0.35.0)

> 결정 본문 SSOT 는 ADR-0027 (저자 vault). 본 문서는 plugin repo 측 구현 spec.

## 1. 문제 — 실사용 데이터

LSKun 회사 `.audit/decisions.jsonl` (288줄, 2026-09-17 관찰):

| 관찰 | 의미 |
|---|---|
| 결재 기록 249건 | persona 지시만으로도 CPO 는 기록해 왔다 (`audit.record()` 의 코드 호출자 0건 ≠ 기록 0건) |
| 월별 141 → 62 → 35 → 1 | 기록이 빠르게 줄고 있다 |
| P126 (빙의 기본) 이후 `embody:` 기록 0건 | 기본 경로가 된 빙의 건이 기록되지 않는다 |
| 일부 entry `first_pass_score: null`, JSON 포맷 상이 | `AuditEntry` 검증을 우회한 JSONL 손기록 |

원인 = 기록 절차의 마찰. persona 가 지시하던 방법은 12필드 inline Python 이고 그중 2개는
ADR-0014 로 폐기된 점수 체계의 잔재다.

## 2. 결정 (D1~D7)

- **D1** plugin `bin/lskun-audit` (공식 구성요소 — Bash PATH 에 추가) → `src/lskun_kit/cli_audit.py`. self-bootstrap.
- **D2** `lskun-audit record --worker <name> --verdict <enum> --reason "<…>"`. company · domain · request_id · ts 자동 해소.
  선택: `--request-id` `--rounds` `--model` (기본 `inherit`) `--auto-hired`. 잔재 필드 = `first_pass_score: 0`, `final_score: null`. **schema 불변.**
  검증 = 기존 `AuditEntry`. 실패 시 비정상 종료 + 사유 1줄 + 파일 미변경. 성공 시 `recorded <request_id> <verdict> <worker>`.
- **D3** `--embody` → reason 에 `embody: ` 접두 보장 (중복 방지).
- **D4** `decisions.jsonl` 손기록 금지 — 진입점 단일 경로.
- **D5** 하위 명령 `record` 단일. 조회 · 집계 금지 (ADR-0006).
- **D6** `templates/cpo.md` §결재 3단계를 진입점 1줄로 교체 (dispatch · 빙의 예시 병기). `work.md` · `routing.py` 동기화.
- **D7** doctor [39] — 실행 파일 존재 · 실행 권한 · 하위 명령 단일.

## 3. hook 으로 강제하지 않는 이유

- hook 은 dispatch 건만 본다. 핵심 문제인 빙의 건은 도구 이벤트가 없다.
- ADR-0006 §2 — hook 자동화 미도입. 기록 주체 = 판단 주체 (CPO).

## 4. "CLI 금지" 조항과의 관계

ADR-0001 §7 이 금지한 것은 사용자가 터미널에서 치는 CLI 제품 표면이다. `lskun-audit` 는 CPO 가
Bash 도구로 호출하는 내부 실행 파일이며 선례는 `cli_org.py` (P75). 사용자 표면은 계속 slash command 뿐.

## 5. 알려진 한계

- 마찰을 줄일 뿐 기록을 강제하지 않는다. 효과는 배포 후 `embody:` 기록이 다시 나타나는지를 사람이 확인한다 (자동 집계 금지).
- 첫 실행 시 Bash 권한 확인이 1회 뜰 수 있다 (`lskun-audit` 허용).
- plugin `bin/` 은 claude.ai 조직 설정 경유 배포에 포함할 수 없다 (본 plugin 은 GitHub marketplace — 해당 없음).

## 6. 적용 지점

- `bin/lskun-audit`, `src/lskun_kit/cli_audit.py` (신설)
- `src/lskun_kit/templates/cpo.md` §핵심 책임 8 · §결재 1·3단계, `commands/work.md`, `src/lskun_kit/routing.py`
- `commands/doctor.md` [39], `docs/internals/{forbidden-history,adr-index,phase-roadmap,directory-structure}.md`, `CLAUDE.md` §1 · §6 · §7 · §9
- tests: `test_cli_audit.py` (14), `test_p130_audit_entrypoint_docs.py` (4)

## 7. 검증

- stdlib unittest 508 OK (`bin/` 경유 subprocess 실행 포함)
- 실제 세션 (`claude -p --plugin-dir <repo>`): `lskun-audit record … --embody` 가 PATH 에서 이름만으로 실행,
  `reason: "embody: …"` · company · domain 자동 해소된 1줄 append 확인

## 8. 마이그레이션

1. plugin update → v0.35.0, 세션 재시작 또는 `/reload-plugins`
2. `/lskun-kit:sync-persona --execute`
3. 기존 `decisions.jsonl` 변경 없음 (비정형 줄 보정 안 함 — append-only)
