# 디렉토리 구조 (현재, ADR-0015 갱신)

> 본 문서는 LSKunCompanyKit repo 의 디렉토리 구조. CLAUDE.md 의 §7 에서 분리 (P109-C, 2026-05-27).

## 7. 디렉토리 구조 (현재, ADR-0015 갱신)

```
LSKunCompanyKit/
├── .claude-plugin/
│   ├── plugin.json           # version SSOT (ADR-0012) — 0.21.1
│   └── marketplace.json      # version 필드 없음 — plugin.json 으로 fallback
├── hooks/
│   └── hooks.json            # SessionStart + PreToolUse:Task (ADR-0014 — Stop/PostToolUse 제거. ADR-0016 — denylist (supersede). ADR-0017 — Allowlist 정책 전환)
├── commands/                  # 9개 slash command (ADR-0015 — /migrate 제거, /sync-in /sync-out 신규)
│   ├── init.md               # /lskun-kit:init             (ADR-0015 멱등성 4행)
│   ├── doctor.md             # /lskun-kit:doctor           (19개 진단 항목 — 7C/7D 추가)
│   ├── hire.md               # /lskun-kit:hire             (--domain --model)
│   ├── work.md               # /lskun-kit:work             (메인 세션 = CPO, --model, 7-E 가드)
│   ├── sync_in.md            # /lskun-kit:sync-in          (ADR-0015 — 외부 mirror → Local SSOT)
│   ├── sync_out.md           # /lskun-kit:sync-out         (ADR-0015 — Local SSOT → 외부 mirror)
│   ├── migrate-schema.md     # /lskun-kit:migrate-schema   (ADR-0014 — legacy history rename)
│   ├── sync-persona.md       # /lskun-kit:sync-persona     (cpo/hr-lead body sync)
│   └── org.md                # /lskun-kit:org              (조직도 read-only)
├── src/lskun_kit/             # Python core (stdlib only, 0 외부 의존성)
│   ├── adapters/             # StorageAdapter ABC, MarkdownTreeAdapter, Local, frontmatter
│   │                         # (ADR-0015 — vault.py 폐기, archive_worker 시그니처 확장)
│   ├── hooks/                # session_start (CLAUDE.md marker 기반) + pre_tool_use (chain 차단)
│   ├── templates/            # CPO / HR persona markdown (ADR-0014 + ADR-0015 갱신)
│   ├── models.py             # Worker / Company + REQUIRED_WORKER_FIELDS (6) + MODEL_ALIASES
│   ├── errors.py             # LSKunKitError + ConfirmRequired + WorkerArchivedError (ADR-0015)
│   ├── paths.py              # ADR-0015 — ~/.lskun-companies/<name>/ 단일 진입점
│   ├── permissions.py        # ADR-0015 결정 4 — ~/.claude/settings.json 자동 박제
│   ├── sync.py               # ADR-0015 결정 5 — sync_in / sync_out (shutil.copytree)
│   ├── session.py            # 활성 워커 1명 프로세스 간 공유
│   ├── context.py            # build_worker_context (ADR-0014 — JD only)
│   ├── audit.py              # CPO 결재 audit log (ADR-0006)
│   ├── persona_sync.py       # 메타 워커 body sync — plan/execute (cpo, hr-lead)
│   ├── org.py                # 조직도 read-only view
│   ├── schema_migration.py   # frontmatter 보강 + legacy history rename (ADR-0005 + ADR-0014)
│   ├── hire_audit.py         # HR Lead 자동 채용 rate-limit + audit log
│   ├── init.py               # ADR-0015 멱등성 4행 + ConfirmRequired 패턴
│   ├── persona_injection.py  # CLAUDE.md marker 박제·교체·검출 + extract_company_name
│   ├── routing.py            # CPO 라우팅 + ADR-0015 결정 7-E archived 가드
│   └── cli_org.py            # /lskun-kit:org canonical entrypoint
├── tests/                     # stdlib unittest, 227 tests (ADR-0015 후 +12)
├── docs/                      # storage-adapter-spec, migration-spec
├── CLAUDE.md                 # 본 문서
├── LICENSE                   # MIT
└── README.md                 # P92 — Phase 15 갱신
```

**hired/ 같은 회사 운영 데이터는 본 repo 에 절대 작성 금지.**
사용자 SSOT (`~/.lskun-companies/<name>/`) 에만 존재해야 함 (ADR-0015 결정 1-A).

---

