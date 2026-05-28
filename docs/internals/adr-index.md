# ADR Index (전체 결정문)

> 본 문서는 LSKunCompanyKit 의 상위 결정문 (Architecture Decision Records) 인덱스.
> CLAUDE.md 의 머리부에서 분리 (P109-C, 2026-05-27).
> 저자 SSOT 의 물리적 위치는 저자별로 다르다 (ADR-0009 §5). 본 문서는 저자 개인 SSOT 경로를 박제하지 않는다.

| ADR | 결정 | 상태 |
|---|---|---|
| ADR-0001 | Stateful Workers (창설) | 활성 (§3 일부 ADR-0014 supersede) |
| ADR-0002 | CPO/HR pivot (Phase 2 진입) | 활성 (§3 일부 ADR-0004 supersede) |
| ADR-0003 | 도메인 인지 워커 (`role × domain`) | 활성 |
| ADR-0004 | **메인 세션 = CPO (Leader-Worker, 자동 채용)** | 활성 |
| ADR-0005 | Schema 마이그레이션 (`/lskun-kit:migrate-schema`) | 활성 |
| ADR-0006 | CPO 결재 audit log (`.audit/decisions.jsonl`) | 활성 |
| ~~ADR-0007~~ | SSOT 3축 + `.claude/lskun-kit.json` | **superseded by ADR-0008** |
| ADR-0008 | Local-first, vault optional, link 미도입 | 활성 (일부 ADR-0015 supersede) |
| ADR-0009 | **Self-contained default** — plugin core 외부 SDK 미보유 | 활성 |
| ADR-0010 | Persona sync + provenance + 조직도 view | 활성 |
| ADR-0011 | **JD 기반 채용 + 정체성 보강** | 활성 (§6 ADR-0014 supersede) |
| ADR-0012 | Plugin version single-source SSOT (`plugin.json`) | 활성 |
| ~~ADR-0013~~ | 조직도 stable table + reflection 박제 강제 | **부분 supersede by ADR-0014** (table 유지, reflection 폐기) |
| ADR-0014 | **Reflection 메커니즘 완전 폐기 + JD-driven 정체성 박제** | 활성 (4 전문가 5차 만장일치, ~1,528 LoC 제거) |
| ADR-0015 | **Local SSOT 단일화 + sync 분리 + 권한 박제 + 해고 결합 해제** | 활성 (결정 1~6 유지, 결정 7 ADR-0019 supersede) |
| ~~ADR-0016~~ | 메인 세션 측 OMC fallback 차단 (denylist) | **supersede by ADR-0017** (메커니즘 계승, denylist → allowlist) |
| ADR-0017 | **Dispatch subagent_type Allowlist (`claude` 단일)** | 활성 (v0.21.0+) |
| ADR-0019 | **Archive 메커니즘 완전 폐기** (`delete_worker`) | 활성 (v0.23.0+, ADR-0015 결정 7-A/7-B/7-C/7-D/7-E supersede) |
| ADR-0018 | **No external harness, doctor is the harness** | 활성 (v0.25.0+, P106 메타 리뷰 + P109 자기관찰 도구 실증 후 박제 — design doc: `docs/p110-adr-0018.md`) |
| ADR-0020 | **워커 전문 도구 (`skills`) 박제 — JD 의 도구 차원 확장** | 활성 (v0.26.0+, ADR-0014 확장 / ADR-0009 범위 내 — spec: `docs/p111-worker-skills.md`) |
| ADR-0021 | **외주 (레드팀 + 고객) — 회사 비종속 평가 자원** | 활성 (v0.27.0+, ADR-0014 확장 / ADR-0008 2축 유지 — spec: `docs/superpowers/specs/2026-05-28-external-redteam-customers-design.md`) |

## Supersede Chain (시각화)

```
ADR-0007 → ADR-0008
ADR-0013 → ADR-0014 (부분)
ADR-0001 §3 → ADR-0014 (state 재정의)
ADR-0011 §6 → ADR-0014
ADR-0002 §1~§2 → ADR-0004 (HR Lead 호출 정책)
ADR-0016 → ADR-0017 (정책 전환)
ADR-0015 결정 7 → ADR-0019 (archive 폐기)
```

## ADR 박제 위치

- 저자 SSOT (개발자 개인): 저자별 다른 위치 (ADR-0009 §5)
- 본 plugin repo 의 사용자 참조: 본 인덱스 + 본문 ADR 번호 인용만

세부 결정 변경 시 새 ADR 박제 → 본 인덱스 갱신.
