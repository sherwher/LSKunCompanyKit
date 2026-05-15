---
name: lskun-kit:migrate
description: 사용자 SSOT 를 backend 간 이동 (Local ↔ Vault), 체크섬 검증과 dry-run 지원
arguments:
  - name: from
    description: source spec — "local:<path>" 또는 "vault:<vault_path>:<company>"
    required: true
  - name: to
    description: target spec — 동일 포맷
    required: true
  - name: dry_run
    description: "true" 일 경우 plan 만 출력하고 디스크 변경 없음
    required: false
---

# /lskun-kit:migrate

사용자 SSOT 의 위치를 backend 간 단방향 이동한다.

## 동작

1. `--from` 과 `--to` 파싱:
   - `local:<path>` → `LocalAdapter(<path>)`
   - `vault:<vault>:<company>` → `VaultAdapter(<vault>, <company>)`
2. `lskun_kit.migration.plan(source, target_root, target_backend)` 로 plan 출력
3. `--dry-run=true` 면 plan 만 출력하고 종료
4. 그렇지 않으면 `execute(...)` 호출:
   - target 의 임시 디렉토리 (`_migrating-<ts>-<name>/`) 로 복사
   - 각 파일 SHA-256 일치 검증
   - 워커 frontmatter 의 `storage_backend` 를 target backend 로 자동 갱신
   - atomic-ish swap (rename) 으로 target 정식 자리로 이동
   - 실패 시 임시 디렉토리 자동 정리, target 은 빈 채로 남음

## 예시

```
/lskun-kit:migrate \
    --from=local:/Users/me/myproj/.company \
    --to=vault:/Users/me/Vault:LSKun \
    --dry-run=true
```

출력:
```
Migration plan: local → vault
  source: /Users/me/myproj/.company
  target: /Users/me/Vault/03_Companies/LSKun
  workers: 3 (alice, bob, carol)
  company.md: yes
  files: 4, bytes: 8421
```

## 보장 사항 (ADR-0001 §검증 KPI: Migration 무결성 데이터 손실 0)

- ✅ 체크섬 검증 (SHA-256) — 전송 중 손실 0
- ✅ target 이 비어 있지 않으면 거부 (덮어쓰기 사고 방지)
- ✅ 실패 시 target 변경 없음 (rename 직전까지 staging 에서만 작업)
- ✅ frontmatter `storage_backend` 자동 갱신 → doctor 의 cross-validation 통과
- ❌ 부분 / 점진 마이그레이션 미지원 (v0.2+)
- ❌ 양방향 동기화 미지원 (단방향 이동만)

`docs/migration-spec.md` 참조.
