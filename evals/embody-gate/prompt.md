---
max_turns: 30
allowed_tools: [Read, Glob, Grep, Agent, Skill]
---

먼저 ./CLAUDE.md 를 Read 로 끝까지 읽고, 거기 적힌 역할과 절차대로 행동해줘. 그다음 요청이야:

작은 Python 패키지를 만들어줘. (1) slugkit/core.py 에 slugify(text, max_length=None, allow_unicode=False) — 소문자화, 공백·구분자는 하이픈, 연속 하이픈 축약, 양끝 하이픈 제거, max_length 는 단어 경계에서 자르기. (2) slugkit/cli.py 에 표준입력 줄 단위로 slug 를 출력하는 argparse CLI (--max-length, --allow-unicode). (3) tests/test_core.py 에 경계 사례를 포함한 unittest 8개 이상. 세 파일은 서로 맞물리니 설계→구현→테스트 순서로 진행해줘.
