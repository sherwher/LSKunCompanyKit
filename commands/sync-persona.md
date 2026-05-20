---
name: lskun-kit:sync-persona
description: 메타 워커 (CPO / HR Lead) 의 persona body 를 plugin 의 최신 template 본문으로 sync. frontmatter / Project History 절대 보존, idempotent, 자동 백업
---

# /lskun-kit:sync-persona

활성 backend 의 `hired/cpo.md` + `hired/hr-lead.md` 의 **body 본문만** plugin 의 최신 `templates/{cpo,hr-lead}.md` 와 sync. frontmatter (사용자 personalize) 와 `## Project History` (자동 누적 reflection) 는 **한 글자도 건드리지 않는다**.

## 사용

```
/lskun-kit:sync-persona               # plan (dry-run, diff 표시)
/lskun-kit:sync-persona --execute     # 실행 (백업 + provenance 박제)
/lskun-kit:sync-persona cpo           # 특정 메타 워커만 plan
/lskun-kit:sync-persona cpo --execute # 특정 메타 워커만 실행
```

## 동작

1. 활성 backend 의 `hired/cpo.md` / `hired/hr-lead.md` 로드
2. plugin 의 `src/lskun_kit/templates/cpo.md` / `hr-lead.md` 와 body 본문 비교
3. plan 출력:
    - `body          : OK` 또는 `STALE — needs sync`
    - `provenance    : OK` 또는 `missing/stale (current=..., target=lskun-kit@<version>)`
4. `--execute` 시:
    - 변경 발생 워커마다 자동 백업 (`<file>.lskun-pre-sync.bak`, 이미 있으면 timestamp 추가)
    - body 본문만 교체. frontmatter 의 모든 기존 키 보존
    - `## Project History` 섹션 절대 보존
    - frontmatter 에 `persona_synced_from: lskun-kit@<version>` + `persona_synced_at: <YYYY-MM-DD>` 박제

## Idempotent 보장

- 이미 sync 된 상태에서 재실행 → body 변경 0, 백업 0
- body 는 sync 됐지만 provenance 가 부재인 케이스 (기존 회사) → provenance 만 박제, 백업 1회
- 완전히 일치하는 상태에서 재실행 → no-op 결과 리포트

## 안전 가드

- 메타 워커 (`cpo`, `hr-lead`) **만** 대상. 일반 워커 (사용자 hire) 는 sync 대상 아님
- `## Project History` 한 줄도 변경 금지
- frontmatter 기존 키 (`display_name` / `model` / `domain` 등) 절대 덮어쓰기 금지 — provenance 2개 키만 갱신
- 변경 전 백업 강제

## 출력 예 (plan)

```
Persona Sync Plan
================================================
backend          : vault
company root     : <your-vault>/03_Companies/<company>
plugin version   : <plugin-version>

[cpo] <your-vault>/03_Companies/<company>/hired/cpo.md
  body          : OK
  provenance    : missing/stale (current=None, target='lskun-kit@<plugin-version>')
  action        : sync
[hr-lead] <your-vault>/03_Companies/<company>/hired/hr-lead.md
  body          : STALE — needs sync
  provenance    : missing/stale (current=None, target='lskun-kit@<plugin-version>')
  action        : sync
```

## 출력 예 (execute)

```
Persona Sync Result
================================================
[cpo] provenance
  backup        : <your-vault>/.../hired/cpo.md.lskun-pre-sync.bak
[hr-lead] body, provenance
  backup        : <your-vault>/.../hired/hr-lead.md.lskun-pre-sync.bak
```

## 구현 노트

실제 로직: `lskun_kit.persona_sync.plan(adapter, plugin_version)` → diff 표시 → `execute(adapter, plan)`.

`/lskun-kit:migrate-schema` 와 동일한 plan → confirm → execute 패턴. 백업·history 보존 가드 재사용.
