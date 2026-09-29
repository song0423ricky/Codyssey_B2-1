"""CLI 계층: 명령어 해석(argparse), 대화형 입력, 화면 출력만 담당한다.

실제 규칙과 계산은 service.py, 파일 입출력은 repository.py / csv_io.py가 한다.
"""
import argparse
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from . import __version__
from .decorators import EXIT_ERROR, EXIT_OK, handle_errors, log_execution, print_error
from .errors import BudgetAppError
from .formatter import format_summary, format_transaction_line, format_transactions, won
from .models import SearchFilter
from .repository import DEFAULT_CATEGORIES, BudgetStore, CategoryStore, TransactionRepository
from .service import BudgetService
from .validators import (
    parse_amount,
    parse_category_name,
    parse_date,
    parse_month,
    parse_tags,
    parse_tx_id,
    parse_type,
)

T = TypeVar("T")
Handler = Callable[[argparse.Namespace, BudgetService], int]


# ====================== 입력 도우미 ======================

def ask(prompt: str, parse: Callable[[str], T]) -> T:
    """올바른 값이 들어올 때까지 다시 묻는다 (오류 + 힌트 출력)."""
    while True:
        raw = input(prompt)
        try:
            return parse(raw)
        except BudgetAppError as e:
            print_error(e.message, e.hint, file=sys.stdout)


def optional(value: str | None, parse: Callable[[str], T]) -> T | None:
    """옵션이 주어졌을 때만 검증한다 (주어지지 않으면 None)."""
    return None if value is None else parse(value)


def positive_int(value: str) -> int:
    """argparse용 검사기: --limit, --top 값은 1 이상의 정수"""
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"양의 정수를 입력하세요 (입력값: {value})") from None
    if n <= 0:
        raise argparse.ArgumentTypeError(f"1 이상이어야 합니다 (입력값: {value})")
    return n


# ====================== 명령 ======================

@log_execution
def cmd_add(args: argparse.Namespace, service: BudgetService) -> int:
    print("새 거래를 입력하세요. (중단: Ctrl+C)")
    date = ask("날짜(YYYY-MM-DD): ", parse_date)
    tx_type = ask("타입(income/expense): ", parse_type)
    print(f"  등록된 카테고리: {', '.join(service.list_categories())}")
    category = ask(
        "카테고리: ",
        lambda raw: service.require_category(parse_category_name(raw)),
    )
    amount = ask("금액(양수): ", parse_amount)
    memo = input("메모(선택): ").strip()
    tags = parse_tags(input("태그(쉼표로 구분, 없으면 엔터): "))

    tx = service.add_transaction(
        date=date, tx_type=tx_type, category=category,
        amount=amount, memo=memo, tags=tags,
    )
    print(f"[저장 완료] id={tx.id}")
    return EXIT_OK


@log_execution
def cmd_list(args: argparse.Namespace, service: BudgetService) -> int:
    rows = service.latest(args.limit)
    if not rows:
        print("거래 내역이 없습니다.")
        print("[힌트] add 명령으로 거래를 추가하세요: python -m budget_app add")
        return EXIT_OK
    print(format_transactions(rows))
    print(f"(최신순 {len(rows)}건 표시, --limit {args.limit})")
    return EXIT_OK


@log_execution
def cmd_search(args: argparse.Namespace, service: BudgetService) -> int:
    flt = SearchFilter(
        date_from=optional(args.date_from, parse_date),
        date_to=optional(args.date_to, parse_date),
        category=optional(args.category, parse_category_name),
        tx_type=optional(args.type, parse_type),
        keyword=(args.q.strip() or None) if args.q is not None else None,
        tag=(args.tag.strip() or None) if args.tag is not None else None,
    )
    rows, total = service.search(flt, args.limit)
    if not rows:
        print("조건에 맞는 거래가 없습니다.")
        return EXIT_OK
    print(format_transactions(rows))
    print(f"(조건 일치 {total}건 중 최신순 {len(rows)}건 표시)")
    return EXIT_OK


@log_execution
def cmd_summary(args: argparse.Namespace, service: BudgetService) -> int:
    month = parse_month(args.month)
    print(format_summary(service.monthly_summary(month, args.top)))
    return EXIT_OK


@log_execution
def cmd_budget_set(args: argparse.Namespace, service: BudgetService) -> int:
    month = parse_month(args.month)
    amount = parse_amount(args.amount)
    previous = service.set_budget(month, amount)
    print(f"[저장 완료] {month} 예산 {won(amount)}")
    if previous is not None and previous != amount:
        print(f"  (기존 예산 {won(previous)}에서 변경)")
    return EXIT_OK


@log_execution
def cmd_budget_show(args: argparse.Namespace, service: BudgetService) -> int:
    if args.month is not None:
        month = parse_month(args.month)
        amount = service.get_budget(month)
        if amount is None:
            print(f"{month} 예산이 설정되지 않았습니다.")
            print(f"[힌트] budget set --month {month} --amount 500000")
        else:
            print(f"{month} 예산: {won(amount)}")
        return EXIT_OK

    budgets = service.all_budgets()
    if not budgets:
        print("설정된 예산이 없습니다.")
        print("[힌트] budget set --month 2024-01 --amount 500000")
        return EXIT_OK
    for month, amount in sorted(budgets.items()):
        print(f"- {month}: {won(amount)}")
    return EXIT_OK


@log_execution
def cmd_category_add(args: argparse.Namespace, service: BudgetService) -> int:
    name = (parse_category_name(args.name) if args.name is not None
            else ask("카테고리명: ", parse_category_name))
    service.add_category(name)
    print(f"[저장 완료] category={name}")
    return EXIT_OK


@log_execution
def cmd_category_list(args: argparse.Namespace, service: BudgetService) -> int:
    names = service.list_categories()
    if not names:
        print("등록된 카테고리가 없습니다.")
        return EXIT_OK
    for name in names:
        print(f"- {name}")
    return EXIT_OK


@log_execution
def cmd_category_remove(args: argparse.Namespace, service: BudgetService) -> int:
    name = (parse_category_name(args.name) if args.name is not None
            else ask("삭제할 카테고리명: ", parse_category_name))
    service.remove_category(name)
    print(f"[삭제 완료] category={name}")
    return EXIT_OK


@log_execution
def cmd_update(args: argparse.Namespace, service: BudgetService) -> int:
    tx_id = parse_tx_id(args.id)
    changes: dict[str, Any] = {}
    if args.date is not None:
        changes["date"] = parse_date(args.date)
    if args.type is not None:
        changes["type"] = parse_type(args.type)
    if args.category is not None:
        changes["category"] = parse_category_name(args.category)
    if args.amount is not None:
        changes["amount"] = parse_amount(args.amount)
    if args.memo is not None:
        changes["memo"] = args.memo.strip()
    if args.tags is not None:
        changes["tags"] = parse_tags(args.tags)

    before, after = service.update_transaction(tx_id, changes)
    print(f"[수정 완료] id={after.id}")
    print(f"  수정 전: {format_transaction_line(before)}")
    print(f"  수정 후: {format_transaction_line(after)}")
    return EXIT_OK


@log_execution
def cmd_delete(args: argparse.Namespace, service: BudgetService) -> int:
    tx = service.delete_transaction(parse_tx_id(args.id))
    print(f"[삭제 완료] {format_transaction_line(tx)}")
    return EXIT_OK


@log_execution
def cmd_import(args: argparse.Namespace, service: BudgetService) -> int:
    result = service.import_csv(Path(args.src))
    print(f"[완료] imported={result.imported}, skipped={result.skipped}")
    for message in result.errors[:10]:
        print(f"  - 건너뜀 {message}")
    if len(result.errors) > 10:
        print(f"  ... 외 {len(result.errors) - 10}건")
    if result.imported == 0 and result.skipped > 0:
        return EXIT_ERROR          # 한 건도 못 가져왔으면 실패로 종료
    return EXIT_OK


@log_execution
def cmd_export(args: argparse.Namespace, service: BudgetService) -> int:
    flt = SearchFilter(
        month=optional(args.month, parse_month),
        date_from=optional(args.date_from, parse_date),
        date_to=optional(args.date_to, parse_date),
    )
    out = Path(args.out)
    count = service.export_csv(out, flt)
    print(f"[완료] {out} ({count} records)")
    return EXIT_OK


@log_execution
def cmd_backup(args: argparse.Namespace, service: BudgetService) -> int:
    dest = service.backup()
    print(f"[완료] 백업 생성: {dest}")
    print("[힌트] 복구하려면 이 폴더의 파일을 data 폴더로 복사해 덮어쓰세요.")
    return EXIT_OK


# ====================== 명령어 해석 ======================

EPILOG = """\
사용 예:
  python -m budget_app add
  python -m budget_app list --limit 5
  python -m budget_app search --from 2024-01-01 --to 2024-01-31 --category food
  python -m budget_app summary --month 2024-01 --top 3
  python -m budget_app budget set --month 2024-01 --amount 500000
  python -m budget_app category add --name cafe
  python -m budget_app update --id TX-000001 --amount 20000 --memo 저녁
  python -m budget_app delete --id TX-000001
  python -m budget_app export --out export.csv --month 2024-01
  python -m budget_app import --from import.csv

각 명령의 자세한 사용법: python -m budget_app <명령> --help
전역 옵션(--data-dir, --verbose)은 명령 이름보다 앞에 씁니다.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="budget_app",
        description="용돈 기입장(가계부) 콘솔 프로그램",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--data-dir", default="./data",
                        help="데이터 저장 폴더 (기본값: ./data)")
    parser.add_argument("--verbose", action="store_true",
                        help="실행 로그와 실행 시간을 함께 출력")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    # add
    p = sub.add_parser("add", help="거래 추가 (대화형 입력)",
                       description="날짜, 타입, 카테고리, 금액, 메모, 태그를 차례로 입력받아 저장합니다.")
    p.set_defaults(handler=cmd_add)

    # list
    p = sub.add_parser("list", help="거래 목록 (날짜 최신순)",
                       description="거래를 날짜 최신순으로 출력합니다.")
    p.add_argument("--limit", type=positive_int, default=10, help="출력할 최대 개수 (기본값: 10)")
    p.set_defaults(handler=cmd_list)

    # search
    p = sub.add_parser("search", help="조건 검색 (날짜 최신순)",
                       description="여러 조건을 함께 쓰면 모두 만족하는 거래만 출력합니다(AND).")
    p.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="시작 날짜 (포함)")
    p.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="끝 날짜 (포함)")
    p.add_argument("--category", help="카테고리")
    p.add_argument("--type", help="income 또는 expense")
    p.add_argument("--q", metavar="KEYWORD", help="메모에 포함된 키워드 (대소문자 무시)")
    p.add_argument("--tag", help="태그")
    p.add_argument("--limit", type=positive_int, default=20, help="출력할 최대 개수 (기본값: 20)")
    p.set_defaults(handler=cmd_search)

    # summary
    p = sub.add_parser("summary", help="월별 요약 (수입/지출/잔액/예산/지출 TOP N)",
                       description="해당 월의 총수입, 총지출, 잔액, 예산 사용률, 카테고리별 지출 TOP N을 출력합니다.")
    p.add_argument("--month", required=True, metavar="YYYY-MM", help="요약할 월")
    p.add_argument("--top", type=positive_int, default=5, help="지출 상위 카테고리 개수 (기본값: 5)")
    p.set_defaults(handler=cmd_summary)

    # budget set / show
    p = sub.add_parser("budget", help="월 예산 설정/조회 (set / show)",
                       description="월 예산을 설정하거나 조회합니다.")
    budget_sub = p.add_subparsers(dest="budget_command", required=True, metavar="<set|show>")
    bp = budget_sub.add_parser("set", help="월 예산 설정 (같은 월이면 덮어씀)")
    bp.add_argument("--month", required=True, metavar="YYYY-MM")
    bp.add_argument("--amount", required=True, help="예산 금액 (양의 정수)")
    bp.set_defaults(handler=cmd_budget_set)
    bp = budget_sub.add_parser("show", help="예산 조회 (--month 생략 시 전체)")
    bp.add_argument("--month", metavar="YYYY-MM")
    bp.set_defaults(handler=cmd_budget_show)

    # category add / list / remove
    p = sub.add_parser("category", help="카테고리 관리 (add / list / remove)",
                       description="카테고리를 추가, 조회, 삭제합니다. 사용 중인 카테고리는 삭제할 수 없습니다.")
    cat_sub = p.add_subparsers(dest="category_command", required=True, metavar="<add|list|remove>")
    cp = cat_sub.add_parser("add", help="카테고리 추가 (--name 생략 시 대화형 입력)")
    cp.add_argument("--name", help="추가할 카테고리명")
    cp.set_defaults(handler=cmd_category_add)
    cp = cat_sub.add_parser("list", help="카테고리 목록")
    cp.set_defaults(handler=cmd_category_list)
    cp = cat_sub.add_parser("remove", help="카테고리 삭제 (--name 생략 시 대화형 입력)")
    cp.add_argument("--name", help="삭제할 카테고리명")
    cp.set_defaults(handler=cmd_category_remove)

    # update (옵션 방식으로 고정)
    p = sub.add_parser("update", help="거래 수정 (옵션 방식)",
                       description="지정한 옵션의 필드만 수정합니다. 최소 1개 이상 지정하세요. "
                                   "--memo \"\" 또는 --tags \"\"로 비울 수 있습니다.")
    p.add_argument("--id", required=True, help="수정할 거래 id (예: TX-000001)")
    p.add_argument("--date", metavar="YYYY-MM-DD")
    p.add_argument("--type", help="income 또는 expense")
    p.add_argument("--category")
    p.add_argument("--amount", help="양의 정수")
    p.add_argument("--memo")
    p.add_argument("--tags", help="쉼표로 구분 (예: meal,lunch)")
    p.set_defaults(handler=cmd_update)

    # delete
    p = sub.add_parser("delete", help="거래 삭제", description="id로 거래 한 건을 삭제합니다.")
    p.add_argument("--id", required=True, help="삭제할 거래 id (예: TX-000001)")
    p.set_defaults(handler=cmd_delete)

    # import
    p = sub.add_parser("import", help="CSV 가져오기",
                       description="CSV(date,type,category,amount,memo,tags)의 올바른 행을 새 거래로 추가합니다.")
    p.add_argument("--from", dest="src", required=True, metavar="CSV", help="가져올 CSV 파일 경로")
    p.set_defaults(handler=cmd_import)

    # export
    p = sub.add_parser("export", help="CSV 내보내기",
                       description="조건에 맞는 거래를 CSV로 저장합니다. "
                                   "--month 또는 --from/--to 중 하나 이상이 필요합니다.")
    p.add_argument("--out", required=True, metavar="CSV", help="저장할 CSV 파일 경로 (있으면 덮어씀)")
    p.add_argument("--month", metavar="YYYY-MM")
    p.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD")
    p.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD")
    p.set_defaults(handler=cmd_export)

    # backup (보너스)
    p = sub.add_parser("backup", help="저장 파일 백업 (data/backups/<시각>/)",
                       description="현재 저장 파일 3개를 타임스탬프 폴더에 복사합니다.")
    p.set_defaults(handler=cmd_backup)

    return parser


# ====================== 실행 ======================

def build_service(data_dir: Path) -> tuple[BudgetService, list[str]]:
    """저장소 3개와 서비스를 만들고, 초기화 안내 문구를 함께 돌려준다."""
    transactions = TransactionRepository(data_dir)
    categories = CategoryStore(data_dir)
    budgets = BudgetStore(data_dir)

    notices: list[str] = []
    created = [s.path.name for s in (transactions, categories, budgets) if s.created]
    if created:
        notices.append(f"[안내] 저장 파일을 새로 만들었습니다: {data_dir} ({', '.join(created)})")
    if categories.created_defaults:
        notices.append(f"[안내] 카테고리가 비어 있어 기본 카테고리를 등록했습니다: "
                       f"{', '.join(DEFAULT_CATEGORIES)}")
    return BudgetService(transactions, categories, budgets), notices


@handle_errors
def run(args: argparse.Namespace) -> int:
    service, notices = build_service(Path(args.data_dir))
    for notice in notices:
        print(notice)
    handler: Handler = args.handler
    return handler(args, service)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)     # 잘못된 옵션은 argparse가 사용법과 함께 종료 코드 2로 처리
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="[log] %(message)s",
    )
    return run(args)
