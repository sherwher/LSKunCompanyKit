# StorageAdapter 인터페이스 명세

> ADR-0001 §4 의 storage 추상화. core 는 본 인터페이스만 알고 구현은 모른다.
> ADR-0014 (2026-05-22) — Reflection 폐기. `append_history` 메서드 제거.

## 1. 4-Method Interface (read-path)

| Method | 동작 | 예외 |
|---|---|---|
| `read_worker(name) -> Worker` | `hired/<name>.md` 의 frontmatter + body 파싱 | `WorkerNotFoundError`, `InvalidWorkerSchemaError` |
| `list_workers() -> list[str]` | `hired/` 의 워커 이름 (sorted) | — |
| `read_company() -> Company` | `company.md` 의 메타데이터 | — |

ADR-0014 — `append_history` ABC 제거. 워커 history 누적 메커니즘 자체 폐기.

## 2. Write-path (default NotImplementedError)

| Method | 동작 |
|---|---|
| `create_worker(name, frontmatter, body)` | `hired/<name>.md` 신규 박제. 존재 시 `FileExistsError` |
| `archive_worker(name)` | `hired/<name>.md` → `archived/<name>.md` 이동. 삭제 X |
| `append_audit(json_line)` | `.audit/decisions.jsonl` 1줄 append (ADR-0006 CPO 결재 audit) |

## 3. 구현체

- `LocalAdapter` — `<project>/.company/` 디렉토리
- `VaultAdapter` — `<vault>/03_Companies/<name>/` 디렉토리

둘 다 `MarkdownTreeAdapter` (공통 기반) 를 상속한다.

## 4. 외부 통합 정책 (ADR-0009)

Plugin core 는 외부 시스템 (Notion / Slack / API) 의 SDK / API 호출을 두지 않는다. 본 ABC 가 정의하는 인터페이스는 file 기반 (Local / Vault) 외 다른 구현체를 core 에 박는 것을 허용하지 않으며, 외부 통합은 별도 add-on package 의 책임이다.
