---
name: lskun-kit:org
description: 현재 회사의 조직도를 한눈에 본다 (읽기 전용). hired 워커 목록, 도메인 분포, persona sync 상태 요약
---

# /lskun-kit:org

활성 backend 의 `hired/` 디렉토리를 스캔해 조직도를 표 형태로 출력. **읽기 전용** — 파일을 수정하지 않는다.

## 실행 — Canonical (1줄 박제)

다른 호출 형태로 우회하지 말 것. 이 1줄만 실행한다 (LLM 추론 우회 방지).

```bash
PYTHONPATH="$CLAUDE_PLUGIN_ROOT/src" python3 -m lskun_kit.cli_org
```

옵션:

```bash
PYTHONPATH="$CLAUDE_PLUGIN_ROOT/src" python3 -m lskun_kit.cli_org --compact            # 1줄 compact 포맷
PYTHONPATH="$CLAUDE_PLUGIN_ROOT/src" python3 -m lskun_kit.cli_org --include-archived   # archived/ 도 표시
PYTHONPATH="$CLAUDE_PLUGIN_ROOT/src" python3 -m lskun_kit.cli_org --compact --include-archived
```

> `$CLAUDE_PLUGIN_ROOT` 가 없는 환경에서는 plugin install 경로 (`~/.claude/plugins/cache/LSKunCompanyKit/LSKunCompanyKit/<ver>/`) 또는 repo clone 경로의 `src` 를 PYTHONPATH 로 지정한다.

## 출력 예 (기본 — ADR-0013 stable markdown table)

```
LSKunCompanyKit org
================================================
회사: Acme (domain=핀테크)
backend: vault → <your-vault>/03_Companies/Acme

| Cat    | Name | Display | Role | Domain | Model | History |
|--------|------|---------|------|--------|-------|---------|
| CPO    | cpo | 자비스 | chief-product-officer | meta | default | 12 |
| HR     | hr-lead | 요니찡 | hr-lead | meta | sonnet | 3 |
| Worker | backend-engineer | 준호 Kim | backend-engineer | web | sonnet | 28 |

총: 3명 (CPO 1, HR 1, Worker 1)
도메인별: meta 2, web 1
Persona sync: cpo=lskun-kit@<plugin-version> (2026-05-19), hr-lead=lskun-kit@<plugin-version> (2026-05-19)
```

## 출력 예 (`--compact` — 1줄 포맷)

워커가 많을 때 가독성이 좋다. role 이 name 과 같을 때 role 생략.

```
[C] cpo (자비스) · chief-product-officer · meta · default · h=12
[H] hr-lead (요니찡) · meta · sonnet · h=3
[W] backend-engineer (준호 Kim) · web · sonnet · h=28
[W] frontend-engineer (민지 Park) · web · sonnet · h=45
```

> 기본 markdown table 은 ADR-0013 stable format SSOT — 호출 시점·데이터셋·한글 비율에 무관하게 형식이 안정적이고 Claude Code / GitHub / Obsidian 모두 동일 렌더링.
> `--compact` 는 일상 사용 가독성용 add-on. format 결정은 호출자 선택.

## 동작

1. backend 결정: `LSKUN_VAULT` + `LSKUN_COMPANY` → Vault, 없으면 cwd 상향 `.company/` 탐색
2. `company.md` 에서 회사 이름 + 도메인 읽기
3. `hired/*.md` 각 파일 frontmatter + body 파싱
    - `## Project History` 섹션의 ` - ... first-pass ` 줄을 카운트해 `history=N` 표시
    - schema 위반 파일은 자동 skip (doctor 에서 별도 검증)
4. CPO → HR → Worker (이름순) 으로 정렬
5. 도메인별 카운트 + Persona sync 상태 (메타 워커만)

## 정렬·필터

- 기본: CPO 1명 → HR 1명 → Worker (이름 알파벳)
- `--include-archived` — 별도 섹션 `--- archived ---` 으로 archived/ 워커 표시

## 안전 가드

- read-only — 파일 쓰기 0
- schema 위반 파일은 silent skip (doctor 가 잡음)
- backend 부재 시 stderr 에 안내 + exit code 2

## 구현 노트

`lskun_kit.cli_org.main()` 이 entrypoint. 내부적으로 `lskun_kit.org.build(adapter)` 로 `OrgReport` 를 만들고 `report.render(include_archived, compact)` 호출.
