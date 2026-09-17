"""``lskun-audit`` — CPO 결재 기록 진입점 (ADR-0027, P130).

배경: 기록 절차가 12필드 inline Python 이라 (a) 빙의 건 기록이 누락되고
(b) CPO 가 검증을 우회해 ``decisions.jsonl`` 을 손으로 append 했다. 본 진입점은
입력을 3개로 줄이되 기존 :class:`lskun_kit.audit.AuditEntry` 검증을 그대로 거친다.

원칙:
    - 호출자는 메인 세션 = CPO (ADR-0006 §2 — hook 자동화 미도입).
    - schema 불변 (ADR-0006 §4). reflection 시절 잔재 필드는 기본값으로 채운다.
    - 하위 명령은 ``record`` 하나. 조회·집계 하위 명령을 만들지 않는다
      (ADR-0006 — audit 위 KPI·대시보드 금지).
    - 사용자 인터페이스가 아니다 (ADR-0001 §7 — 사용자 표면은 slash command 만).

사용::

    lskun-audit record --worker <name> --verdict <approved|rework|rejected|rerouted> \\
        --reason "<결재 사유 1~2문장>" [--embody] [--request-id ID] [--rounds N] \\
        [--model M] [--auto-hired]
"""

from __future__ import annotations

# self-bootstrap (cli_org.py 와 동일 패턴) — PYTHONPATH / $CLAUDE_PLUGIN_ROOT 의존 0.
import sys
from pathlib import Path

_PKG_PARENT = Path(__file__).resolve().parent.parent  # .../src/
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))

import argparse

#: ADR-0027 D5 — 단일 동작. 늘리려면 새 ADR.
SUBCOMMANDS = ("record",)

EMBODY_PREFIX = "embody:"
DEFAULT_MODEL = "inherit"  # ADR-0025 D4 — 미지정 = 메인 세션 모델 상속
LEGACY_FIRST_PASS_SCORE = 0  # ADR-0014 로 폐기된 점수 체계의 잔재 필드 (schema 호환용)


def _build_parser() -> argparse.ArgumentParser:
    from lskun_kit import audit

    parser = argparse.ArgumentParser(
        prog="lskun-audit",
        description="CPO 결재 기록 진입점 (ADR-0027). 호출자는 메인 세션 = CPO.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record", help="결재 1건을 .audit/decisions.jsonl 에 append")
    rec.add_argument("--worker", required=True, help="결재 대상 워커 이름 (hired/<name>.md)")
    rec.add_argument(
        "--verdict", required=True,
        choices=sorted(audit._VALID_VERDICTS),  # noqa: SLF001 — enum 단일 진실원 재사용
    )
    rec.add_argument("--reason", required=True, help="결재 사유 1~2문장")
    rec.add_argument(
        "--embody", action="store_true",
        help="빙의 (CPO 직접 수행) 건 — reason 에 'embody:' 접두 보장 (ADR-0025 D2)",
    )
    rec.add_argument("--request-id", default=None, help="rework 라운드는 같은 id 재사용")
    rec.add_argument("--rounds", type=int, default=1)
    rec.add_argument("--model", default=DEFAULT_MODEL, help="해소 후 실제 dispatch 모델")
    rec.add_argument("--auto-hired", action="store_true")
    return parser


def _normalize_reason(reason: str, embody: bool) -> str:
    text = reason.strip()
    if embody and text and not text.lower().startswith(EMBODY_PREFIX):
        text = f"{EMBODY_PREFIX} {text}"
    return text


def _record(args: argparse.Namespace) -> int:
    from lskun_kit import audit
    from lskun_kit.adapters.local import LocalAdapter
    from lskun_kit.errors import LSKunKitError
    from lskun_kit.hooks._common import detect_company_root

    root = detect_company_root()
    if root is None:
        print(
            "lskun-audit: 활성 회사를 찾지 못했다 (cwd 상위 CLAUDE.md 의 LSKUN-CPO marker "
            "또는 LSKUN_SSOT_ROOT). 기록하지 않았다.",
            file=sys.stderr,
        )
        return 2

    adapter = LocalAdapter(root)
    try:
        # ADR-0023 — 파일 없는 워커에 대한 audit (유령참조) 금지.
        worker = adapter.read_worker(args.worker)
        company = adapter.read_company()
        entry = audit.AuditEntry(
            request_id=args.request_id or audit.new_request_id(),
            company=company.name or root.name,
            worker=worker.name,
            domain=worker.domain,
            model=args.model,
            first_pass_score=LEGACY_FIRST_PASS_SCORE,
            rounds=args.rounds,
            verdict=args.verdict,
            reason=_normalize_reason(args.reason, args.embody),
            auto_hired=args.auto_hired,
        )
        audit.record(adapter, entry)
    except (LSKunKitError, OSError, ValueError) as e:
        print(f"lskun-audit: 기록 실패 — {e} (worker={args.worker!r}). 파일 미변경.", file=sys.stderr)
        return 1

    print(f"recorded {entry.request_id} {entry.verdict} {entry.worker}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "record":
        return _record(args)
    return 2  # pragma: no cover — argparse 가 선차단


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
