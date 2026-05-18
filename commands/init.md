---
name: lskun-kit:init
description: 신규 회사 셋업 — backend 결정, company.md 박제, CPO/HR 자동 hire, CLAUDE.md 에 CPO persona inline 박제 (ADR-0002 §3 + ADR-0004 §1·§5)
arguments:
  - name: company
    description: 회사 이름 (Vault backend 필수, Local 은 생략 가능)
    required: false
  - name: one_liner
    description: 회사 한 줄 소개 (company.md 본문에 들어감)
    required: false
---

# /lskun-kit:init

새 회사를 단일 진입점으로 셋업한다. ADR-0002 §3 + ADR-0004 §1·§5 의 정식 명령.

## 인터뷰 (Claude 가 사용자에게 순차 질문)

본 명령이 호출되면 Claude 는 다음 4가지를 사용자에게 묻는다 (CLI 인자로 일부가 전달됐으면 해당 질문 skip):

1. **회사 이름** (Vault backend 일 때 필수, Local 은 디렉토리 이름 fallback)
2. **회사 한 줄 소개** (생략 가능, company.md 본문에 들어감)
3. **회사 도메인** — 자유 입력 (예: "의료 SaaS", "핀테크", "K-POP 팬덤") — ADR-0003. 빈 값이면 doctor 가 경고로 안내.
4. **CPO 의 사람 이름 (`display_name`)** — ADR-0004 §5. 자유 입력. **자동 생성 금지** — 사용자가 직접 입력.
5. **HR Lead 의 사람 이름 (`display_name`)** — 동일.

## 동작 (멱등)

1. **활성 backend 결정**
   - `LSKUN_VAULT` 환경변수 있음 → Vault backend
   - 없음 → Local backend (`<project-root>/.company/`)
2. **회사 루트 디렉토리 생성** (기존 디렉토리 있으면 그대로 재사용)
3. **company.md 박제** — 이미 있으면 **절대 덮어쓰지 않음** (보존 정책). frontmatter 에 `domain` 박제.
4. **CPO + 인사팀장(hr-lead) 자동 hire** — 이미 있으면 skip. frontmatter 6 필수 필드 (`name`, `role`, `domain="meta"`, `hired_at`, `storage_backend`, `display_name`) + HR Lead 는 optional `model: sonnet`.
5. **CPO persona inline 박제 (ADR-0004 §1)** — 사용자 프로젝트 root 의 `CLAUDE.md` 에 marker 구간 (`<!-- LSKUN-CPO:START -->` ~ `<!-- LSKUN-CPO:END -->`) 으로 hired/cpo.md 의 본문 박제. 기존 CLAUDE.md 본문은 보존, marker 구간만 갱신.
6. 결과 진단 리포트 출력

## 사용 예

```bash
# Local backend (가장 가벼움)
/lskun-kit:init

# Vault backend
export LSKUN_VAULT="$HOME/Documents/private-workspaces/obsidian-vault"
/lskun-kit:init Acme "AI agents for SMB compliance"
```

## 출력 예

```
LSKunCompanyKit init
================================================
backend       : vault
company       : Acme
company root  : /Users/.../obsidian-vault/03_Companies/Acme
company.md    : created → /Users/.../03_Companies/Acme/company.md
workers hired : cpo, hr-lead
CPO persona   : created → /Users/.../my-project/CLAUDE.md
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

## 사양 참조

- ADR-0002 §3 — init 명령 도입 사유 / 동작 정의
- ADR-0002 §1~§2 — auto-hire 되는 CPO / 인사팀장 의 책임 범위
- ADR-0001 §5 — SSOT 분리 정책 (init 도 본 규칙 준수)
- ADR-0003 — `domain` 필드 박제
- ADR-0004 §1 — CPO persona 의 CLAUDE.md inline 박제 (메인 세션 = CPO)
- ADR-0004 §5 — `display_name` 사용자 직접 입력 정책 (자동 생성 금지)
- ADR-0004 §6 — frontmatter 6 필수 + optional `model`
