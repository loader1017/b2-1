"""출력 포맷 등 공통 유틸리티."""
from __future__ import annotations

from typing import Iterable, List

from .models import Transaction


def format_transaction_line(tx: Transaction) -> str:
    memo = tx.memo or ""
    return f"{tx.id} | {tx.date} | {tx.type.value} | {tx.category} | {tx.amount} | {memo}"


def print_transactions(transactions: Iterable[Transaction]) -> None:
    any_row = False
    for tx in transactions:
        any_row = True
        print(format_transaction_line(tx))
    if not any_row:
        print("(결과 없음)")


def parse_tags(raw: str) -> List[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]
