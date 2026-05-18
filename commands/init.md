---
name: lskun-kit:init
description: 신규 회사 셋업 — backend 결정, company.md 박제, CPO/HR 자동 hire (ADR-0002 §3)
arguments:
  - name: company
    description: 회사 이름 (Vault backend 필수, Local 은 생략 가능)
    required: false
  - name: one_liner
    description: 회사 한 줄 소개 (company.md 본문에 들어감)
    required: false
---

# /lskun-kit:init

새 회사를 단일 진입점으로 셋업한다. ADR-0002 §3 의 정식 명령.

## 동작 (멱등)

1. **활성 backend 결정**
   - `LSKUN_VAULT` 환경변수 있음 → Vault backend
   - 없음 → Local backend (`<project-root>/.company/`)
2. **회사 루트 디렉토리 생성** (기존 디렉토리 있으면 그대로 재사용)
3. **company.md 박제** — 이미 있으면 **절대 덮어쓰지 않음** (보존 정책)
4. **CPO + 인사팀장(hr-lead) 자동 hire** — 이미 있으면 skip
5. 결과 진단 리포트 출력

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
```

## 구현

Python 백엔드: `lskun_kit.init.run(project_root, company_name=?, one_liner=?)`.

```python
from pathlib import Path
from lskun_kit.init import run

result = run(Path.cwd(), company_name="Acme", one_liner="...")
print(result.render())
```

## 사양 참조

- ADR-0002 §3 — init 명령 도입 사유 / 동작 정의
- ADR-0002 §1~§2 — auto-hire 되는 CPO / 인사팀장 의 책임 범위
- ADR-0001 §5 — SSOT 분리 정책 (init 도 본 규칙 준수)
