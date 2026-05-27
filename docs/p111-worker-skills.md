# P111 — 워커 `skills` 필드 (전문 도구 박제)

> 상태: spec **v2 (검증 워커 critic + architect 반영)**. 구현 전.
> 관련 ADR: ADR-0020 (신규), ADR-0014 (완성형 워커 — 확장), ADR-0009 (self-contained — 범위 내), ADR-0011 (JD 채용 — 보강).
> 선례: P69 (`keywords` optional 필드 추가) — 본 작업의 직접 템플릿.

## 0. 검증 반영 이력 (v1 → v2)

critic + architect 두 워커가 합의 발견한 blocker/concern 반영:
- **C1 (blocker)**: 두 dispatch 경로의 prompt 조립이 다름 → 단일 주입점으로 통합 (§5 재작성).
- **M1 (concern)**: skill 이름 검증 부재 → allowlist + traversal 가드 (§5.1 신설).
- **M2 (concern)**: doctor 카운트 4중 불일치 → 실측 24개 확정 후 [31] (§7.2).
- **M3 (concern)**: 워커가 Read 안 하면 silent failure → 보고 가시성 필드 (§5.2).
- **M4 (concern)**: dangling 한 방향만 → 양방향(dangling+orphan) (§7.2).
- **M5 (concern)**: JD body inline 대안 미반박 → 비교표 + 정당화 (§3.1).
- **m1**: 필요 시 생성도 사용자 알림 1줄 (§6).
- **gaps**: skill frontmatter 스키마 / 빈 토큰 / 메타 가드 / 공유 정책 (§4.1, §6).

---

## 1. 문제

워커는 JD(persona body)의 산문 텍스트("핵심 역량: Spring Boot, JPA…")로만 전문성이 표현된다.
이 텍스트는 CPO 라우팅용 신호일 뿐, 워커가 dispatch될 때 **"이 스킬이 네 전문 도구다"라는 인지**로 이어지지 않는다.

- 워커는 `subagent_type="claude"`로 dispatch되므로 메인 세션의 모든 plugin skill(figma, vercel 등)에 **접근은 가능**하다.
- 문제는 접근이 아니라 **유도**다. dispatch prompt에 "너는 이 스킬을 써라"는 신호가 없어, 스킬 사용 여부가 dispatch된 Claude의 일반 판단에 맡겨진다 → 도메인 전문가로서의 결정론 상실.

## 2. 목표

워커의 전문성을 JD 텍스트뿐 아니라 **전문 도구(skills)**로도 뒷받침한다.
채용 시점에 전문성(JD) + 전문 도구(skills)가 함께 박제되어 **완성형**(ADR-0014).

## 3. 핵심 설계 결정 (brainstorming 합의)

| # | 결정 | 근거 |
|---|---|---|
| D1 | `skills` = **콤마 구분 string** optional frontmatter 필드 | `keywords`(P69) 선례. frontmatter.py가 list 미지원 → 코드 변경 0 |
| D2 | 저장 위치 = `~/.lskun-companies/<name>/skills/<skill-name>.md` (사용자 SSOT, hired/ sibling) | sync로 함께 이동. 회사 종속 전문 도구 |
| D3 | dispatch 시 워커 인지 = **경로만 주입 + 워커가 Read** | ADR-0009(외부 호출 0) + 컨텍스트 효율. prompt 안 부풀음 |
| D4 | 없는 스킬 생성 = **HR Lead가 로컬 파일 Write** | skill-creator는 LLM이 도구로 호출(있으면 보조, 없어도 동작). core 의존 0 |
| D5 | 생성 시점 = **채용 시 + 필요 시(둘 다)** | 채용 시 = HR Lead 자율. 필요 시 = CPO 판단 → HR Lead 위임 |
| D6 | "marketplace 다운로드" = **채택 안 함** | 네트워크 접촉 → ADR-0009 정체성 붕괴. 생성으로 목적 충족 |

### 3.1 왜 별도 파일인가 — JD body inline 대안과의 비교 (M5)

JD body 는 CPO 라우팅 경로에서 워커에게 통째 주입되므로(`cpo.md`: `context = worker.body + user_request`), "## 전문 도구" 문단을 JD body 에 산문으로 적는 0-코드 대안이 존재한다. 그럼에도 별도 `skills/` 파일을 택하는 정당화:

| 옵션 | Pros | Cons | 채택 |
|---|---|---|---|
| A. JD body inline 텍스트 | 0 코드, 워커가 반드시 봄(body 주입됨), silent failure 없음 | 재사용 불가(워커마다 복붙), 긴 체크리스트가 라우팅 컨텍스트 오염, 여러 워커 공유 불가 | 짧은 지침은 이걸로 충분 |
| B. 별도 skills/ 파일 + 경로 주입 (본 spec) | **여러 워커가 동일 스킬 공유**, 긴 본문이 dispatch prompt 안 부풀림, sync 단위 명확 | Read 준수 비결정적(M3 완화 필요), 검증 표면 추가(M1) | **2000자+ 체크리스트 / 공유 스킬에 한해** |

**결론**: 별도 파일은 (1) 스킬 본문이 길거나(라우팅 컨텍스트 오염 회피) (2) 여러 워커가 공유할 때만 정당화된다. 짧은 단일 워커 지침은 JD body inline 이 낫다. HR Lead 는 이 기준으로 선택한다 — spec 은 "모든 전문성을 skills 로" 강제하지 않는다.

## 4. 데이터 모델 (섹션 1)

`models.py`:
```python
OPTIONAL_WORKER_FIELDS = (
    "model",
    "persona_synced_from",
    "persona_synced_at",
    "keywords",
    "skills",   # 신규 — 콤마 구분 string. 예: "hipaa-phi-masking, hl7-fhir-validator"
)
```

- `keywords`와 다른 점: `keywords`는 raw display(core 매칭 안 씀), `skills`는 dispatch 시 **경로로 변환 + 행동 지시와 함께 주입**.
- 메타 워커(CPO/HR Lead)는 비워둠.
- 값 = 스킬 이름(콤마 구분). 경로는 core가 조합: `<root>/skills/<name>.md` (상대, `adapter.root` 기반).

### 4.1 skill 파일 자체의 스키마 (gap 반영)

`<root>/skills/<name>.md` 의 frontmatter:
```markdown
---
name: hipaa-phi-masking      # 파일명과 일치 필수 (doctor 검증)
description: <1줄 요약>        # 필수
---
<본문 — 체크리스트 / 도메인 지식>
```
- `name` 누락 또는 파일명 불일치 / `description` 누락 → doctor [31] 가 `⚠️ invalid skill schema` 표시.
- 워커 frontmatter 만큼 엄격하진 않음(2필드만). core 는 이 스키마를 **강제하지 않고** doctor 가 사실 표시만.

## 5. dispatch 주입 (섹션 2-A) — C1 반영: 단일 주입점

**검증으로 밝혀진 사실 (C1)**: 두 dispatch 경로의 prompt 조립이 다르다.
- 직통 경로(`work.md`): `prompt = f"{ctx}\n\n{user_request}"`, `ctx = build_worker_context()` = **메타 2줄만** (JD body 없음).
- CPO 라우팅 경로(`cpo.md`): `context = worker.body + user_request` — `build_worker_context` **미호출**.

→ skills 블록을 `build_worker_context` 에만 넣으면 **CPO 라우팅(주 경로)에서 무효**. 단일 주입점으로 통합한다.

**설계**: core 에 공통 헬퍼 `build_skills_block(adapter, name) -> str` 신설. 두 경로가 모두 호출:
- 직통: `build_worker_context` 가 내부에서 `build_skills_block` 을 append.
- CPO: `cpo.md` 의사코드를 `context = worker.body + build_skills_block(...) + user_request` 로 수정.

core 가 하는 일: string split → strip → 빈 토큰 제거 → **이름 검증(§5.1)** → 경로 조합 → 존재 확인. **스킬 내용은 안 읽음**(워커가 Read). `skills` 비면(메타 워커 등) **빈 문자열 반환**(블록 생략).

```
## 전문 도구 (Specialized Skills)
당신의 채용 시 박제된 전문 도구입니다. **작업 시작 전 반드시 Read 로 읽고 따르세요.**
또한 작업 보고 시 "읽은 전문 도구: <이름들>" 1줄을 포함하세요.
- hipaa-phi-masking → <root>/skills/hipaa-phi-masking.md
- hl7-fhir-validator → <root>/skills/hl7-fhir-validator.md  ⚠️ 파일 없음
```

### 5.1 skill 이름 검증 (M1 — traversal 차단)

worker name 과 동일 수준의 allowlist 를 각 토큰에 적용:
- 패턴: `^[a-z0-9][a-z0-9_-]{0,63}$` (`_markdown_tree.py` 의 worker name 패턴 재사용).
- 경로 조합 후 resolve 결과가 `skills/` 밖으로 새면 거부(`_worker_path` 의 escape 가드 재사용 → `_skill_path`).
- 위반 토큰은 블록에 `⚠️ invalid skill name` 표시, 경로 조합 안 함.
- HR Lead 가 생성 시 Write 경로(`<root>/skills/<name>.md`)도 동일 검증 → traversal write 차단.

### 5.2 silent failure 완화 (M3)

"경로 주입 + 워커 Read"는 워커 자율 준수에 의존 → Read 안 하면 조용히 미적용. 완화:
- dispatch 블록에 "보고 시 '읽은 전문 도구: <이름들>' 1줄 포함" 지시 (위 예시).
- CPO 결재 시 skills 선언됐는데 보고에 없으면 재dispatch 1회 유도("재작업 최대 2회" 라인 재사용).
- 이는 **사실 표시**이지 평가/점수가 아님 → ADR-0006 위반 아님.
- **한계 명시**: 100% 보장은 불가(LLM 자율 의존). §9 비목표 참조.

### 5.3 adapter 변경

- `skills_dir` property 신설: `self._root / "skills"` (hired_dir 과 동일 패턴, paths.py 불변 — ADR-0015 정합).

## 6. 스킬 생성 (섹션 2-B) — 두 시점, 한 권한 라인

**채용 시** (HR Lead가 hire 수행 중): JD 작성하며 "이 도메인엔 X 체크리스트 필요" 판단 → `skills/`에 박제 + frontmatter `skills`에 이름 등록.

**필요 시** (CPO 판단 → HR Lead 위임):
```
사용자 요청 → CPO → "이 작업엔 워커에게 X 스킬 없다" 판단
  → HR Lead Task dispatch ("backend-eng 에게 X 스킬 생성")
  → HR가 skill 생성 + 해당 워커 frontmatter.skills 갱신
  → [스킬 박제 알림] 1줄 (사용자 알림, 차단 X) → CPO가 워커 재dispatch
```

- 생성 메커니즘: HR Lead가 skill markdown(frontmatter name/description + 본문, §4.1)을 `<root>/skills/<name>.md`에 직접 Write. 이름은 §5.1 검증 통과 필수.
- skill-creator 스킬: 있으면 품질 보조, 없어도 동작(graceful). 엉터리 skill 이 박히면 사용자가 나중에 수정(keywords 의 "부적절하면 사용자가 수정" 톤 재사용).
- **사용자 알림 (m1)**: "필요 시 생성"도 자동 채용과 동일하게 **알림 1줄, 차단 없음**. CPO 자율 판단이지만 사용자가 사후 인지 → ADR-0014 "자동 진화" 논란 회피(자산 추가는 자동 채용 선례와 동급).
- **중복 방지**: 같은 이름이 이미 `skills/`에 있으면 재생성 대신 frontmatter에 이름만 연결(재사용). hire의 워커 중복 거부와 같은 정신.
- **공유 skill 갱신 정책 (gap)**: 여러 워커가 공유하는 skill 을 갱신하면 모든 공유 워커에 영향. 이는 "도구 공유"이지 "워커 진화"가 아님(워커 JD 는 불변). 단 사용자 명시 갱신만 허용 — CPO 자율로 기존 공유 skill 본문을 바꾸지 않음(신규 생성만 자율).

## 7. ADR / doctor / 테스트 (섹션 3)

### 7.1 ADR-0020 (신규 박제)

> **워커 전문 도구(skills) 박제 — JD 의 도구 차원 확장**
> - ADR-0014(완성형 워커)의 "전문성 박제"를 텍스트 → 도구로 확장. 시간 진화 없음(채용 시 + 명시적 필요 시 갱신만).
> - ADR-0009 **범위 내**: plugin core는 skill-creator를 import/호출하지 않음(LLM이 도구로 호출). 파일 Write만, 외부 호출 0. marketplace 다운로드 미채택.
> - ADR-0011(JD 채용) 보강: HR Lead 채용 권한에 "스킬 박제" 추가. CPO→HR Lead 위임 라인 재사용(워커→워커 chain 위반 아님).
> - 저장: 사용자 SSOT `<root>/skills/`. sync 자동 포함(copytree).
> - **core 는 skills 를 해석/매칭/평가하지 않는다** — string split + 이름 검증 + 경로 조합 + 존재 확인만(keywords 의 "core 는 매칭에 안 씀" 주석과 동급 명문화 → 향후 회귀 차단).
> - **keywords vs skills 의미 구분**: `keywords` = 라우팅용 자기신고 텍스트(CPO 가 읽고 매칭). `skills` = 실행 시 워커가 Read 할 전문 도구 파일 경로.

### 7.2 doctor 진단 추가 — `[31] skills/ 정합성` (M2 + M4)

**M2 — 카운트 정합 (구현 시 실측 정정)**: critic 이 "24개"라 한 것은 예시 출력 블록만 센 오류. **실제 섹션 헤더 기준 실측 = `[1]~[17]`(17) + `[20]~[30]`(11) = 28개** ([18][19] 는 ADR-0019 로 제거). header "28개"가 정확했음. 본 PR:
- 신규 항목 `[31]` 추가 → **28개 → 29개**. header / CLAUDE.md `29개` 로 갱신.

**M4 — 양방향 검출**:얇은 Python helper(`skills_diagnostics` 또는 기존 모듈에 함수) 가 `(worker, skill, exists)` 리스트 반환, doctor.md 가 호출([25]/[27] helper 패턴):
- **dangling** (선언↔파일없음): `⚠️ <worker>.skills=<name> → 파일 없음`.
- **orphan** (파일↔선언없음): `ℹ️ skills/<name>.md → 선언 워커 0 (죽은 자산)`. archived/ 가 쓰레기통화해 ADR-0019 로 폐기된 전철 방지.
- **invalid name/schema**: §5.1 / §4.1 위반 표시.
- **메타 워커 가드 (gap)**: cpo/hr-lead 에 skills 박히면 `⚠️ 메타 워커는 skills 비워둠 권장`.
- 정보성. ADR-0006 정신(평가·점수 0, 사실 표시만).

### 7.3 테스트 (keywords 테스트 패턴 재사용)

- `test_models` (또는 frontmatter 파싱): `skills` optional 파싱, 없으면 None.
- `test_context`: skills 블록 주입 / 누락 ⚠️ 표시 / 빈 값 시 블록 생략 / 경로 조합 정확성.
- `test_doctor` (진단 helper): dangling + orphan + invalid name/schema + 메타 가드 검출.
- `test_schema_migration`: `skills` 없는 기존 워커가 여전히 v0.4 정상 판정(안 깨짐).
- **C1 회귀 테스트**: `build_skills_block` 이 양 경로(직통 build_worker_context + CPO worker.body 조립)에 모두 들어가는지 — 두 경로 각각 skills 블록 포함 검증.
- **M1 보안 테스트**: skill 이름에 `../`, 공백, 절대경로, 빈 토큰(`a,,b`) 거부.

## 8. 마이그레이션 — 기존 워커 안 깨짐

- `read_worker`가 optional을 `.get()`으로 읽음 → `skills` 없으면 None.
- `detect_worker_schema`는 `REQUIRED_WORKER_FIELDS`(6개)만 봄 → `skills` 없어도 정상.
- P69(keywords) 때도 기존 회사 0 변경. 강제 일괄 보강 불필요 — "필요할 때" 채움(= D5 필요 시 생성과 연결).

## 9. 범위 밖 (명시적 비목표)

- marketplace/원격 다운로드(D6).
- skills의 YAML list 형식(D1 — string 유지).
- frontmatter 파서 변경.
- 워커→워커 직접 스킬 생성(CPO→HR Lead 라인만).
- **skill Read 의 100% 보장(M3)**: "경로 주입 + 워커 Read"는 LLM 자율 준수에 의존하므로 결정론적 강제는 불가. P111 의 목표는 "결정론"이 아니라 **"인지 유도 + 누락 가시성"**(보고 필드 + CPO 재dispatch 로 확률 상향). 이 한계는 JD body 주입조차 같은 가정에 의존하는 ADR-0009 self-contained 아키텍처의 구조적 귀결이다.
- 생성 skill 의 자동 품질 평가(ADR-0006 — 평가/점수 금지). 사용자 사후 수정에 위임.
