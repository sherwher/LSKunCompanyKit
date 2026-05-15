---
name: lskun-kit:hire
description: 신규 워커 박제 — hired/<name>.md 파일을 frontmatter 4 필수 필드와 함께 생성
arguments:
  - name: worker
    description: 워커 이름 (kebab-case 권장)
    required: true
  - name: role
    description: 워커 역할 (backend-engineer, designer, pm 등)
    required: true
---

# /lskun-kit:hire

신규 워커를 사용자 SSOT 에 박제한다.

## 동작

1. 활성 backend 결정:
   - `LSKUN_SSOT_ROOT` 환경변수 우선
   - 없으면 현재 디렉토리의 `.company/` (LocalAdapter)
2. 다음 frontmatter 로 `hired/<worker>.md` 생성:

```yaml
---
name: <worker>
role: <role>
hired_at: <오늘 ISO 날짜>
storage_backend: <local|vault>
---

# <worker>

## Project History

_(empty — first task will append the first line)_
```

3. 이미 존재하면 ❌ 와 함께 거부한다 (덮어쓰기 방지).

## 사양

ADR-0001 §3 의 Reflection 메커니즘에 필요한 4 필수 필드 (`name`, `role`, `hired_at`, `storage_backend`) 를 채워야만 이후 `/work` / `/reflect` 가 동작한다. 본 명령은 그 진입점.

`docs/reflection-spec.md` §3 워커 frontmatter schema 참조.
