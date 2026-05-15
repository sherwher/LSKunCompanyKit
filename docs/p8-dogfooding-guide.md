# P8 Dogfooding Guide (v0.1.0-dev)

> Phase 1 의 마지막 검증 단계. 본인 환경에서 1주간 실제로 사용하면서
> ADR-0001 §검증 KPI 5개를 측정한다. KPI 미달 시 컨셉 폐기 가능.

## 0. 진입 조건

- [x] P3~P7 모두 merge (main: `fe98d33`)
- [x] 52/52 테스트 통과
- [ ] 본인 (이성근) 의 Mac 1대 + 보조 PC 1대 (멀티 PC 동기화 KPI 검증용)
- [ ] Obsidian (또는 다른 vault 가능 도구) 가 양쪽 PC 에 설치되어 있고 sync 활성화

## 1. 설치 — 본인 환경

### 1.1 Plugin 등록

```bash
cd /Users/sk.lee/Documents/private-workspaces/LSKunCompanyKit
# Claude Code 안에서:
/plugin install ./
```

설치 후 검증:

```text
/lskun-kit:doctor
```

기대 출력 (P3 단계 사양):
```
[1] Claude Code 버전              : ✅ <version>
[2] Plugin manifest               : ✅ name=LSKunCompanyKit, namespace=/lskun-kit:*
[3] Storage backend
      Local  (<path>)             : ⚠️  .company/ 없음 (초기 상태)
      Vault  (<path>)             : ⏳ LSKUN_VAULT 환경변수 미설정
[4] SSOT cross-contamination       : ✅ 분리 정상
[5] Worker frontmatter             : ⏳ Phase 미구현 (P3 prototype)
[6] Reflection hook                : ⏳ 환경변수 미설정
[7] Migration tool                 : ✅ /lskun-kit:migrate 등록됨
```

### 1.2 Vault backend 활성화

```bash
# ~/.zshrc 에 추가
export LSKUN_VAULT="$HOME/Documents/private-workspaces/obsidian-vault"
export LSKUN_SSOT_ROOT="$LSKUN_VAULT/03_Companies/LSKun"
```

Vault 안에 회사 디렉토리가 없으면 만든다:

```bash
mkdir -p "$LSKUN_SSOT_ROOT/hired"
```

`company.md` 박제:

```bash
cat > "$LSKUN_SSOT_ROOT/company.md" <<'EOF'
---
name: LSKun
founded: 2026-05-15
---

# LSKun

이성근의 1인 회사. AI 직원이 자라며 함께 일한다.
EOF
```

### 1.3 Stop hook 등록

`~/.claude/settings.json` 에 추가 (이미 다른 hook 이 있으면 Stop 배열에 append):

```json
{
  "hooks": {
    "Stop": [
      { "command": "python3 -m lskun_kit.hooks.stop_reflect" }
    ]
  }
}
```

`PYTHONPATH` 가 plugin src/ 를 보도록:

```bash
# ~/.zshrc
export PYTHONPATH="$HOME/Documents/private-workspaces/LSKunCompanyKit/src:$PYTHONPATH"
```

## 2. 워커 hire (1~3명)

본인이 평소 자주 호출하는 역할을 박제. 권장 시작점:

```
/lskun-kit:hire backend-engineer  backend-engineer
/lskun-kit:hire designer          designer
/lskun-kit:hire pm                pm
```

(이름과 role 이 같아도 무방 — 도그푸딩 1주에 페르소나 다양화는 우선순위 낮음.)

## 3. 1주간 일상 워크플로

각 작업 단위마다:

```
1. /lskun-kit:work backend-engineer   ← 워커 호출, history 컨텍스트 주입
2. 실제 작업 (코딩 / 문서 / 디버깅 등)
3. 작업 종료 시 둘 중 하나:
     a) /lskun-kit:reflect <project> <topic> <pattern> <score>
     b) 환경변수 export 후 Claude Code 종료 (Stop hook 이 자동 처리)
```

### 환경변수 자동화 예시

작업 시작 시 한 줄로 reflection 필드를 export 해두면 Stop hook 이 자동 reflect:

```bash
export LSKUN_PROJECT="LSKunCompanyKit"
export LSKUN_TOPIC="dogfooding"
export LSKUN_PATTERN="vault-backend-roundtrip"
export LSKUN_FIRST_PASS=80
```

작업 종료하면 1줄이 자동 박제된다.

## 4. KPI 측정 (ADR-0001 §검증 KPI)

| KPI | 목표 | 측정 방법 |
|---|---|---|
| Reflection 인용율 | 60%+ | `lskun_kit.metrics.estimate_citation_rate(...)` 를 일주일 마지막 날 실행. 워커의 응답 N개를 모아 keyword overlap 측정. v1.0 LLM-as-judge 미도입 상태이므로 60% 는 lower bound 추정. |
| 사용자 효용 (정성) | "내 직원이 기억한다" 느낌 | 1주 종료 후 자유서술 (50자 이상). 무미건조해도 정직하게. |
| 토큰 영향 | < 20% 증가 | `/lskun-kit:work` 없이 동일 작업한 control 1회 vs work 사용 5회 평균 비교. claude-code 의 token 통계로 대조. |
| 멀티 PC 동기화 충돌 | 월 1회 미만 (1주 0회 목표) | git diff / Obsidian sync 충돌 markers (`<<<<<<<`) 발생 횟수 카운트. |
| Migration 무결성 | 데이터 손실 0 | 1주 중반에 Local 백업본 → Vault 마이그레이션 1회 실행. `/lskun-kit:migrate ... --dry-run=true` 후 실행. SHA-256 검증은 코드 보장이지만, 사용자가 결과 파일을 눈으로 검수. |

## 5. 일별 체크포인트

매일 1분만:

```
[Day N]
- /lskun-kit:work 호출 횟수: __
- /lskun-kit:reflect 또는 Stop hook 성공 횟수: __
- 어이없는 history 라인 (의미 없거나 잘못된): __
- 워커가 history 를 직접 인용한 응답 (체감): __
- 충돌 / 에러 발생: __
```

작은 노트로 남겨두면 P9 측정 단계에서 회상 비용이 0 으로 떨어진다.

## 6. 7일차 종료 후 처리

1. **citation rate 측정 스크립트** 실행:
   ```bash
   python3 -c "
   from lskun_kit import VaultAdapter
   from lskun_kit.metrics import estimate_citation_rate
   import os
   adapter = VaultAdapter(os.environ['LSKUN_VAULT'], 'LSKun')
   # responses = [<일주일치 워커 응답 모음>]
   responses = []  # TODO: claude-code transcript 에서 수집
   for w in adapter.list_workers():
       r = estimate_citation_rate(adapter, w, responses)
       print(f'{w}: cited={r.cited_responses}/{r.sampled_responses} ({r.rate:.0%})')
   "
   ```

2. **KPI 5개 표 채워 ADR-0002 (Phase 1 검증 결과) 박제**.
   - 위치: `obsidian-vault/02_Projects/LSKunCompanyKit/decisions/ADR-0002-<date>-phase-1-verification.md`
   - 5개 KPI 표 + 정성 평가 + 채택/폐기/조건부 채택 결정

3. **컨셉 채택 시:** v0.2 로드맵 박제 (Notion backend / LLM Reflection 생성 / semantic history search)
4. **컨셉 폐기 시:** ADR-0002 에 폐기 사유와 다음 방향 박제. 본 repo 는 archive.

## 7. 도그푸딩 중 발견할 가능성 높은 이슈

코드를 짜며 예상한 약점들 — 미리 알고 시작하면 디버깅이 빨라진다:

| 가능한 이슈 | 원인 | 대응 |
|---|---|---|
| Stop hook 이 동작 안 함 | `PYTHONPATH` 누락 / settings.json 형식 오류 | `python3 -m lskun_kit.hooks.stop_reflect` 를 수동 실행해 확인 |
| 환경변수 빠진 상태로 작업 종료 | hook 의 silent no-op 가 의도된 동작 — 사용자는 "왜 안 박제됐지?" 느낄 수 있음 | 익숙해질 때까지 `/lskun-kit:reflect` 명시 호출 우선 |
| Obsidian Sync 충돌 | 두 PC 가 거의 동시에 append_history | 충돌 발생 시 양쪽 history 를 union 으로 수동 머지. P9 측정 결과에 카운트. |
| 토큰 영향 측정 어려움 | claude-code 의 통계 granularity 가 작업 단위가 아닐 수 있음 | session 단위 평균으로 근사. 엄밀 측정은 v0.2+ |
| Citation rate 가 낮게 나옴 | keyword overlap 의 false negative (워커가 paraphrase 함) | v1.0 의 LLM-as-judge 로 재측정 예정. 60% 미달이어도 정성 평가가 좋으면 조건부 채택. |

## 8. 부담 줄이기

도그푸딩이 무겁게 느껴지면 **3일만** 으로 줄여도 의미 있다. ADR-0001 의 1주 권장은 권장이지 강제가 아니다. 정직한 측정 > 긴 측정.

## 9. 그 다음

- **채택:** v0.2 계획 (Notion / LLM-judge / semantic history) 박제 → 새 Phase 시작
- **조건부 채택:** 발견된 critical issue 만 fix 하는 P10 → 재측정
- **폐기:** ADR-0002 박제, repo archive, 다른 방향 모색
