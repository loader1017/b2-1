"""사용자 입력 검증 함수 모음.

모든 검증 실패는 ValidationError(원인, 힌트)로 통일하여
CLI 계층의 handle_errors 데코레이터가 일관되게 처리하도록 한다.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .models import TransactionType, ValidationError


def validate_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except (ValueError, TypeError):
        raise ValidationError(
            "날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).",
            "예: 2024-01-15",
        )
    return value


def validate_month(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m")
    except (ValueError, TypeError):
        raise ValidationError(
            f"월 형식이 올바르지 않습니다: '{value}'",
            "예: 2024-01",
        )
    return value


def validate_type(value: str) -> str:
    value = (value or "").strip().lower()
    if value not in (TransactionType.INCOME.value, TransactionType.EXPENSE.value):
        raise ValidationError(
            f"허용되지 않은 타입입니다: '{value}'",
            "income 또는 expense 중 하나를 입력하세요.",
        )
    return value


def validate_amount(value: str) -> int:
    try:
        amount = int(str(value).strip())
    except (ValueError, TypeError):
        raise ValidationError(
            f"금액은 숫자여야 합니다: '{value}'",
            "예: 15000",
        )
    if amount <= 0:
        raise ValidationError(
            "금액은 0보다 큰 양수여야 합니다.",
            "예: 15000",
        )
    return amount


def validate_category(value: str, existing: Iterable[str]) -> str:
    value = (value or "").strip()
    existing_set = set(existing)
    if value not in existing_set:
        raise ValidationError(
            f"등록되지 않은 카테고리입니다: '{value}'",
            "category add 로 먼저 카테고리를 등록하거나, category list 로 확인하세요.",
        )
    return value
