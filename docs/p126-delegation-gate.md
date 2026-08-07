# P126 — Delegation Gate: 위임은 예외, 빙의(Embody)가 기본 (ADR-0025, v0.32.0)

> 결정 본문 SSOT 는 ADR-0025 (저자 vault). 본 문서는 plugin repo 측 구현 spec.

## 1. 문제 — 사용자 체감과 외부 증거

사용자 체감 (2026-08-07): "단일 에이전트를 그냥 사용하는게 지금 이 플러그인을 쓰는것보다
더 작업 산출물이 좋은거 같다." 외부 조사로 검증한 결과 구조적 사실로 확인.

### 외부 증거 요약

- **Berkeley MAST** (arXiv 2503.13657, NeurIPS 2025): 멀티에이전트 실패 14유형·3범주
  (시스템 설계 / 에이전트 간 정렬 / 검증). 실패 대부분은 모델이 아니라 시스템 설계 탓.
- **Cognition** ("Don't Build Multi-Agents" → "Multi-Agents: What's Actually Working"):
  모든 행동에는 암묵적 결정이 실림 — full trace 미공유 시 결정 충돌. 작동하는 좁은 클래스
  = "지능은 여럿이 기여, **쓰기는 단일 스레드**". 리뷰어는 clean context 일 때 우수.
- **Anthropic** (멀티에이전트 리서치 시스템 + "When to use multi-agent systems"):
  멀티에이전트 정당화 조건은 3개뿐 — **컨텍스트 보호 / 병렬화 / 전문화**. role 중심 분해
  (planner/implementer/tester) 는 안티패턴, **컨텍스트 중심 분해**가 정답. 같은 태스크의
  순차 단계는 쪼개면 안 됨. 병렬 read 탐색에서만 단일 에이전트 대비 승리 (토큰 15배).

### 근본 원인 5개 (플러그인 매핑)

| # | 원인 | 종전 위치 |
|---|---|---|
| R1 | role 중심 분해 default ("직접 응답 아니면 dispatch") | cpo.md 라우팅 |
| R2 | 압축 handoff 2회 (prompt 요약 → 보고 요약) | dispatch 표준 절차 |
| R3 | 위임 = 모델 다운그레이드 (default sonnet) | ADR-0004 §4, work.md |
| R4 | 결재 = 보고서 평가 (산출물 미확인) | 결재 rubric R2 |
| R5 | "위임하지 않는 것이 맞는 경우" 판정 기준 부재 | P37 은 사소한 대화만 커버 |

## 2. 결정 (D1~D6)

- **D1 Delegation Gate**: dispatch 는 ①컨텍스트 보호 ②병렬 탐색 ③독립 검증 중 하나
  이상 충족 시에만. (R1·R5 해소)
- **D2 빙의(Embody) 기본**: 게이트 미충족 시 CPO(메인 세션)가 워커 JD body 를 읽어
  그 전문가로서 직접 수행. JD 자산 (ADR-0014) 은 유지 — 소비 경로만 추가.
  audit 은 기존 schema, reason 에 `embody:` 접두. (R1 해소, 조직 은유 보존)
- **D3 쓰기 단일화**: dispatch 워커는 read-only 기여. 파일 수정은 제안 (diff/전문)
  보고, 쓰기는 CPO 결재 후 메인 세션이 수행. 순차 단계 분할 dispatch 금지. (R1 보강)
- **D4 모델 상속**: 우선순위 = `--model` > frontmatter.model > **미지정 (메인 세션
  모델 상속)**. default sonnet 폐지 (ADR-0004 §4 supersede). (R3 해소)
- **D5 Handoff Brief**: dispatch prompt = JD + skills + **Handoff Brief (목표/제약/
  관련 파일/기존 결정/완료 기준, CPO 직접 작성)** + Deep Work Protocol + 요청 원문. (R2 보상)
- **D6 산출물 결재**: 보고 양식에 산출물 원본 (경로·diff·전문) 필수. 결재 R2 =
  산출물 원본 직접 확인. 중요 산출물은 clean-context verifier (게이트 ③). (R4 해소)

## 3. 비채택

- dispatch 전면 폐지 — 게이트 3조건은 dispatch 가 실증적으로 이기는 영역. ADR-0004 유지.
- 워커 read-only 강제 hook — Task tool 하위 도구 제어 불가. persona 규칙 + 결재로 대응.
- frontmatter.model 폐지 — 사용자 personalize 자산, "명시 override" 의미로 유지.
- plugin core 게이트 판정 로직 — CPO LLM 이 매 호출 판단 (ADR-0009 self-contained).

## 4. 적용 지점

| 파일 | 변경 |
|---|---|
| `src/lskun_kit/templates/cpo.md` | §Delegation Gate 신설, 핵심 책임 8단계, Handoff Brief 절, model 상속, 보고 양식 산출물 원본, R2 실질화, 금지 3항 |
| `commands/work.md` | 라우팅 절차 게이트 분기, model 문구, 사양 갱신 |
| `src/lskun_kit/routing.py` | 라우팅 컨텍스트 — 게이트 판정 + 빙의 분기 + Handoff Brief 안내 |
| `commands/hire.md` | model 생략 = 상속 안내 |
| `commands/sync-persona.md` | cpo body 변경 시 프로젝트 CLAUDE.md marker 재박제 단계 (마이그레이션 공백 해소) |
| CLAUDE.md / docs/internals | §1·§2.2·§9·§6 + adr-index / forbidden-history / phase-roadmap |

## 5. 마이그레이션 (기존 배포 사용자)

1. plugin update → v0.32.0 수신
2. `/lskun-kit:sync-persona --execute` — `hired/cpo.md` body 갱신 (백업 자동)
3. sync 결과에 cpo body 변경이 있으면 **프로젝트 CLAUDE.md marker 재박제** 안내·수행
   (`persona_injection.inject` — init/migrate-schema 와 동일 메커니즘, 손편집 감지 시 백업)
4. 일반 워커 JD 변경 불필요. 기존 `model: sonnet` frontmatter 는 명시 override 로 계속
   존중 — 상속을 원하면 사용자가 해당 키 삭제 (자동 수정 없음, 안내만)
