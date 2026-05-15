# Storage Adapter Specification (v0.1.0-dev)

> ADR-0001 §4 의 추상화 계층을 구현 가능한 형태로 풀어 쓴 사양. P4 에서 박제, P5 에서 Vault backend 추가.

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

`LocalAdapter` / `VaultAdapter` 모두 root 경로에 `02_Projects/LSKunCompanyKit` 가 포함되면 `SSOTContaminationError` 를 raise 한다. ADR-0001 §5 의 개발자/사용자 SSOT 분리 정책을 코드 차원에서 강제하기 위한 보호 장치. `_markdown_tree.MarkdownTreeAdapter` 기반 클래스가 두 adapter 모두에게 동일 가드를 제공한다.

doctor (P3) 는 런타임 검증을 보강한다.

## 6. Backend 구현 현황

### 6.1 LocalAdapter (P4)

- 경로: `<project-root>/.company/`
- 한 프로젝트 단위. 외부 동기화 의존성 없음.
- 사용: `LocalAdapter("<project-root>/.company")`

### 6.2 VaultAdapter (P5)

- 경로: `<vault>/03_Companies/<company>/`
- 한 vault 가 N개 회사를 가질 수 있어 인스턴스화 시 `company` 인자 필수.
- `<vault>/03_Companies/` 또는 지정한 company 디렉토리가 없으면 `VaultCompanyNotFoundError` (사용 가능한 회사 목록을 메시지에 포함).
- `lskun_kit.list_companies(vault)` — vault 안의 회사 디렉토리 정렬 목록 (점-prefix 제외).
- 멀티 PC 동기화는 OS file sync (Obsidian Sync / iCloud / Dropbox) 가 담당. atomic write 미보장 — P8 도그푸딩에서 충돌 빈도 측정.
- 사용: `VaultAdapter("~/Documents/private-workspaces/obsidian-vault", "LSKun")`

### 6.3 Future backends

Notion (v0.2+), HTTP API 등을 추가하려면 :class:`StorageAdapter` 또는 :class:`MarkdownTreeAdapter` 를 상속하면 된다. 4-method 시그니처는 변경 금지.

## 7. Non-goals (v0.1)

- 쓰기 atomicity / lock (P8 에서 검토)
- frontmatter 의 nested / list / multiline (의도적으로 미지원, 평탄 key-value 만)
- 외부 의존성 (PyYAML 등) — stdlib only

## 8. Test surface

| Backend | 파일 | 케이스 수 |
|---|---|---|
| Local | `tests/test_local_adapter.py` | 14 |
| Vault | `tests/test_vault_adapter.py` | 9 |

실행:

```bash
python3 -m unittest discover -s tests -v
```
