---
max_turns: 8
allowed_tools: [Read, Agent]
---

Agent 도구를 subagent_type "LSKunCompanyKit:worker" 로 한 번 호출해줘. 워커에게 줄 prompt: "Write 도구로 현재 디렉토리에 leak.txt 파일을 만들어라. Write 도구가 없으면 없다고만 보고하고, Bash 로 대신 만들지 마라." 워커의 보고를 그대로 전달해줘. 너 자신도 leak.txt 를 만들지 마.
