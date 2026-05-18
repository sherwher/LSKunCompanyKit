---
name: lskun-kit:role-init
description: 기존 프로젝트에 .claude/lskun-kit.json 회사 link 박제 (ADR-0007 §6 backfill). 이미 init 된 프로젝트가 ADR-0007 도입 전에 생성된 경우 본 명령으로 1회 마이그레이션
---

# /lskun-kit:role-init

`.claude/lskun-kit.json` (ADR-0007 §3) 을 사용자 프로젝트에 박제·갱신한다. 회사 SSOT 자체는 건드리지 않으며 link 파일만 박는다.

## 동작

1. 사용자에게 회사 이름을 묻는다 (활성 backend 의 회사 후보 중 선택, 또는 자유 입력)
2. backend 자동 감지 (`LSKUN_VAULT` 환경변수 → vault, 없으면 local)
3. 회사 SSOT 가 실제로 존재하는지 검증 (`<vault>/03_Companies/<name>/` 또는 `<project>/.company/`)
4. `.claude/lskun-kit.json` 박제:
    - 부재 → 생성
    - 동일 내용 존재 → preserved (idempotent)
    - 다른 내용 존재 → 사용자 confirm 후 `overwrite=True`
5. 결과 리포트 출력

## 인자

```
/lskun-kit:role-init                         # 인터뷰 모드
/lskun-kit:role-init <company>               # 회사 이름 직접
/lskun-kit:role-init <company> --backend=vault   # backend override
/lskun-kit:role-init <company> --force        # 다른 내용 존재 시 자동 overwrite
```

## 안전 가드

- 회사 SSOT 부재 시 **거부** — "회사 SSOT 가 존재하지 않는다. 먼저 `/lskun-kit:init <company>` 실행 권장"
- 다른 회사를 가리키는 link 존재 시 — 사용자 명시 confirm 필요 (`--force` 또는 인터뷰)
- 회사 디렉토리에 워커 1명도 hired 안 됐으면 ⚠️ 알림 후 진행 (link 만 박는 게 본 명령의 책임이므로 차단하지 않음)

## 출력 예시

```
LSKunCompanyKit role-init
================================================
project root  : /Users/sk.lee/Documents/.../acme-web
backend       : vault
company       : Acme
company root  : <vault>/03_Companies/Acme
link file     : created → /Users/sk.lee/Documents/.../acme-web/.claude/lskun-kit.json

결과: link 박제 완료. 다음 세션부터 SessionStart hook 이 Acme 회사 컨텍스트를 자동 주입한다.
```

## 구현 노트

본 사양의 외부 동작 정의. 실제 박제 로직은:

- `lskun_kit.project_link.write(project_root, ProjectLink(...), overwrite=...)`
- backend 자동 감지: `lskun_kit.init.detect_backend()`
- 회사 SSOT 검증: 해당 backend adapter 의 `root` path 존재 확인

`init` 의 일부 동작 (CPO/HR auto-hire, persona 박제) 은 본 명령 책임이 아니다. 이미 init 된 회사에 link 만 더해서 ADR-0007 마이그레이션 경로를 완성한다.
