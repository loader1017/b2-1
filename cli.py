"""CLI 계층.

argparse로 서브커맨드를 정의하고, add처럼 대화형 입력이 기본인 명령과
search/list/summary/export/import/delete/update처럼 옵션 인자를 지원하는
명령을 구분하여 처리한다. 각 명령 핸들러에는 공통 관심사 데코레이터
(handle_errors/measure_time/log_call)를 적용한다.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from .decorators import handle_errors, log_call, measure_time
from .service import BudgetService
from .storage import BudgetStore, CategoryStore, TransactionRepository
from .utils import parse_tags, print_transactions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="budget_app",
        description="파일 기반 가계부 콘솔 프로그램",
    )
    parser.add_argument("--data-dir", default="./data", help="데이터 저장 폴더 (기본값: ./data)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("add", help="거래 추가 (대화형)")

    list_p = subparsers.add_parser("list", help="거래 목록 조회 (최신순, 스트리밍)")
    list_p.add_argument("--limit", type=int, default=20, help="출력할 최대 건수 (기본값: 20)")

    search_p = subparsers.add_parser("search", help="조건 기반 거래 검색")
    search_p.add_argument("--from", dest="date_from", help="검색 시작일 YYYY-MM-DD")
    search_p.add_argument("--to", dest="date_to", help="검색 종료일 YYYY-MM-DD")
    search_p.add_argument("--category", help="카테고리")
    search_p.add_argument("--type", help="income 또는 expense")
    search_p.add_argument("--q", dest="query", help="메모 키워드")
    search_p.add_argument("--tag", help="태그")

    summary_p = subparsers.add_parser("summary", help="월별 요약 (수입/지출/잔액/카테고리 TOP N)")
    summary_p.add_argument("--month", required=True, help="YYYY-MM")
    summary_p.add_argument("--top", type=int, default=5, help="지출 카테고리 TOP N (기본값: 5)")

    budget_p = subparsers.add_parser("budget", help="예산 설정/조회")
    budget_sub = budget_p.add_subparsers(dest="budget_command", required=True)
    budget_set_p = budget_sub.add_parser("set", help="월 예산 설정")
    budget_set_p.add_argument("--month", required=True, help="YYYY-MM")
    budget_set_p.add_argument("--amount", required=True, help="예산 금액 (양수)")

    category_p = subparsers.add_parser("category", help="카테고리 관리")
    category_sub = category_p.add_subparsers(dest="category_command", required=True)
    category_sub.add_parser("add", help="카테고리 추가 (대화형)")
    category_sub.add_parser("list", help="카테고리 목록 조회")
    category_remove_p = category_sub.add_parser("remove", help="카테고리 삭제")
    category_remove_p.add_argument("--name", help="삭제할 카테고리명 (미입력 시 대화형으로 입력받음)")

    update_p = subparsers.add_parser("update", help="거래 수정 (옵션 기반, --id 필수)")
    update_p.add_argument("--id", required=True, help="수정할 거래 id")
    update_p.add_argument("--date", help="YYYY-MM-DD")
    update_p.add_argument("--type", help="income 또는 expense")
    update_p.add_argument("--category", help="카테고리")
    update_p.add_argument("--amount", help="금액 (양수)")
    update_p.add_argument("--memo", help="메모")
    update_p.add_argument("--tags", help="쉼표로 구분한 태그 목록")

    delete_p = subparsers.add_parser("delete", help="거래 삭제")
    delete_p.add_argument("--id", required=True, help="삭제할 거래 id")

    import_p = subparsers.add_parser("import", help="CSV 파일에서 거래 일괄 등록")
    import_p.add_argument("--from", dest="from_file", required=True, help="가져올 CSV 파일 경로")

    export_p = subparsers.add_parser("export", help="조건에 맞는 거래를 CSV로 내보내기")
    export_p.add_argument("--out", required=True, help="내보낼 CSV 파일 경로")
    export_p.add_argument("--month", help="YYYY-MM (month 또는 from/to 중 하나 이상 필수)")
    export_p.add_argument("--from", dest="date_from", help="YYYY-MM-DD")
    export_p.add_argument("--to", dest="date_to", help="YYYY-MM-DD")

    subparsers.add_parser("backup", help="[보너스] 타임스탬프 포함 데이터 백업 생성")

    return parser


# ---------------------------------------------------------------------------
# 명령 핸들러 (공통 관심사 데코레이터 적용)
# ---------------------------------------------------------------------------


@handle_errors
@measure_time
@log_call
def cmd_add(service: BudgetService) -> None:
    date = input("날짜(YYYY-MM-DD): ").strip()
    type_ = input("타입(income/expense): ").strip()
    category = input("카테고리: ").strip()
    amount = input("금액(양수): ").strip()
    memo = input("메모(선택): ").strip()
    tags_raw = input("태그(쉼표로 구분, 없으면 엔터): ").strip()
    tx = service.add_transaction(date, type_, category, amount, memo, parse_tags(tags_raw))
    print(f"[저장 완료] id={tx.id}")


@handle_errors
@measure_time
@log_call
def cmd_list(service: BudgetService, limit: int) -> None:
    print_transactions(service.list_transactions(limit))


@handle_errors
@measure_time
@log_call
def cmd_search(service: BudgetService, args: argparse.Namespace) -> None:
    results = service.search_transactions(
        date_from=args.date_from,
        date_to=args.date_to,
        category=args.category,
        type_=args.type,
        query=args.query,
        tag=args.tag,
    )
    print_transactions(results)


@handle_errors
@measure_time
@log_call
def cmd_summary(service: BudgetService, month: str, top: int) -> None:
    result = service.summary(month, top)
    if not result["has_data"]:
        print("데이터 없음")
        return
    print(f"총 수입: {result['total_income']}원")
    print(f"총 지출: {result['total_expense']}원")
    print(f"잔액: {result['balance']}원")
    if result["budget_amount"] is not None:
        print(f"예산: {result['budget_amount']}원 (사용률 {result['usage_rate']}%)")
        if result["over_budget"]:
            print("[경고] 예산을 초과했습니다!")
    if result["top_categories"]:
        print(f"지출 TOP {len(result['top_categories'])}")
        for i, (cat, amt) in enumerate(result["top_categories"], start=1):
            print(f"{i}) {cat} {amt}원")


@handle_errors
@measure_time
@log_call
def cmd_budget_set(service: BudgetService, month: str, amount: str) -> None:
    amt = service.set_budget(month, amount)
    print(f"[저장 완료] {month} 예산 {amt}원")


@handle_errors
@measure_time
@log_call
def cmd_category_add(service: BudgetService) -> None:
    name = input("카테고리명: ").strip()
    service.add_category(name)
    print(f"[저장 완료] category={name}")


@handle_errors
@measure_time
@log_call
def cmd_category_list(service: BudgetService) -> None:
    for cat in service.list_categories():
        print(f"- {cat}")


@handle_errors
@measure_time
@log_call
def cmd_category_remove(service: BudgetService, name: Optional[str]) -> None:
    if not name:
        name = input("삭제할 카테고리명: ").strip()
    service.remove_category(name)
    print(f"[삭제 완료] category={name}")


@handle_errors
@measure_time
@log_call
def cmd_update(service: BudgetService, args: argparse.Namespace) -> None:
    tags = parse_tags(args.tags) if args.tags is not None else None
    tx = service.update_transaction(
        args.id,
        date=args.date,
        type=args.type,
        category=args.category,
        amount=args.amount,
        memo=args.memo,
        tags=tags,
    )
    print(f"[수정 완료] id={tx.id}")


@handle_errors
@measure_time
@log_call
def cmd_delete(service: BudgetService, tx_id: str) -> None:
    service.delete_transaction(tx_id)
    print(f"[삭제 완료] id={tx_id}")


@handle_errors
@measure_time
@log_call
def cmd_import(service: BudgetService, from_file: str) -> None:
    result = service.import_csv(from_file)
    print(f"[완료] imported={result['imported']}, skipped={result['skipped']}")


@handle_errors
@measure_time
@log_call
def cmd_export(service: BudgetService, out: str, month: Optional[str], date_from: Optional[str], date_to: Optional[str]) -> None:
    count = service.export_csv(out, month=month, date_from=date_from, date_to=date_to)
    print(f"[완료] {out} ({count} records)")


@handle_errors
@measure_time
@log_call
def cmd_backup(service: BudgetService, data_dir: Path) -> None:
    target = service.backup(data_dir)
    print(f"[백업 완료] {target}")


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------


def run(argv: Optional[list] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    tx_repo = TransactionRepository(data_dir / "transactions.jsonl")
    cat_store = CategoryStore(data_dir / "categories.jsonl")
    budget_store = BudgetStore(data_dir / "budgets.jsonl")
    service = BudgetService(tx_repo, cat_store, budget_store)

    if args.command == "add":
        cmd_add(service)
    elif args.command == "list":
        cmd_list(service, args.limit)
    elif args.command == "search":
        cmd_search(service, args)
    elif args.command == "summary":
        cmd_summary(service, args.month, args.top)
    elif args.command == "budget":
        if args.budget_command == "set":
            cmd_budget_set(service, args.month, args.amount)
    elif args.command == "category":
        if args.category_command == "add":
            cmd_category_add(service)
        elif args.category_command == "list":
            cmd_category_list(service)
        elif args.category_command == "remove":
            cmd_category_remove(service, args.name)
    elif args.command == "update":
        cmd_update(service, args)
    elif args.command == "delete":
        cmd_delete(service, args.id)
    elif args.command == "import":
        cmd_import(service, args.from_file)
    elif args.command == "export":
        cmd_export(service, args.out, args.month, args.date_from, args.date_to)
    elif args.command == "backup":
        cmd_backup(service, data_dir)
