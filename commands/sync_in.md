---
name: lskun-kit:sync-in
description: 외부 mirror (vault 등) → ~/.lskun-companies/<name>/ 로 회사 자원 복사. local 백업 자동 생성 (ADR-0015 결정 5)
arguments:
  - name: company
    description: 회사 이름 (예 - "LSKun"). ~/.lskun-companies/<company>/ 으로 복사됨
    required: true
  - name: source
    description: 외부 mirror 경로 (예 - "~/vault/03_Companies/LSKun"). 디렉토리만 허용
    required: true
---

# /lskun-kit:sync-in

외부 mirror 에서 Local SSOT (`~/.lskun-companies/<name>/`) 로 회사 자원을 복사한다.

ADR-0015 결정 5 — Plugin core 는 vault 를 직접 참조하지 않는다. Sync 는 명시적 액션이며 파일시스템 복사 (`shutil.copytree`) 만 사용. Vault 가 Obsidian / Notion local cache / Dropbox / 외장 디스크 / git submodule 무엇이든 plugin 은 모름.

## 동작 (멱등 가드 + 백업 안전망)

1. **인자 파싱** — `company` 이름 검증 (`paths.validate_company_name`), `source` 경로 expanduser + resolve
2. **첫 호출 (confirmed=False)** — `ConfirmRequired` 예외 raise. caller (LLM) 가 다음 정보를 사용자에게 출력 후 y/N 입력 받음:
   - 방향: 외부 mirror → Local SSOT
   - source / target / backup path
   - target 기존 내용 덮어쓰기 경고 (target 부재 시 "신규 생성" 안내)
3. **사용자 y 입력 → 재호출 (`confirmed=True`)**:
   - target (`~/.lskun-companies/<name>/`) 이 존재하면 통째 `~/.lskun-companies/.backups/<name>/<YYYYMMDD-HHMMSS>/` 로 백업
   - target 삭제 후 source 통째 복사 (`shutil.copytree`)
4. **결과 리포트 출력** — files / bytes / backup 위치

## 충돌 정책 (결정 5-B)

- **local 덮어쓰기** (양방향 merge 미도입)
- **사용자 confirm 강제**
- **local 백업 자동 생성** (회사 SSOT 디렉토리 외부 통합 위치)

## 백업 정책 (결정 5-E)

- 위치: `~/.lskun-companies/.backups/<name>/<timestamp>/`
- timestamp: `YYYYMMDD-HHMMSS`
- **자동 삭제 / rotation 없음** — 사용자 책임
- 정리: `~/.lskun-companies/.backups/` 에서 수동 삭제

## 사용 예

```bash
# 기존 vault 사용자가 본 plugin 으로 처음 마이그레이션
/lskun-kit:sync-in LSKun ~/vault/03_Companies/LSKun

# 다른 PC 에서 받은 mirror 를 local 로 복원
/lskun-kit:sync-in Acme /Volumes/usb/Acme-export
```

## 출력 예

```
LSKunCompanyKit sync-in
================================================
company       : LSKun
source        : /Users/me/vault/03_Companies/LSKun
target        : /Users/me/.lskun-companies/LSKun
backup        : /Users/me/.lskun-companies/.backups/LSKun/20260522-143052
files copied  : 87
bytes copied  : 1245678
note          : 기존 local 백업: /Users/me/.lskun-companies/.backups/LSKun/20260522-143052
```

## Python 진입점

```python
from pathlib import Path
from lskun_kit import sync
from lskun_kit.errors import ConfirmRequired

# 1차 호출 → ConfirmRequired raise (caller 가 사용자에게 묻기)
try:
    sync.sync_in("LSKun", Path("~/vault/03_Companies/LSKun"))
except ConfirmRequired as e:
    print(e.prompt)  # 사용자에게 출력 + y/N 입력 받기
    # if user_answers_yes:
    result = sync.sync_in("LSKun", Path("~/vault/03_Companies/LSKun"),
                          confirmed=True)
    print(result.render())
```

## 금지 사항 (ADR-0015)

- ❌ 양방향 자동 merge — 사용자가 시점 선택
- ❌ 자동 스케줄링 (cron / hook 자동 실행) — 사용자 명시 실행만
- ❌ 외부 SDK (Obsidian API / Notion SDK 등) — 파일시스템 복사만
- ❌ 백업 자동 삭제 / rotation — 사용자 책임
- ❌ 회사 SSOT 디렉토리 안에 backup 박제 — `.backups/` 별도 위치만

## doctor 와의 관계

`/lskun-kit:doctor` 의 [3] (Storage backend), [7] (Sync 명령 등록) 에서 본 명령의 호환성 검증.
