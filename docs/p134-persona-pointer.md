# P134 — Persona 포인터 배포 (ADR-0029, v0.38.0)

> 결정 본문 SSOT 는 ADR-0029 (저자 vault). 본 문서는 plugin repo 측 구현 spec.

## 1. 문제 — 실측 (저자 환경, 2026-09-17)

회사 1개 (LSKun) 에 CPO marker 가 박힌 프로젝트 10개.

- Delegation Gate (P126, 2026-08-07) 가 있는 프로젝트는 **1개**. persona 가 프로젝트마다 복사본이라 갱신이 프로젝트당 수동이고, 빠뜨려도 경고가 없다.
- marker 구간 형식이 최소 3세대 + 손글씨 변형 2종 (`<!-- LSKUN-CPO:START -->`, `<!-- LSKUN-CPO:START company=X -->`). 회사명 검출이 머리말 형식에 의존하므로 옛 형식 프로젝트는 hook · 가드가 꺼진 채 persona 본문만 남아 있었다.
- 외주 저장소 2곳의 `origin/master` 에 CPO 구간이 푸시되어 있었다 (비밀값 없음. 회사명 · CPO 이름 · 경로 · 내부 ADR 번호).
- `/lskun-kit:init <같은 회사>` 재실행은 silent skip — stale 프로젝트를 갱신하는 명시 경로가 없었다.

## 2. 공식 기능 실측 (Claude Code v2.1.274)

| 확인 항목 | 결과 |
|---|---|
| `CLAUDE.local.md` | `CLAUDE.md` 와 동일하게 로드 |
| marker 주석 사이의 `@path` import | 동작 |
| import 파일의 frontmatter | 컨텍스트에 노출되지 않음 → `hired/cpo.md` 를 그대로 import |
| 작업 디렉토리 밖 import | 프로젝트당 1회 승인 필요. 미승인 · headless 에서는 **조용히** 로드되지 않음. 미승인 외부 import 가 있으면 같은 파일의 다른 import 도 꺼진다 |
| 승인 상태 저장 위치 | `~/.claude.json` 의 프로젝트별 플래그 — plugin 비접촉 |
| hook `additionalContext` | 10,000자 상한 |

## 3. 결정 (D1~D7)

- **D1** 프로젝트의 CPO 구간 = 머리말 1줄 + `@~/.lskun-companies/<회사>/hired/cpo.md`. 갱신은 회사당 1회 `sync-persona`.
- **D2** 포인터 위치 = `CLAUDE.local.md`. 추적 `CLAUDE.md` 비접촉.
- **D3** git 제외 = **프로젝트 root 자신의** `.git/info/exclude` (`.gitignore` 불변). 상위로 올라가지 않는다 — 상위에는 무관한 저장소 (홈의 dotfiles, 남의 monorepo) 가 있을 수 있다. worktree / submodule · 상위 저장소의 하위 디렉토리 · 비저장소는 건너뛰고 안내.
- **백업은 덮어쓰지 않는다** — `CLAUDE.md.lskun.bak` 이 있으면 `.1`, `.2` … (릴리스 전 독립 리뷰 지적 반영).
- **D4** 로드 자가 점검 — `templates/cpo.md` 끝의 `LSKUN-PERSONA-LOADED` 표식 + SessionStart 안내 (워커 명단 **앞**).
- **D5** `/lskun-kit:init <회사>` 재실행 = inline → pointer 전환 (`idempotency_row = "pointer_converted"`). inline 구간 제거 시 항상 백업, 남는 내용 없으면 파일 삭제, **커밋 없음**. `migrate-schema` · `sync-persona` 도 같은 함수.
- **D6** inline 프로젝트 · 회사 식별 불가 구간에 SessionStart 1줄 알림.
- **D7** marker 탐색 순서 = `CLAUDE.local.md` → `CLAUDE.md` (hook · `cli_org` · `lskun-audit` 공통). 구간 **인식**은 `<!-- LSKUN-CPO:START` 접두 (손글씨 변형 포함), **쓰기**는 표준형만.

## 4. 검증

- stdlib unittest 547 OK — 포인터 주입 · 전환 · 손글씨 변형 · git exclude (`git status` 로 local 파일 · 백업 비노출 확인) · init 전환 행 · hook 안내 3종
- 10개 프로젝트 `CLAUDE.md` **사본** 으로 전환 시험 — 전부 `inline → pointer`, 추적 파일에서 구간 제거 확인 (예: ilsaek 10,018 → 882자, userAPP 은 persona 뿐이라 파일 삭제)
- 실제 세션 (sonnet): 미승인 포인터 → "CPO persona 가 로드되지 않았습니다…" 경고 / import 로드된 포인터 → 경고 없이 CPO 로 동작

## 5. 알려진 한계

- 프로젝트당 1회 승인 창. 거절 · headless 면 persona 없이 돈다 — D4 가 드러낸다.
- **D4 는 LLM 지시다. haiku 는 위치를 옮긴 뒤에도 점검을 놓쳤다 (2/2).** sonnet 은 양방향 통과. 작은 모델로 회사 프로젝트를 여는 경우 `/doctor` [40] 로 확인한다.
- 승인된 외부 import 의 실제 로드는 저자의 대화형 승인이 필요해 사전 검증하지 못했다 — 첫 전환 프로젝트에서 확인한다.
- `CLAUDE.local.md` 는 worktree 마다 따로다.
- persona 크기 (26,000자) 는 그대로 — 후속 과제 (backlog).

## 6. 적용 지점

`src/lskun_kit/persona_injection.py` (포인터 렌더 · `inject_pointer` · `detect_mode` · `has_marker_file` · git exclude · 접두 인식) /
`init.py` · `schema_migration.py` / `hooks/session_start.py` (`_find_marker_project` · `_persona_mode_lines` · `_orphan_marker_notice`) /
`cli_org.py` / `templates/cpo.md` (표식) / `commands/{init,migrate-schema,sync-persona,doctor}.md` ([40]) /
`evals/` (행동 케이스 prompt) / forbidden-history · adr-index · backlog · CLAUDE.md.

## 7. 마이그레이션

1. plugin update → v0.38.0, 세션 재시작
2. 회사당 1회: `/lskun-kit:sync-persona --execute`
3. 프로젝트마다 마지막 1회: `/lskun-kit:init <회사>` → 다음 세션에서 외부 import 승인
4. 추적되던 `CLAUDE.md` 의 구간 제거는 확인 후 직접 커밋
