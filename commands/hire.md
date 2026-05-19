---
name: lskun-kit:hire
description: 신규 워커 박제 — hired/<name>.md 파일을 필수 frontmatter (name/role/domain/hired_at/storage_backend/display_name) + optional model 과 함께 생성
arguments:
  - name: worker
    description: 워커 이름 (kebab-case 권장)
    required: true
  - name: role
    description: 워커 역할 (backend-engineer, designer, pm 등)
    required: true
  - name: display_name
    description: 사람 이름 (예 - "Alex Kim"). 자유 입력 필수.
    required: true
  - name: domain
    description: 회사 도메인 (예 - "의료 SaaS") 또는 "meta" (도메인 무관). 생략 시 회사 company.md 의 domain 상속.
    required: false
  - name: model
    description: "sonnet" / "opus" / 모델 ID. 생략 시 default ("sonnet").
    required: false
---

# /lskun-kit:hire

신규 워커를 사용자 SSOT 에 박제한다. `domain` / `display_name` / `model` 필드를 자동·인자 기반으로 채운다.

## 동작

1. 활성 backend 결정:
   - `LSKUN_VAULT` 환경변수 → Vault backend
   - 없으면 현재 디렉토리의 `.company/` (Local backend)
2. 다음 frontmatter 로 `hired/<worker>.md` 생성:

```yaml
---
name: <worker>
role: <role>
domain: <domain or company.domain or "meta">
hired_at: <오늘 ISO 날짜>
storage_backend: <local|vault>
display_name: <사람 이름>
model: <"sonnet" | "opus" | 모델 ID>   # optional, 생략 시 default
---

# <worker>

## Project History

_(empty — first task will append the first line)_
```

3. 이미 존재하면 ❌ 와 함께 거부한다 (덮어쓰기 방지).

## 사용 예

```bash
# 회사 도메인 상속 + default model
/lskun-kit:hire alice backend-engineer "앨리스 박"

# 도메인 명시 + Opus
/lskun-kit:hire security-architect security-architect "Sarah Chen" --domain="핀테크" --model=opus

# 도메인 무관 (meta)
/lskun-kit:hire qa qa-engineer "Mike Lee" --domain=meta
```

## Python 진입점

```python
from datetime import date
from lskun_kit.adapters.local import LocalAdapter

adapter = LocalAdapter(".company")
adapter.create_worker(
    name="alice",
    frontmatter_dict={
        "name": "alice",
        "role": "backend-engineer",
        "domain": "의료 SaaS",
        "hired_at": date.today().isoformat(),
        "storage_backend": "local",
        "display_name": "앨리스 박",
        # "model": "opus",  # optional
    },
    body="# alice\n\n## Project History\n\n_(empty)_\n",
)
# 해고는 adapter.archive_worker("alice") — hired/ → archived/ 이동, 삭제 X
```

``frontmatter.dump`` + ``path.write_text`` 직접 호출은 외부 add-on
이 파일 쓰기가 아닌 호출 기반 backend 를 구현할 때 깨진다. adapter API 를
경유해야 backend 추상화가 유지된다 (core 는 파일 기반 Local/Vault
만, 외부 시스템 통합은 add-on 책임).

## CPO 자동 채용과의 관계

CPO 가 부재 워커를 발견하면 HR Lead 를 Task tool 로 호출해 **자동 채용**. 본 `/lskun-kit:hire` 는 사용자가 직접 호출하거나 HR Lead persona 의 내부 동작이 사용하는 **primitive**.

```
사용자 요청 → CPO → 적합 워커 없음 → HR Lead Task dispatch
   → HR 가 본 hire 동작 수행 → [채용 알림] 1줄 → CPO 가 신규 워커 dispatch
```

### Audit log + Rate-limit

자동 채용 (HR Lead 가 actor) 은 `<company_root>/hired/.audit.jsonl` 에 1줄씩 기록되며 같은 `role + domain` 으로 30분 내 재채용 시 `HireRateLimited` 로 차단된다. 사용자가 본 명령을 직접 호출 (`actor="user"`) 하면 rate-limit 을 통과한다 — 사람의 결정은 신뢰. 자세한 구조는 `lskun_kit.hire_audit` 모듈.
