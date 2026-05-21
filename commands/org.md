---
name: lskun-kit:org
description: 현재 회사의 조직도를 한눈에 본다 (읽기 전용). hired 워커 목록, 도메인 분포, persona sync 상태 요약
---

# /lskun-kit:org

활성 backend 의 `hired/` 디렉토리를 스캔해 조직도를 출력. **읽기 전용** — 파일을 수정하지 않는다.

## 실행 — Canonical (P75: self-bootstrap, env var 의존 0)

**다른 호출 형태로 우회하지 말 것.** `cli_org.py` 가 자기 위치 기반으로 `sys.path` 자체 보정하므로 `PYTHONPATH` / `$CLAUDE_PLUGIN_ROOT` 환경변수 불필요. 아래 1줄만 그대로 실행한다.

```bash
python3 "$CLAUDE_PLUGIN_ROOT/src/lskun_kit/cli_org.py"
```

`$CLAUDE_PLUGIN_ROOT` 가 미주입 환경이면, plugin install 경로 (`~/.claude/plugins/cache/LSKunCompanyKit/LSKunCompanyKit/<latest>/src/lskun_kit/cli_org.py`) 또는 repo clone 경로의 `src/lskun_kit/cli_org.py` 를 **그대로 첫 인자로** 실행한다. PYTHONPATH 박지 말 것.

옵션:

```bash
python3 .../cli_org.py --domain tech           # tech-* 도메인만 필터 (출력 길이 제어)
python3 .../cli_org.py --domain meta           # meta 도메인만 (CPO/HR/CFO/COO 등)
python3 .../cli_org.py --export /tmp/org.md    # stdout 대신 파일로 dump (Obsidian/GitHub 렌더링용)
python3 .../cli_org.py --full                  # 옛 markdown table (ADR-0013 stable format)
python3 .../cli_org.py --include-archived      # archived/ 도 표시
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
