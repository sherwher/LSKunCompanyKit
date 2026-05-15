"""Claude Code hook 진입점.

각 hook 은 stdin 으로 JSON event 를 받아 부수효과를 수행하고 exit code 로 응답한다.
hook 등록은 사용자 settings.json 책임 (`docs/reflection-spec.md` §Hook 등록 참조).
"""
