# StorageAdapter 인터페이스 명세

> ADR-0001 §4 의 storage 추상화. core 는 본 인터페이스만 알고 구현은 모른다.
> ADR-0014 (2026-05-22) — Reflection 폐기. `append_history` 메서드 제거.
> ADR-0015 (2026-05-22) — Vault backend 폐기. Local 단일 backend (`~/.lskun-companies/<name>/`). 외부 mirror 통합은 sync 명령의 파일시스템 복사로만.

## 1. Read-path Interface (3 methods)

| Method | 동작 | 예외 |
|---|---|---|
| `read_worker(name) -> Worker` | `hired/<name>.md` 의 frontmatter + body 파싱 | `WorkerNotFoundError`, `InvalidWorkerSchemaError` |
| `list_workers() -> list[str]` | `hired/` 의 워커 이름 (sorted) — archived/ 제외 (ADR-0015 결정 7-B) | — |
| `read_company() -> Company` | `company.md` 의 메타데이터 | — |

ADR-0014 — `append_history` ABC 제거. 워커 history 누적 메커니즘 자체 폐기.

## 2. Write-path (default NotImplementedError)

| Method | 동작 |
|---|---|
| `create_worker(name, frontmatter, body)` | `hired/<name>.md` 신규 박제. 존재 시 `FileExistsError` |
| `archive_worker(name, archived_at=None, archived_reason=None)` | `hired/<name>.md` → `archived/<name>.md` 이동. ADR-0015 결정 7-B — archive 시점에 frontmatter 에 `archived_at` + `archived_reason` 박제. 기존 `display_name` 보존 (자동 익명화 금지). 파일 삭제 금지. |
| `append_audit(json_line)` | `.audit/decisions.jsonl` 1줄 append (ADR-0006 CPO 결재 audit) |

## 3. 구현체 (ADR-0015 — Local 단일)

- `LocalAdapter` — `~/.lskun-companies/<name>/` 디렉토리 (`paths.company_root(name)` 단일 진입점)
  - `LocalAdapter(<absolute_path>)` — 절대경로 명시
  - `LocalAdapter.from_company_name("<name>")` — 회사 이름으로 생성 (ADR-0015 권장)

`MarkdownTreeAdapter` 가 공통 기반. 단 vault 직접 통합은 영원히 금지 (결정 1-B). 외부 mirror 와의 동기화는 `/lskun-kit:sync-in` / `/lskun-kit:sync-out` 명령의 `shutil.copytree` 로만.

## 4. 단일 경로 진입점 (`paths.py`)

ADR-0015 결정 1-A — Plugin core 의 회사 자원 물리적 위치는 `lskun_kit.paths` 만 결정:

- `paths.lskun_companies_root() -> Path` — `~/.lskun-companies/`
- `paths.company_root(name) -> Path` — `~/.lskun-companies/<name>/`
- `paths.backup_root(name) -> Path` — `~/.lskun-companies/.backups/<name>/`
- `paths.validate_company_name(name)` — 검증 (영문/숫자/_/-/. + 시작 영문/숫자, `.backups` 예약어)
- `paths.list_companies() -> list[str]` — `.backups/` 제외

호출자 (init / hooks / cli_org / sync / permissions) 는 본 모듈만 import 한다.

## 5. 외부 통합 정책 (ADR-0009 + ADR-0015)

Plugin core 는 외부 시스템 (Notion / Slack / Obsidian API) 의 SDK / API 호출을 두지 않는다. 본 ABC 가 정의하는 인터페이스는 file 기반 (Local) 외 다른 구현체를 core 에 박는 것을 허용하지 않으며, 외부 통합은 별도 add-on package 의 책임이다.

ADR-0015 — 외부 mirror (vault / Obsidian / Dropbox / 외장 디스크) 와의 동기화는 사용자 명시 sync 명령으로만 수행. `lskun_kit.sync` 모듈이 `shutil.copytree` 만 사용. 자동 스케줄링 / 자동 merge / 외부 SDK 호출 모두 영구 금지.
