---
name: lskun-kit:org
description: 현재 회사의 조직도를 한눈에 본다 (읽기 전용). hired 워커 목록, 도메인 분포, persona sync 상태 요약
---

# /lskun-kit:org

활성 backend 의 `hired/` 디렉토리를 스캔해 조직도를 표 형태로 출력. **읽기 전용** — 파일을 수정하지 않는다.

## 사용

```
/lskun-kit:org                         # hired/ 만
/lskun-kit:org --include-archived      # archived/ 도 별도 섹션으로 표시
```

## 출력 예 (ADR-0013 — stable markdown table)

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
| Worker | frontend-engineer | 민지 Park | frontend-engineer | web | sonnet | 45 |

총: 4명 (CPO 1, HR 1, Worker 2)
도메인별: meta 2, web 2
Persona sync: cpo=lskun-kit@<plugin-version> (2026-05-19), hr-lead=lskun-kit@<plugin-version> (2026-05-19)
```

> Markdown table 이라 호출 시점·데이터셋·한글 비율에 무관하게 형식이 안정적이다 (ADR-0013).
> Claude Code / GitHub / Obsidian 모두 동일하게 렌더링.

## 동작

1. `company.md` 에서 회사 이름 + 도메인 읽기
2. `hired/*.md` 각 파일 frontmatter + body 파싱
    - `## Project History` 섹션의 ` - ... first-pass ` 줄을 카운트해 `history=N` 표시
    - schema 위반 파일은 자동 skip (doctor 에서 별도 검증)
3. CPO → HR → Worker (이름순) 으로 정렬
4. 도메인별 카운트 + Persona sync 상태 (메타 워커만)

## 정렬·필터

- 기본: CPO 1명 → HR 1명 → Worker (이름 알파벳)
- `--include-archived` — 별도 섹션 `--- archived ---` 으로 archived/ 워커 표시

## 안전 가드

- read-only — 파일 쓰기 0
- schema 위반 파일은 silent skip (doctor 가 잡음)
- backend 부재 시 "(N/A — backend 없음)" 또는 오류

## 구현 노트

`lskun_kit.org.build(adapter)` 가 OrgReport 반환. `report.render(include_archived=False)` 가 사람이 읽는 표 출력.
