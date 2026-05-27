---
name: lskun-kit:audit-rotate
description: CPO 결재 audit log (.audit/decisions.jsonl) 의 옛 월 entry 를 gzip 으로 회전. 현재 월만 평문 jsonl 에 남김. 사용자 명시 명령만, 자동 회전 없음 (ADR-0006 정신, P109-B).
---

# /lskun-kit:audit-rotate

활성 backend 의 `.audit/decisions.jsonl` 누적 entry 를 월별로 분리. 현재 월 entry 만 평문 jsonl 에 남기고 옛 월은 `decisions.<YYYY-MM>.jsonl.gz` 로 gzip 묶음.

ADR-0006 (audit log 불변) 정합 — entry 내용은 한 줄도 수정·삭제 안 함. 단지 파일 분리. `/lskun-kit:org --usage` (P109-A) 가 회전된 파일도 읽으므로 view 정합성 100% 유지.

## 사용

```
/lskun-kit:audit-rotate                          # plan (dry-run)
/lskun-kit:audit-rotate --execute                # 실제 회전 수행
```

## 동작

1. 활성 backend 의 `<company_root>/.audit/decisions.jsonl` 읽기
2. 각 줄의 `ts` 필드에서 `YYYY-MM` 추출
3. 현재 월 (UTC 기준) entry → 평문 `decisions.jsonl` 잔존
4. 옛 월 entry → 월별 `decisions.<YYYY-MM>.jsonl.gz` 로 묶음
5. `--execute` 시:
   - gzip 파일 먼저 write (이미 있으면 append, idempotent)
   - 모두 성공 후 평문 jsonl 을 현재 월만 남기고 rewrite

## 원칙 (불변)

- **사용자 명시 명령만** — 자동 회전 X (ADR-0006 정신)
- **append-only 유지** — 옛 entry 내용 rewrite 절대 금지. 월별 묶기만 함
- **idempotent** — 재실행 시 이미 회전된 파일에 append (옛 데이터 손실 0)
- **atomic-ish** — gzip write → 원본 truncate. 중간 실패 시 데이터 손실 0
- **malformed 라인 보존** — JSON parse 실패 라인은 회전하지 않고 현재 월에 잔존 (사용자 수동 정리 권장)

## 출력 예 (plan)

```
Audit Log Rotation Plan
================================================
audit dir       : ~/.lskun-companies/<company>/.audit
current month   : 2026-05
current lines   : 12
malformed lines : 0 (skipped)

회전 대상       : 2 buckets
  - 2026-03: 8 entries → decisions.2026-03.jsonl.gz
  - 2026-04: 23 entries → decisions.2026-04.jsonl.gz
```

## 출력 예 (execute)

```
Audit Log Rotation Result
================================================
audit dir       : ~/.lskun-companies/<company>/.audit
current 잔존    : 12 lines
  - decisions.2026-03.jsonl.gz: 8 entries 박제
  - decisions.2026-04.jsonl.gz: 23 entries 박제

총 회전: 31 entries
```

## 구현 노트

실제 로직: `lskun_kit.audit_rotate.plan_rotation(audit_dir)` → confirm → `execute_rotation(plan)`. `/lskun-kit:sync-persona` 와 동일한 plan → confirm → execute 패턴.

doctor `[26]` (P109-B) 가 `decisions.jsonl` 크기를 모니터링하여 10 MB 초과 시 ℹ️ 회전 안내. 자동 실행 X (사용자 명시 정책 유지).
