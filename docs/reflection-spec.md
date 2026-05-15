# Reflection Specification (v0.1.0-dev)

> ADR-0001 §3 의 핵심 메커니즘 "Reflection — 작업 종료 시 자동 기록" 을 구현 가능한 형태로 풀어 쓴 사양. P6 에서 박제.

## 1. 사용자 흐름 (3 명령)

```text
1) /lskun-kit:hire alice backend-engineer
     → hired/alice.md 박제

2) /lskun-kit:work alice
     → 자기 history 컨텍스트 주입 + 세션 상태에 활성 워커 등록
     ... 사용자가 평소대로 일을 시킴 ...

3) /lskun-kit:reflect music-pay refund-flow saga 88
     → 1줄 append + 세션 정리
```

3) 대신 Stop hook 이 환경변수에서 reflection 필드를 읽어 자동 처리할 수도 있다 (§5).

## 2. 세션 상태

```
<root>/.lskun-session.json
{
  "active_worker": "alice",
  "started_at": "2026-05-15T10:23:00+00:00"
}
```

- `<root>` 는 사용자 SSOT root (LocalAdapter 의 `.company/` 또는 VaultAdapter 의 `<vault>/03_Companies/<co>/`)
- 한 번에 하나의 활성 워커만 허용 (의도적 단순화 — concurrency 는 P8 이후 검토)
- git 추적 대상 아님 (휘발성)

## 3. 워커 frontmatter schema

P4 에서 박제된 4 필수 필드를 그대로 사용한다:

```yaml
---
name: alice
role: backend-engineer
hired_at: 2026-05-15
storage_backend: local        # local | vault
---
```

`/lskun-kit:hire` 가 위 필드를 자동으로 채운다. 누락 시 LocalAdapter / VaultAdapter 가 `InvalidWorkerSchemaError` 를 raise.

## 4. 컨텍스트 주입 포맷

`lskun_kit.context.build_worker_context(adapter, name, recent=10)` 가 반환:

```markdown
# Worker: alice (backend-engineer)
Hired: 2026-05-15 · Backend: vault

## Past Patterns (recent 3)
- 2026-05-10 / payment-svc / idempotency / stripe-key-as-idem / first-pass 92%
- 2026-05-12 / music-pay / webhook / signature-verify / first-pass 85%
- 2026-05-14 / music-pay / refund-flow / saga / first-pass 88%
```

- history 가 비어 있으면 "_(no history yet — this is the worker's first task)_"
- `recent` 기본값 10 — 토큰 영향 < 20% 목표 (ADR-0001 §검증 KPI) 와 균형

## 5. 자동 vs 명시 Reflection

### 5.1 명시 (`/lskun-kit:reflect`)

사용자가 작업 종료 후 직접 호출. 입력 검증:

- `project`, `topic`, `pattern` 은 비어 있을 수 없고 `/` 포함 금지
- `first_pass_score` 는 0..100 정수

### 5.2 자동 (Stop hook)

Claude Code Stop hook 이 `python3 -m lskun_kit.hooks.stop_reflect` 를 호출. 환경변수에서 reflection 필드를 읽음:

| 변수 | 의미 |
|---|---|
| `LSKUN_SSOT_ROOT` | 사용자 SSOT root (필수) |
| `LSKUN_PROJECT` | 프로젝트명 |
| `LSKUN_TOPIC` | 이번 작업 주제 |
| `LSKUN_PATTERN` | 적용한 핵심 패턴 |
| `LSKUN_FIRST_PASS` | 1차 통과율 (0..100) |

환경변수 4개 중 하나라도 비어 있으면 hook 은 **silent no-op** — 명시 워크플로만 쓰는 사용자를 방해하지 않기 위함.

#### Hook 등록 예시 (`~/.claude/settings.json`)

```json
{
  "hooks": {
    "Stop": [
      {
        "command": "python3 -m lskun_kit.hooks.stop_reflect"
      }
    ]
  }
}
```

`LSKUN_PROJECT` 등은 사용자가 워크플로 시작 시 export 하거나, 별도 hook 으로 자동 채울 수 있다 (v0.2+ 확장 영역).

## 6. Reflection 인용율 측정 (KPI)

`lskun_kit.metrics.estimate_citation_rate(adapter, worker, responses, recent=10)` 가
:class:`CitationReport` 를 반환:

| 필드 | 의미 |
|---|---|
| `worker` | 측정 대상 워커 이름 |
| `sampled_responses` | 검사한 응답 수 |
| `cited_responses` | 키워드가 한 번이라도 등장한 응답 수 |
| `keywords` | history 의 최근 N줄에서 추출된 토큰 |
| `rate` (property) | cited / sampled |

알고리즘 (v0.1):

1. `history` 의 최근 N줄에서 `topic`, `pattern` 셀의 토큰 추출 (영문 ≥3자, stopword 제외)
2. 각 응답에서 키워드 등장 여부를 binary 로 측정
3. 등장 비율을 인용율로 추정

v1.0+ 에서는 LLM-as-judge 로 의미 인용 여부를 판정하는 방식으로 교체 예정. v0.1 에서는 60%+ KPI 의 달성 여부를 가늠하는 것이 목표.

## 7. 한계 (v0.1 의도적 미지원)

- 동시 활성 워커 여러 명 (의도적 단순화)
- Reflection 의 LLM 자동 생성 (v0.3+)
- history semantic 검색 (현재는 recent N 만, v0.4+)
- 쓰기 atomicity / lock (P8 도그푸딩에서 충돌 빈도 측정)
