---
name: lskun-kit:org
description: 현재 회사의 조직도를 한눈에 본다 (읽기 전용). hired 워커 목록, 도메인 분포, persona sync 상태 요약
---

# /lskun-kit:org

활성 backend 의 `hired/` 디렉토리를 스캔해 조직도를 출력. **읽기 전용** — 파일을 수정하지 않는다.

## 실행 — Canonical (반드시 이 1줄)

**다른 호출 형태로 우회하지 말 것.** 옛 patterns (`PLUGIN_ROOT=...0.X.Y` hardcode, `python3 << 'PY'` heredoc, `python3 -c "..."` 등) 모두 금지. 아래 1줄만 그대로 실행한다.

```bash
PYTHONPATH="$CLAUDE_PLUGIN_ROOT/src" python3 -m lskun_kit.cli_org
```

옵션 (필요 시에만):

```bash
PYTHONPATH="$CLAUDE_PLUGIN_ROOT/src" python3 -m lskun_kit.cli_org --full              # 옛 markdown table (ADR-0013 stable format)
PYTHONPATH="$CLAUDE_PLUGIN_ROOT/src" python3 -m lskun_kit.cli_org --include-archived  # archived/ 도 표시
PYTHONPATH="$CLAUDE_PLUGIN_ROOT/src" python3 -m lskun_kit.cli_org --full --include-archived
```

> `$CLAUDE_PLUGIN_ROOT` 는 Claude Code 가 plugin 활성 버전으로 자동 resolve. 버전을 hardcode 하지 말 것.

## 출력 처리 — 그대로 (paste 변형 금지)

Bash 결과의 stdout 을 **그대로** 사용자에게 보여준다. 절대 LLM 이 행을 옮겨 적거나 재포맷하지 말 것.

- 행 순서 변경 금지
- 행 복제·일부 paste 금지 (collapsed 출력을 직접 paste 하는 단계에서 자주 발생)
- 컬럼 정렬·여백 조정 금지
- "요약해드릴게요" 식 재서술 금지

호출 결과가 길어 collapsed 되면 사용자에게 expand 안내만 한다. **출력을 다시 옮겨 적지 말 것.**

## 출력 예 (기본 — P74: compact 1줄)

```
LSKunCompanyKit org
================================================
회사: Acme (domain=핀테크)
backend: vault → <your-vault>/03_Companies/Acme

[C] cpo (자비스) · chief-product-officer · meta · default · h=12
[H] hr-lead (요니찡) · meta · sonnet · h=3
[W] backend-engineer (준호 Kim) · web · sonnet · h=28
[W] frontend-engineer (민지 Park) · web · sonnet · h=45

총: 4명 (CPO 1, HR 1, Worker 2)
도메인별: meta 2, web 2
Persona sync: cpo=lskun-kit@<plugin-version> (...), hr-lead=lskun-kit@<plugin-version> (...)
```

> 1줄 short 포맷이 LLM paste 오류에 강하고 (행 분할/중복 자주 발생하던 markdown table 대비), 한눈에 도메인 분포까지 보임. role==name 인 일반 워커는 role 컬럼을 자동 생략.

## 출력 예 (`--full` — ADR-0013 stable markdown table)

옛 format. format SSOT (Claude Code / GitHub / Obsidian 동일 렌더링) 가 필요할 때만 사용.

```
| Cat    | Name | Display | Role | Domain | Model | History |
|--------|------|---------|------|--------|-------|---------|
| CPO    | cpo | 자비스 | chief-product-officer | meta | default | 12 |
| HR     | hr-lead | 요니찡 | hr-lead | meta | sonnet | 3 |
| Worker | backend-engineer | 준호 Kim | backend-engineer | web | sonnet | 28 |
```

## 동작

1. backend 결정: `LSKUN_VAULT` + `LSKUN_COMPANY` → Vault, 없으면 cwd 상향 `.company/` 탐색
2. `company.md` 에서 회사 이름 + 도메인 읽기
3. `hired/*.md` 각 파일 frontmatter + body 파싱
    - `## Project History` 섹션의 ` - ... first-pass ` 줄을 카운트해 `h=N` 표시
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

`lskun_kit.cli_org.main()` 이 entrypoint. 내부적으로 `lskun_kit.org.build(adapter)` 로 `OrgReport` 를 만들고 `report.render(include_archived, compact)` 호출. `--full` 미지정 시 `compact=True`.
