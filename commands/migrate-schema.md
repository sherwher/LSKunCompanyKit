---
name: lskun-kit:migrate-schema
description: 기존 회사 (v0.2 / v0.3 schema) 를 현재 v0.4 schema 로 보강 — frontmatter 누락 필드 + CLAUDE.md marker 박제. history 절대 보존 (ADR-0005).
arguments:
  - name: dry_run
    description: 변경 없이 plan 만 출력 (--dry-run)
    required: false
  - name: from_schema
    description: 자동 추정 무시하고 강제 지정 (v0.2 | v0.3)
    required: false
---

# /lskun-kit:migrate-schema

이미 운영 중인 회사를 새 schema 로 끌어올린다. ADR-0005.

## 동작 (멱등 · 안전 가드 4중)

1. 활성 backend 결정 (`init.detect_backend`)
2. `schema_migration.plan(adapter, company_root, backend, project_root)` 호출
3. **plan 출력** — 사용자에게 무엇이 바뀔지 보여줌:
   - company.md 의 누락 필드 (예: `domain`)
   - 각 워커의 누락 필드 (예: `display_name`, `domain`)
   - CLAUDE.md marker 부재 여부
4. **인터뷰** — plan 이 no-op 아니면 사용자에게 질문:
   - 회사 `domain` (예: "의료 SaaS")
   - 일반 워커별 `display_name` (CPO/HR 도 포함 — 그 외 워커가 있으면 그것도)
   - 일반 워커별 `domain` (CPO/HR 은 자동 `meta` 부여, 사용자 입력 불필요)
5. `schema_migration.execute(adapter, plan, answers)` 호출:
   - 변경 전 모든 파일 자동 백업 (`<file>.lskun-pre-migrate.bak`)
   - frontmatter 의 **누락 필드만 추가** — 기존 값 절대 덮어쓰지 않음
   - `## Project History` 섹션 한 줄도 건드리지 않음
   - CLAUDE.md marker 박제 (없으면 신규, 손편집 감지되면 P34 가드대로 추가 백업)
6. 결과 리포트 출력 — 변환 항목 / 백업 위치 / 손실 0 검증

## 안전 가드 (불가침)

- **history 절대 보존** — `## Project History` 의 어떤 줄도 추가·수정·삭제 X
- **frontmatter 기존 키 덮어쓰기 금지** — 누락된 키만 추가
- **백업 강제** — 모든 변경 파일에 `.lskun-pre-migrate.bak` 사전 생성
- **developer SSOT 거부** — `02_Projects/LSKunCompanyKit/` 경로면 즉시 ❌

## 옵션

- `--dry-run` : 변경 없이 plan + 인터뷰 질문 미리보기만
- `--from-schema=v0.2|v0.3` : 자동 추정 무시
- 환경변수 비대화 모드:
  - `LSKUN_MIGRATE_DOMAIN=<도메인>`
  - `LSKUN_MIGRATE_CPO_NAME=<이름>` / `LSKUN_MIGRATE_HR_NAME=<이름>`
  - 일반 워커는 `LSKUN_MIGRATE_DISPLAY_<workername>=<이름>` 패턴

## 사용 예

```bash
# 1단계: 변경 없이 plan 확인
/lskun-kit:migrate-schema --dry-run

# 2단계: 실제 마이그레이션 (인터뷰)
/lskun-kit:migrate-schema
```

## 출력 예 (Migration Result)

```
Migration Plan
================================================
backend       : vault
company root  : /Users/.../obsidian-vault/03_Companies/LSKun
company.md    : detected schema=v0.2, missing=['domain']
workers:
  - cpo: schema=v0.2, missing=['domain', 'display_name']
  - hr-lead: schema=v0.2, missing=['domain', 'display_name']
CLAUDE.md     : /Users/.../AIMBTI/CLAUDE.md (marker 부재 — 박제 필요)
```

사용자 인터뷰 후:

```
Migration Result
================================================
company.md    : updated
workers       : cpo, hr-lead
CLAUDE.md     : created
backups       : 3 files
  - .../company.md.lskun-pre-migrate.bak
  - .../hired/cpo.md.lskun-pre-migrate.bak
  - .../hired/hr-lead.md.lskun-pre-migrate.bak
```

## doctor 와의 관계

`/lskun-kit:doctor` 의 [5] / [10] / [11] 항목이 ⚠️ / ❌ 일 때 본 명령으로 안내된다.
실행 후 doctor 를 다시 돌리면 모두 ✅ 가 되어야 한다.

## 사양 참조

- ADR-0005 — 본 명령 도입 사유 / 안전 가드 / ADR-0004 §6 부분 supersede
- ADR-0003 — `domain` 필드 의미
- ADR-0004 §5 — `display_name` 사용자 입력 정책
- ADR-0004 §6 — frontmatter 6 필수 (본 ADR 가 일부 supersede)
- CLAUDE.md §1 — "마이그레이션은 LSKunCompanyKit 책임"

## Python 진입점

```python
from pathlib import Path
from lskun_kit import schema_migration as sm
from lskun_kit.adapters.local import LocalAdapter
from lskun_kit.init import detect_backend, resolve_company_root

backend, _ = detect_backend(Path.cwd())
_, _, company_root = resolve_company_root(Path.cwd())
adapter = LocalAdapter(company_root)

plan = sm.plan(adapter, company_root, backend, project_root=Path.cwd())
print(plan.render())

answers = sm.MigrationAnswers(
    company_domain="의료 SaaS",
    worker_display_names={"cpo": "이세근", "hr-lead": "김지혜"},
)
result = sm.execute(adapter, plan, answers)
print(result.render())
```
