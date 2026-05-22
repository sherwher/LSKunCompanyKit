# P78 계획 — `/org` h=N 카운트 정확화 + history narrative 압축 강제 (실측 재진단 후)

## 배경 (재진단)

1차 진단 ("38명이 실제로 h=0") 은 **부분 오류**. 실측:

### 실제 vault 상태 (8개 워커 history 박혀 있음)

| 워커 | 줄 수 | first-pass | 박힌 줄 길이 (대략) |
|---|---|---|---|
| `cpo.md` | 1 (실측) | 없음 ("first-pass 100% 승인" 만 본문) | 250자 |
| `chief-operating-officer.md` | 1 | `first-pass 자가 평가 88/100` | 200자 |
| `backend-implementation-engineer.md` | 2 | 첫 줄 부재, 둘째 줄 부재 | 약 1400자 + 900자 |
| `hr-lead.md` | 1 | 없음 | 100자 |
| `launch-ops-manager.md` | 1 | 없음 | 900자 |
| `qa-verification-engineer.md` | 1 | 없음 | 700자 |
| `analytics-engineer.md` | 1 | 없음 | 700자 |
| `dcodejob-product-expert.md` | 1 | `CPO first-pass 94/100 승인` 본문 | 800자 |

### `/org` 가 h=0 으로 잘못 표시한 이유

`org.py` h 카운트 정규식이 `first-pass` 문자열 포함 줄만 셈 (commands/org.md:69 "`first-pass` 줄을 카운트해 `h=N`"). 8명 중 **first-pass 점수가 줄 안에 명시된 워커는 2명만** → 나머지 6명도 h=0 으로 잘못 표시.

### history narrative 길이

ADR-0013 + P76 가 `HISTORY_FIELD_MAX_LEN=80` (topic / pattern 각 80자) 가드를 박았는데, 실제 박힌 줄들은 **400 ~ 1400자 단일 narrative**. P76 가드는 `record_from_report()` 경로에서만 작동하고, 옛 `record()` + **수동 vault 편집** 경로는 가드 우회. 이게 사용자가 말한 "뭉쳐있다" 의 실체.

## 두 진짜 문제

### 문제 1 — `/org` h=N 카운트 부정확

`first-pass` 가 없는 history 줄을 세지 못함. 8명 박혀 있는데 표시는 3명만.

### 문제 2 — history 줄당 narrative 폭주

P76 가드 (topic/pattern 80자) 가 다음 두 경로에서 미적용:
- **수동 편집**: 사용자가 vault 의 `hired/<worker>.md` 를 직접 열어 박은 줄
- **옛 record() 호출**: deprecation 경고만 띄우고 실제 가드는 받음 → 즉 옛 경로도 80자 가드는 작동
- **`record_from_report` 의 first-pass 정규식이 본문 어디서나 매칭** → topic/pattern 은 80자로 가드되지만 사용자가 그 외 영역에 narrative 박는 것은 가드 0

즉 plugin 의 입력 API 는 80자 가드를 갖지만 **vault 가 plain text 라서 우회 가능**.

## 합의안

### P78-1: `/org` h=N 카운트 정규식 수정 (즉시, 단순)

`org.py` 의 history 카운트 로직을 변경:

- **현재**: `"first-pass" in line` (대소문자 무관) 으로 카운트
- **변경**: `## Project History` 섹션 안의 `^- 20\d\d-\d\d-\d\d — ` 정규식 매칭 줄 수
- 부수효과: 다음 history 박힌 줄 형식 강제 (date 시작) — 이미 ADR-0001 §3 의 1줄 양식과 동일

영향:
- 41명 중 8명 실제 박힌 history 가 즉시 정확히 표시
- 기존 cpo.md 가 6 → 1 로 떨어지지만 그게 사실 (cpo.md 의 first-pass 6 카운트는 "first-pass" 문자열이 본문 narrative 안에 6번 나온 결과로, 실제 history 줄 수 아님)
- 회귀 위험: `org.py.build` 의 history 카운트만 변경. 테스트 추가.

### P78-2: history 줄 길이 가드 — 표시 단계에서 truncate

vault 가 plain text 라 **쓰기 가드는 한계**. 대신 **읽기 가드** 로 사용자에게 압축 강제:

- `/lskun-kit:org` 의 표시는 워커당 1줄 (이미 P74 compact). h=N 만 표시하면 narrative 길이는 무관.
- `doctor` 17번에 **"history 1줄 평균/최대 길이 가드"** 추가:
  - 평균 > 300자: ⚠️ "narrative 압축 권장. ADR-0001 §3 의 1줄 양식 위반"
  - 최대 > 500자: ⚠️ "특정 줄이 너무 김. 분할 또는 압축 권장"
- 자동 truncate / rewrite 금지 (사용자 자산 변형 금지)

### P78-3: 입력 시점 가드 강화 — `record()` 의 narrative 전체 길이 제한

현재 `record()` 는 topic / pattern 만 80자 가드. 전체 entry serialize 길이는 무가드. 추가:

- `HISTORY_LINE_MAX_LEN = 400` (date + project + topic + pattern + score + outcome + request_id 합)
- `record()` / `record_from_report()` 양쪽에 진입 가드. 초과 시 `ValueError` raise → CPO 가 보고 양식 재작업 지시
- 옛 워커 history (1400자 줄 등) 는 영향 X (사후 검증만, 자동 수정 0)

### P78-4: 사용자 명시 압축 도구 — `/lskun-kit:reflect --compact-existing`

기존 장문 history 를 사용자가 워커별로 검토·압축할 수 있는 보조 명령:

- dry-run: 워커별 평균/최대 길이 + 압축 후보 줄 제시
- confirm 후 사용자가 워커 1명씩 vault 의 `.md` 를 열어 압축 (plugin 은 안내만, 자동 변형 X)
- 자동 압축 금지 (LLM 이 사용자 자산 narrative 를 무단 요약하면 ADR-0013 §"자동 박제 금지" 결과 결 위반)

## 폐기 (의도적 X)

- **history 자동 압축 / rewrite** — 사용자 자산 변형 금지
- **vault history 무결성 hook** — write-time enforcement 는 plugin 이 vault 쓰기 모든 경로를 가로채야 가능 (Obsidian 직접 편집은 가로챌 수 없음)
- **`org-chart.md` 등 캐시** — P75 폐기 유지
- **first-pass 점수를 history 줄에 강제** — 옛 record() 가 점수를 받지만 vault 수동 편집은 점수 생략 가능. 강제는 plain text vault 와 충돌

## 검증

1. P78-1 후: `/lskun-kit:org` 실행 → 41명 중 cpo 1 / coo 1 / backend 2 / hr 1 / launch 1 / qa 1 / analytics 1 / dcodejob 1 = **8명에 h≥1 표시**, 나머지 33명은 정확히 h=0
2. P78-2 후: `/lskun-kit:doctor` 실행 → 평균 300자 초과 워커 목록 출력 (현재 LSKun 회사는 ~5명 해당 예상)
3. P78-3 후: `record(topic="...", pattern="...")` 호출이 합계 400자 초과 시 ValueError 즉시 raise
4. P78-4 후: `/lskun-kit:reflect --compact-existing` dry-run 출력이 8명 history 의 줄별 길이 표 제시
5. 274 tests + 신규 ~12 tests 통과

## 제약

- `org.py` 정규식 변경은 frontmatter `date` 필드 형식 (`YYYY-MM-DD`) 가정. ADR-0001 §3 양식과 일치.
- `HISTORY_LINE_MAX_LEN=400` 은 신규 박제만 영향. 기존 1400자 줄은 P78-4 사용자 명시 트리거 외에는 안 건드림.
- vault 가 plain text 라 100% write-time enforcement 불가. **읽기 가드 + 안내 + 사용자 압축** 의 3단 방어선이 최선.

## 다음 단계

1. 본 계획 사용자 confirm
2. 4 에이전트 검토 (critic / architect — over-engineering / analyst — 영향 범위 / planner — 단계 분해)
3. **P78-1 부터 즉시 박제 가능 (가장 작은 변경, 즉각적 사용자 가치).** P78-2/3/4 는 P78-1 commit 후 순차.
