---
name: lskun-kit:org
description: 현재 회사의 조직도를 한눈에 본다 (읽기 전용). hired 워커 목록, 도메인 분포, persona sync 상태 요약
---

# /lskun-kit:org

활성 backend 의 `hired/` 디렉토리를 스캔해 조직도를 출력. **읽기 전용** — 파일을 수정하지 않는다.

## 실행 — Canonical (P77: env 의존 0, shell-side resolve)

**다른 호출 형태로 우회하지 말 것.** 아래 1줄을 그대로 실행한다. 셸이 직접 `cli_org.py` 경로를 해소하므로 `$CLAUDE_PLUGIN_ROOT` 가 주입되지 않은 환경에서도 동작한다.

```bash
LSKUN_CLI="${CLAUDE_PLUGIN_ROOT:-}/src/lskun_kit/cli_org.py"; [ -f "$LSKUN_CLI" ] || LSKUN_CLI="$(ls -1d ~/.claude/plugins/cache/LSKunCompanyKit/LSKunCompanyKit/*/src/lskun_kit/cli_org.py 2>/dev/null | sort -V | tail -1)"; [ -f "$LSKUN_CLI" ] || LSKUN_CLI="$(pwd)/src/lskun_kit/cli_org.py"; python3 "$LSKUN_CLI"
```

해소 순서:
1. `$CLAUDE_PLUGIN_ROOT/src/lskun_kit/cli_org.py` (env 주입된 경우)
2. `~/.claude/plugins/cache/LSKunCompanyKit/LSKunCompanyKit/<latest>/src/lskun_kit/cli_org.py` (sort -V 최신)
3. `<cwd>/src/lskun_kit/cli_org.py` (repo clone 직접 실행)

**LLM 금지 사항**: 위 1줄을 다른 형태로 재작성·축약·heredoc 변형하지 말 것. 버전 번호 hardcode 금지 (`0.16.0` 등). `PYTHONPATH=...` 박지 말 것. `python3 -m lskun_kit.cli_org` 도 금지 (sys.path 미보정 환경에서 실패).

옵션 (위 1줄 끝의 `python3 "$LSKUN_CLI"` 에 인자 append):

```bash
python3 "$LSKUN_CLI" --domain tech           # tech-* 도메인만 필터 (출력 길이 제어)
python3 "$LSKUN_CLI" --domain meta           # meta 도메인만 (CPO/HR/CFO/COO 등)
python3 "$LSKUN_CLI" --export /tmp/org.md    # stdout 대신 파일로 dump (Obsidian/GitHub 렌더링용)
python3 "$LSKUN_CLI" --full                  # 옛 markdown table (ADR-0013 stable format)
python3 "$LSKUN_CLI" --include-archived      # archived/ 도 표시
```

## 출력 처리 — 그대로 (paste 변형 금지)

Bash 결과의 stdout 을 **그대로** 사용자에게 보여준다.

- 행 순서 변경 금지
- 행 복제·일부 paste 금지 (collapsed 출력을 직접 paste 하는 단계에서 자주 발생)
- 컬럼 정렬·여백 조정 금지
- "요약해드릴게요" 식 재서술 금지

출력이 길어 collapsed 되면 **expand 안내만** 한다. 다시 옮겨 적지 말 것. 길이가 부담스러우면 사용자에게 `--domain X` 필터를 제안.

## 출력 예 (기본 — compact 1줄)

```
LSKunCompanyKit org
================================================
회사: Acme (domain=핀테크)
backend: vault → <your-vault>/03_Companies/Acme

[C] cpo (자비스) · chief-product-officer · meta · default · h=12
[H] hr-lead (요니찡) · meta · sonnet · h=3
[W] backend-engineer (준호 Kim) · web · sonnet · h=28
```

## 출력 예 (`--full` — ADR-0013 stable markdown table)

```
| Cat    | Name | Display | Role | Domain | Model | History |
|--------|------|---------|------|--------|-------|---------|
| CPO    | cpo | 자비스 | chief-product-officer | meta | default | 12 |
```

## 동작

1. **self-bootstrap**: `cli_org.py` 가 `sys.path` 자체 보정 (PYTHONPATH 환경변수 불필요)
2. backend 결정: `LSKUN_VAULT` + `LSKUN_COMPANY` → Vault, 없으면 cwd 상향 `.company/` 탐색
3. `company.md` 에서 회사 이름 + 도메인 읽기
4. `hired/*.md` 각 파일 frontmatter + body 파싱
    - `## Project History` 섹션의 ` - ... first-pass ` 줄을 카운트해 `h=N` 표시
    - schema 위반 파일은 자동 skip (doctor 에서 별도 검증)
5. CPO → HR → Worker (이름순) 으로 정렬
6. `--domain` 지정 시 prefix 매칭으로 필터
7. `--export` 지정 시 파일에 쓰고 경로만 출력

## 안전 가드

- read-only — 워커 파일 쓰기 0 (`--export` 는 사용자 지정 경로에만 출력)
- schema 위반 파일은 silent skip (doctor 가 잡음)
- backend 부재 시 stderr 안내 + exit code 2

## P75 합의 (참고)

`org-chart.md` 정적 인덱스 도입 안은 4 에이전트 (critic / architect / analyst / planner) 합의로 **폐기**:
- SSOT 이중화 (워커 md frontmatter ↔ org-chart.md)
- `reflection.record()` SRP 위반 + dual-write 비원자성
- ADR-0009 self-contained 원칙 위반 위험 (Obsidian 관습 박제)
- 41명 1인 운영 규모에 over-engineering

현행 동적 산출 유지 + `cli_org.py` self-bootstrap + 필터/export 옵션이 합의안.

## 구현 노트

`lskun_kit.cli_org.main()` 이 entrypoint. 내부적으로 `lskun_kit.org.build(adapter)` 로 `OrgReport` 를 만들고 `report.render(include_archived, compact)` 호출.
