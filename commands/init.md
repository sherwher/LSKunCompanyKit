---
name: lskun-kit:init
description: 신규 회사 셋업 — Local SSOT 단일 backend (ADR-0015), company.md 생성, CPO/HR Lead 자동 hire, 사용자 프로젝트 CLAUDE.md 에 CPO persona inline 박제
arguments:
  - name: company
    description: 회사 이름 (생략 시 project 디렉토리명 fallback)
    required: false
  - name: one_liner
    description: 회사 한 줄 소개 (company.md 본문에 들어감)
    required: false
---

# /lskun-kit:init

새 회사를 단일 진입점으로 셋업한다.

## 인터뷰 (Claude 가 사용자에게 순차 질문)

본 명령이 호출되면 Claude 는 다음 5가지를 사용자에게 묻는다 (CLI 인자로 일부가 전달됐으면 해당 질문 skip):

1. **회사 이름** (생략 시 project 디렉토리명 fallback. P87 의 멱등성 분기 4행에서 marker 회사명과 cross-check)
2. **회사 한 줄 소개** (생략 가능, company.md 본문에 들어감)
3. **회사 도메인** — 자유 입력 (예: "의료 SaaS", "핀테크", "K-POP 팬덤"). 빈 값이면 doctor 가 경고로 안내.
4. **CPO 의 사람 이름 (`display_name`)** — 자유 입력. **자동 생성 금지** — 사용자가 직접 입력.
5. **HR Lead 의 사람 이름 (`display_name`)** — 동일.

## 동작 (멱등)

ADR-0015 (2026-05-22) — Local SSOT 단일 backend. Vault 통합은 `/lskun-kit:sync-in` / `/lskun-kit:sync-out` (P90) 의 파일시스템 복사로만 수행.

1. **회사 root 결정** — 현재는 `<project-root>/.company/` (P86 에서 `~/.lskun-companies/<name>/` 로 이전 예정)
2. **회사 루트 디렉토리 생성** (기존 디렉토리 있으면 그대로 재사용)
3. **company.md 박제** — 이미 있으면 **절대 덮어쓰지 않음** (보존 정책). frontmatter 에 `domain` 박제.
4. **CPO + 인사팀장(hr-lead) 자동 hire** — 이미 있으면 skip. frontmatter 6 필수 필드 (`name`, `role`, `domain="meta"`, `hired_at`, `storage_backend`, `display_name`) + HR Lead 는 optional `model: sonnet`.
5. **CPO persona inline 박제** — 사용자 프로젝트 root 의 `CLAUDE.md` 에 marker 구간 (`<!-- LSKUN-CPO:START -->` ~ `<!-- LSKUN-CPO:END -->`) 으로 hired/cpo.md 의 본문 박제. 기존 CLAUDE.md 본문은 보존, marker 구간만 갱신.
6. 결과 진단 리포트 출력

## 사용 예

```bash
# Local SSOT 단일 backend (ADR-0015 — self-contained, 외부 의존성 0)
/lskun-kit:init Acme "AI agents for SMB compliance"
```

## 출력 예

```
LSKunCompanyKit init
================================================
backend       : local
company       : Acme
company root  : <your-project>/.company
company.md    : created → <your-project>/.company/company.md
workers hired : cpo, hr-lead
CPO persona   : created → <your-project>/CLAUDE.md
```

## 구현

Python 백엔드: `lskun_kit.init.run(project_root, company_name=?, one_liner=?, domain=?, cpo_name=?, hr_name=?, inject_persona=True)`.

```python
from pathlib import Path
from lskun_kit.init import run

result = run(
    Path.cwd(),
    company_name="Acme",
    one_liner="AI agents for SMB compliance",
    domain="의료 SaaS",
    cpo_name="이세근",
    hr_name="김지혜",
)
print(result.render())
```

`inject_persona=False` 로 호출하면 CLAUDE.md 박제 skip (테스트 / dry-run 용도).

