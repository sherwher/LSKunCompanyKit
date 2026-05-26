---
name: lskun-kit:sync-out
description: ~/.lskun-companies/<name>/ → 외부 mirror (vault 등) 로 회사 자원 복사. target 백업 자동 생성 (ADR-0015 결정 5)
arguments:
  - name: company
    description: 회사 이름 (예 - "LSKun"). ~/.lskun-companies/<company>/ 가 source
    required: true
  - name: target
    description: 외부 mirror target 경로 (예 - "~/vault/03_Companies/LSKun")
    required: true
---

# /lskun-kit:sync-out

Local SSOT (`~/.lskun-companies/<name>/`) 에서 외부 mirror 로 회사 자원을 복사한다.

ADR-0015 결정 5 — Plugin core 는 vault 를 직접 참조하지 않는다. Sync 는 명시적 액션이며 파일시스템 복사 (`shutil.copytree`) 만 사용.

## 동작 (멱등 가드 + 백업 안전망)

1. **인자 파싱** — `company` 이름 검증, `target` expanduser + resolve
2. **첫 호출 (confirmed=False)** — `ConfirmRequired` 예외 raise. caller (LLM) 가 사용자에게 출력 후 y/N 입력 받음
3. **사용자 y 입력 → 재호출 (`confirmed=True`)**:
   - target 이 존재하면 통째 `<target>.lskun-backup-<YYYYMMDD-HHMMSS>/` 로 백업 (target 측 sibling — 결정 5-B)
   - target 삭제 후 source (`~/.lskun-companies/<name>/`) 통째 복사
4. **결과 리포트 출력**

## 충돌 정책 (결정 5-B)

- **target 덮어쓰기** (양방향 merge 미도입)
- **사용자 confirm 강제**
- **target 백업 자동 생성** (target 측 sibling 위치)

## 백업 정책

- 위치: `<target>.lskun-backup-<timestamp>/` (target 측 별도, 결정 5-B)
- `--target-backup-root` 인자로 통합 위치 override 가능
- **자동 삭제 / rotation 없음** — 사용자 책임

## 사용 예

```bash
# Local 변경 사항을 vault 로 push (백업 vault 의 기존 폴더가 통째 백업됨)
/lskun-kit:sync-out LSKun ~/vault/03_Companies/LSKun

# USB 백업
/lskun-kit:sync-out Acme /Volumes/usb/Acme-backup
```

## 출력 예

```
LSKunCompanyKit sync-out
================================================
company       : LSKun
source        : /Users/me/.lskun-companies/LSKun
target        : /Users/me/vault/03_Companies/LSKun
backup        : /Users/me/vault/03_Companies/LSKun.lskun-backup-20260522-143052
files copied  : 87
bytes copied  : 1245678
note          : 기존 target 백업: /Users/me/vault/03_Companies/LSKun.lskun-backup-20260522-143052
```

## Python 진입점

```python
from pathlib import Path
from lskun_kit import sync
from lskun_kit.errors import ConfirmRequired

try:
    sync.sync_out("LSKun", Path("~/vault/03_Companies/LSKun"))
except ConfirmRequired as e:
    print(e.prompt)
    # if user_answers_yes:
    result = sync.sync_out("LSKun", Path("~/vault/03_Companies/LSKun"),
                           confirmed=True)
    print(result.render())
```

## 금지 사항 (ADR-0015)

- ❌ 양방향 자동 merge
- ❌ 자동 스케줄링
- ❌ 외부 SDK 호출
- ❌ 백업 자동 삭제 / rotation
- ❌ 회사 SSOT 의 git 자동 commit / push

## doctor 와의 관계

`/lskun-kit:doctor` 의 [7] (Sync 명령 등록) 에서 본 명령의 호환성 검증.
