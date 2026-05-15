# Storage Adapter Specification (v0.1.0-dev)

> ADR-0001 §4 의 추상화 계층을 구현 가능한 형태로 풀어 쓴 사양. P4 단계에서 박제.

## 1. Why an interface

LSKunCompanyKit core 는 사용자 회사 운영 데이터가 어디에 저장되는지 모른다.
core 는 오직 [`StorageAdapter`](../src/lskun_kit/adapters/base.py) 의 4-method interface 만 호출한다.

backend 추가/교체 시 core 코드는 변경되지 않으며, 새 adapter 클래스 하나만 추가하면 된다.

## 2. The four methods

| method | 목적 | 실패 시 예외 |
|---|---|---|
| `read_worker(name) -> Worker` | hired/<name>.md 를 파싱해 :class:`Worker` 반환 | `WorkerNotFoundError`, `InvalidWorkerSchemaError` |
| `append_history(name, entry) -> None` | `## Project History` 섹션에 1줄 append (섹션 없으면 생성) | `WorkerNotFoundError` |
| `list_workers() -> list[str]` | hired/ 의 워커 이름 정렬 목록 | (없으면 빈 리스트) |
| `read_company() -> Company` | company.md 메타데이터 반환 | (없으면 빈 Company) |

각 method 는 부수효과를 최소화한다. `append_history` 만 쓰기 동작이며 atomic 보장은 backend 의무가 아니다 — 멀티 PC 동기화는 P8 에서 검증.

## 3. Worker frontmatter schema (필수 필드)

```yaml
---
name: alice
role: backend-engineer
hired_at: 2026-05-15
storage_backend: local        # local | vault | (future)
---
```

위 4개 필드가 하나라도 빠지면 `InvalidWorkerSchemaError`. 추가 필드는 `Worker.extra` dict 에 평탄하게 저장된다.

`hired_at` 은 ISO-8601 (`YYYY-MM-DD`).

## 4. HistoryEntry 포맷

`Reflection` 의 1줄은 다음 포맷으로 고정한다 (ADR-0001 §3 예시):

```
- {date} / {project} / {topic} / {pattern} / first-pass {score}%
```

| 필드 | 타입 | 비고 |
|---|---|---|
| date | `datetime.date` (ISO) | 작업 종료 시각의 날짜 |
| project | str | 슬래시 `/` 금지 |
| topic | str | 슬래시 `/` 금지 |
| pattern | str | 워커가 적용한 핵심 패턴 |
| first_pass_score | int (0..100) | 1차 통과율 |

순서/구분자는 grep 친화성을 위해 고정. 향후 변경 시 schema migration tool (P7) 책임.

## 5. SSOT guard

`LocalAdapter(root)` 는 root 경로에 `02_Projects/LSKunCompanyKit` 가 포함되면 `SSOTContaminationError` 를 raise 한다. ADR-0001 §5 의 개발자/사용자 SSOT 분리 정책을 코드 차원에서 강제하기 위한 보호 장치.

Vault backend (P5) 도 동일 가드를 상속한다. doctor (P3) 는 런타임 검증을 보강한다.

## 6. Non-goals (v0.1)

- 쓰기 atomicity / lock (P8 에서 검토)
- frontmatter 의 nested / list / multiline (의도적으로 미지원, 평탄 key-value 만)
- 외부 의존성 (PyYAML 등) — stdlib only

## 7. Test surface

`tests/test_local_adapter.py` 에 unittest 기반 18+ 케이스. 실행:

```bash
python3 -m unittest discover -s tests -v
```
