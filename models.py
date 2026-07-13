"""데이터 모델 및 공통 예외 정의 모듈."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List


class TransactionType(str, Enum):
    """거래 유형."""

    INCOME = "income"
    EXPENSE = "expense"


class AppError(Exception):
    """애플리케이션 공통 예외. 원인(cause)과 해결 힌트(hint)를 함께 갖는다."""

    def __init__(self, cause: str, hint: str = "") -> None:
        self.cause = cause
        self.hint = hint
        super().__init__(cause)


class ValidationError(AppError):
    """입력 값 검증 실패 시 발생하는 예외."""


class NotFoundError(AppError):
    """조회/수정/삭제 대상이 존재하지 않을 때 발생하는 예외."""


class ConflictError(AppError):
    """상태 충돌(예: 사용 중인 카테고리 삭제 시도) 시 발생하는 예외."""


@dataclass
class Transaction:
    """거래 내역 하나를 표현하는 데이터 모델.

    id, type, date, amount, category, memo, tags 필드를 가지며
    입출력 계약을 명확히 하기 위해 dataclass + 타입 힌트로 정의한다.
    """

    id: str
    type: TransactionType
    date: str  # YYYY-MM-DD
    amount: int
    category: str
    memo: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value if isinstance(self.type, TransactionType) else self.type
        return data

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Transaction":
        return Transaction(
            id=data["id"],
            type=TransactionType(data["type"]),
            date=data["date"],
            amount=int(data["amount"]),
            category=data["category"],
            memo=data.get("memo", "") or "",
            tags=list(data.get("tags", []) or []),
        )
