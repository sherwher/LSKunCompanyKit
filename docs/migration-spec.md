# Migration Specification (v0.1.0-dev)

> ADR-0001 의 "Migration tool 은 LSKunCompanyKit 책임" + "Migration 무결성: 데이터 손실 0" KPI 를 구현하는 사양. P7 에서 박제.

## 1. 왜 LSKunCompanyKit 책임인가

Storage backend 추상화의 의미는 사용자가 backend 선택권을 가지면서도, 결정 변경 비용이 0 에 수렴해야 한다는 것. 사용자가 `Local` 로 시작했다가 `Vault` 로 옮기고 싶을 때, 직접 파일을 옮기다 frontmatter `storage_backend` 갱신을 빠뜨리거나 일부 파일을 손실하는 일이 없어야 한다.

→ Migration tool 이 backend 의 일급 시민 (first-class citizen) 으로 함께 박제된다.

## 2. 흐름

```
plan(source, target_root, target_backend)
   ↓
[dry-run 이면 여기서 종료]
   ↓
staging = <target_root>/../_migrating-<ts>-<name>/
   ↓
   1. company.md (있으면) 복사 → SHA-256 검증
   2. 각 worker:
        hired/<name>.md 복사 → SHA-256 검증
        frontmatter.storage_backend 를 target_backend 로 갱신
   ↓
swap: staging/* → target_root/*  (rename 으로 원자성 근사)
```

## 3. 보장 사항

| 보장 | 구현 |
|---|---|
| 데이터 손실 0 | SHA-256 체크섬을 source / staging 양쪽 비교 |
| 부분 실패 안전 | 모든 작업이 staging 에서 진행. swap 직전까지 target 변경 없음. 실패 시 staging 자동 정리 |
| 덮어쓰기 사고 방지 | target_root 가 비어있지 않으면 즉시 `MigrationError` |
| backend metadata 일관성 | frontmatter `storage_backend` 자동 갱신 → doctor 검증 통과 |
| Idempotent dry-run | `dry_run=True` 일 때 디스크 변경 0 |

## 4. 비범위 (v0.1 의도적 미지원)

- **부분 / 점진 마이그레이션** — N명 워커 중 일부만 이동 X. 전부 또는 전무.
- **양방향 동기화** — `migrate --bidirectional` 같은 모드 없음. 한 시점에 단방향만.
- **동시 마이그레이션** — 두 사용자 / 두 PC 가 같은 source 를 동시에 migrate X. 호출자 책임.
- **Atomic 보장 (POSIX 의미)** — rename 은 같은 파일시스템 안에서만 atomic. 서로 다른 파일시스템 (e.g. `.company` → 외부 디스크 vault) 일 경우 swap 이 여러 syscall 로 쪼개진다.

## 5. 에러 모드

| 상황 | 결과 |
|---|---|
| target 이 비어있지 않음 | `MigrationError`, 디스크 변경 0 |
| SHA-256 불일치 | `MigrationError`, staging 자동 정리, target 빈 채 |
| source 의 워커가 schema 위반 | `InvalidWorkerSchemaError` (read_worker 단계) → staging 자동 정리 |
| 권한 부족 / 디스크 가득 | OS 예외 그대로 전파, staging 자동 정리 |

target 디렉토리는 swap 성공 직전까지 항상 비어있는 상태로 유지된다 → "실패해도 망가지지 않는다" 보장.

## 6. CLI 매핑 (slash command)

`/lskun-kit:migrate` 는 본 모듈의 `plan` / `execute` 를 래핑한다.
파싱은 `commands/migrate.md` 에 정의된 `--from` / `--to` / `--dry-run` 인자를 따른다.

## 7. 도그푸딩에서 검증할 것 (P8)

- Local (1 프로젝트) → Vault (LSKun company) 실제 마이그레이션
- 멀티 PC: 한 PC 에서 migrate 후 다른 PC 에서 Vault sync 결과 정상 인식
- 50+ legacy history entry (ADR-0014 의 `## Archived History (pre-0.18)`) 가 있는 워커에서 frontmatter 갱신 정확
- 비정상 상황 (target 디렉토리에 사용자가 우발적으로 파일을 둠) 거부 메시지가 명확한지

## 8. 향후 확장 (v0.2+)

- `lskun_kit.migration.plan` 의 반환에 dry-run output 외에 diff/preview 추가
- Notion / HTTP backend 가 추가되면 동일 module 의 `_infer_backend` + `_swap_into` 확장
- 호환성 깨지는 schema 변경 시 (e.g. ADR-0014 의 `## Project History` → `## Archived History (pre-0.18)` rename) migration 이 schema 변환도 책임
