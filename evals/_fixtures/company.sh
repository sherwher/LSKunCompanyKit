#!/usr/bin/env bash
# 공용 fixture — 빈 workspace 에 회사 EvalCo 를 만든다.
#   - $HOME/.lskun-companies/EvalCo/ (eval 실행의 임시 HOME) + workspace CLAUDE.md 의 CPO marker
#   - 도메인 워커 1명 (backend-engineer) — 라우팅·빙의·dispatch 케이스용
# 각 케이스의 fixture.sh 가 source 한다. 케이스 디렉토리가 아니므로 prompt.md 를 두지 않는다.
set -euo pipefail
# 방어 가드 — `claude plugin eval --scaffold` 는 빈 workspace + 임시 HOME 에서 실행한다.
# 그 밖의 환경 (실제 HOME, 작업 중인 디렉토리) 에서 실수로 실행되면 아무것도 만들지 않는다.
if [ -e "$HOME/.lskun-companies" ] || [ -n "$(ls -A . 2>/dev/null)" ]; then
  echo "eval fixture: 임시 HOME · 빈 workspace 가 아니다 (HOME=$HOME, PWD=$PWD) — 중단" >&2
  exit 1
fi
PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHONPATH="$PLUGIN_ROOT/src" python3 - <<'PY'
from datetime import date
from pathlib import Path

from lskun_kit.init import run
from lskun_kit.paths import company_root

run(Path.cwd(), company_name="EvalCo", cpo_name="Dana Eval", hr_name="Hana Eval")
hired = company_root("EvalCo") / "hired"
(hired / "backend-engineer.md").write_text(
    "---\n"
    "name: backend-engineer\n"
    "role: backend-engineer\n"
    "domain: meta\n"
    "display_name: Bora Eval\n"
    f"hired_at: {date.today().isoformat()}\n"
    "storage_backend: local\n"
    "keywords: python 함수 작성, 유틸리티 구현, 코드 리뷰, 버그 수정\n"
    "---\n"
    "# Bora Eval — backend-engineer\n\n"
    "> Python 백엔드 구현과 리뷰를 맡는다.\n\n"
    "## 책임 (Responsibilities)\n- 작은 Python 함수와 유틸리티 구현\n- 구현에 대한 코드 리뷰\n\n"
    "## 핵심 역량 (Qualifications)\n- 표준 라이브러리 중심 구현, 타입 힌트\n"
    "- 함정: 가변 기본 인자 (`def f(x=[])`) 를 쓰지 않는다\n\n"
    "## 작업 지침 (Guidelines)\n- 인프라·배포는 맡지 않는다\n",
    encoding="utf-8",
)
PY
