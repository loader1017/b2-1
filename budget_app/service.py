"""비즈니스 로직 계층. CLI는 이 서비스 계층만 호출한다."""
from __future__ import annotations

import csv
import heapq
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .models import (
    ConflictError,
    NotFoundError,
    SummaryResult,
    Transaction,
    TransactionType,
    ValidationError,
)
from .storage import BudgetStore, CategoryStore, TransactionRepository
from .validators import validate_amount, validate_category, validate_date, validate_month, validate_type


class BudgetService:
    """거래/카테고리/예산에 대한 도메인 로직을 담당하는 서비스 계층."""

    def __init__(self, tx_repo: TransactionRepository, cat_store: CategoryStore, budget_store: BudgetStore) -> None:
        self.tx_repo = tx_repo
        self.cat_store = cat_store
        self.budget_store = budget_store

    # ---------- 거래 ----------
    def add_transaction(
        self, date: str, type_: str, category: str, amount: str, memo: str = "", tags: Optional[List[str]] = None
    ) -> Transaction:
        date = validate_date(date)
        type_ = validate_type(type_)
        category = validate_category(category, self.cat_store.list())
        amount_val = validate_amount(amount)
        tx_id = self.tx_repo.next_id()
        tx = Transaction(
            id=tx_id,
            type=TransactionType(type_),
            date=date,
            amount=amount_val,
            category=category,
            memo=memo or "",
            tags=tags or [],
        )
        self.tx_repo.append(tx)
        return tx

    def list_transactions(self, limit: int = 20) -> List[Transaction]:
        """최신순 상위 limit개만 반환한다.

        전체를 리스트로 모아 정렬(sorted)하면 거래가 10만 건이어도 10만 건이
        전부 메모리에 올라간다. heapq.nlargest는 내부적으로 크기 limit짜리
        힙만 유지하므로, limit이 작을 때 메모리 사용량을 크게 줄인다.
        (파일은 여전히 iter_all()로 한 줄씩 스트리밍해서 읽는다.)
        """
        return heapq.nlargest(limit, self.tx_repo.iter_all(), key=lambda t: (t.date, t.id))

    def search_transactions(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        category: Optional[str] = None,
        type_: Optional[str] = None,
        query: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Transaction]:
        if date_from:
            date_from = validate_date(date_from)
        if date_to:
            date_to = validate_date(date_to)

        def matches(tx: Transaction) -> bool:
            if date_from and tx.date < date_from:
                return False
            if date_to and tx.date > date_to:
                return False
            if category and tx.category != category:
                return False
            if type_ and tx.type.value != type_:
                return False
            if query and query.lower() not in (tx.memo or "").lower():
                return False
            if tag and tag not in tx.tags:
                return False
            return True

        results = [tx for tx in self.tx_repo.iter_all() if matches(tx)]
        return sorted(results, key=lambda t: (t.date, t.id), reverse=True)

    def update_transaction(self, tx_id: str, **changes: object) -> Transaction:
        clean: Dict[str, object] = {}
        if changes.get("date") is not None:
            clean["date"] = validate_date(str(changes["date"]))
        if changes.get("type") is not None:
            clean["type"] = validate_type(str(changes["type"]))
        if changes.get("category") is not None:
            clean["category"] = validate_category(str(changes["category"]), self.cat_store.list())
        if changes.get("amount") is not None:
            clean["amount"] = validate_amount(str(changes["amount"]))
        if changes.get("memo") is not None:
            clean["memo"] = changes["memo"]
        if changes.get("tags") is not None:
            clean["tags"] = changes["tags"]
        return self.tx_repo.update(tx_id, clean)

    def delete_transaction(self, tx_id: str) -> None:
        self.tx_repo.delete(tx_id)

    # ---------- 카테고리 ----------
    def add_category(self, name: str) -> None:
        name = (name or "").strip()
        if not name:
            raise ValidationError("카테고리명이 비어 있습니다.", "예: food")
        try:
            self.cat_store.add(name)
        except ValueError as exc:
            raise ValidationError(str(exc), "category list 로 기존 카테고리를 확인하세요.")

    def list_categories(self) -> List[str]:
        return self.cat_store.list()

    def remove_category(self, name: str) -> None:
        if not self.cat_store.exists(name):
            raise NotFoundError(f"존재하지 않는 카테고리입니다: {name}", "category list 로 확인하세요.")
        if self.tx_repo.category_in_use(name):
            raise ConflictError(
                f"'{name}' 카테고리를 사용 중인 거래가 있어 삭제할 수 없습니다.",
                "update 명령으로 해당 거래들을 다른 카테고리로 변경한 뒤 다시 시도하세요.",
            )
        self.cat_store.remove(name)

    # ---------- 예산/요약 ----------
    def set_budget(self, month: str, amount: str) -> int:
        month = validate_month(month)
        amount_val = validate_amount(amount)
        self.budget_store.set(month, amount_val)
        return amount_val

    def summary(self, month: str, top: int = 5) -> SummaryResult:
        month = validate_month(month)
        tx_in_month = [tx for tx in self.tx_repo.iter_all() if tx.date.startswith(month)]
        total_income = sum(t.amount for t in tx_in_month if t.type == TransactionType.INCOME)
        total_expense = sum(t.amount for t in tx_in_month if t.type == TransactionType.EXPENSE)

        by_category: Dict[str, int] = {}
        for t in tx_in_month:
            if t.type == TransactionType.EXPENSE:
                by_category[t.category] = by_category.get(t.category, 0) + t.amount
        top_categories = sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)[:top]

        budget_amount = self.budget_store.get(month)
        usage_rate = None
        over_budget = False
        if budget_amount:
            usage_rate = round(total_expense / budget_amount * 100, 1)
            over_budget = total_expense > budget_amount

        return {
            "has_data": bool(tx_in_month),
            "total_income": total_income,
            "total_expense": total_expense,
            "balance": total_income - total_expense,
            "top_categories": top_categories,
            "budget_amount": budget_amount,
            "usage_rate": usage_rate,
            "over_budget": over_budget,
        }

    # ---------- import/export ----------
    def export_csv(
        self, out_path: str, month: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None
    ) -> int:
        if not month and not (date_from or date_to):
            raise ValidationError(
                "export 조건이 없습니다.",
                "--month YYYY-MM 또는 --from/--to 중 하나 이상을 지정하세요.",
            )
        if month:
            month = validate_month(month)
            rows = [tx for tx in self.tx_repo.iter_all() if tx.date.startswith(month)]
            rows.sort(key=lambda t: (t.date, t.id), reverse=True)
        else:
            rows = self.search_transactions(date_from=date_from, date_to=date_to)

        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "type", "category", "amount", "memo", "tags"])
            for tx in rows:
                writer.writerow([tx.date, tx.type.value, tx.category, tx.amount, tx.memo, ",".join(tx.tags)])
        return len(rows)

    def import_csv(self, in_path: str, strict: bool = False) -> Dict[str, object]:
        """CSV에서 거래를 일괄 등록한다.

        정책: 먼저 모든 행을 검증만 하고(파일에는 아직 쓰지 않음), 그 결과에 따라
        - strict=False(기본): 유효한 행만 실제로 저장하고, 실패한 행은 행 번호와
          이유를 함께 보고한다(부분 성공 허용).
        - strict=True: 단 한 행이라도 검증에 실패하면 아무 것도 저장하지 않고
          전체를 중단한다(all-or-nothing). 미리 검증부터 끝내고 그 다음에만
          파일에 쓰기 때문에, 쓰다가 중간에 실패해서 일부만 반영되는 상황 자체가
          생기지 않는다.
        """
        path = Path(in_path)
        if not path.exists():
            raise ValidationError(f"파일을 찾을 수 없습니다: {in_path}", "경로를 다시 확인하세요.")

        valid_rows: List[Dict[str, object]] = []
        errors: List[Dict[str, object]] = []
        existing_categories = self.cat_store.list()

        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row_number, row in enumerate(reader, start=2):  # 1행은 헤더
                try:
                    date = validate_date(row.get("date", ""))
                    type_ = validate_type(row.get("type", ""))
                    category = validate_category(row.get("category", ""), existing_categories)
                    amount = validate_amount(row.get("amount", ""))
                    tags = [t for t in (row.get("tags") or "").split(",") if t]
                    valid_rows.append(
                        {
                            "date": date,
                            "type": type_,
                            "category": category,
                            "amount": amount,
                            "memo": row.get("memo", "") or "",
                            "tags": tags,
                        }
                    )
                except ValidationError as exc:
                    errors.append({"row": row_number, "reason": exc.cause})
                except Exception as exc:  # noqa: BLE001
                    errors.append({"row": row_number, "reason": str(exc)})

        if strict and errors:
            first = errors[0]
            raise ValidationError(
                f"{len(errors)}건의 행에서 오류가 발견되어 가져오기를 중단했습니다 (아무 것도 저장되지 않음).",
                f"예: 행 {first['row']} - {first['reason']}",
            )

        imported = 0
        for data in valid_rows:
            tx_id = self.tx_repo.next_id()
            tx = Transaction(
                id=tx_id,
                type=TransactionType(data["type"]),
                date=data["date"],
                amount=data["amount"],
                category=data["category"],
                memo=data["memo"],
                tags=data["tags"],
            )
            self.tx_repo.append(tx)
            imported += 1

        return {"imported": imported, "skipped": len(errors), "errors": errors}

    # ---------- 백업 (보너스) ----------
    def backup(self, data_dir: Path) -> Path:
        backup_dir = data_dir / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = backup_dir / stamp
        target.mkdir(parents=True, exist_ok=True)
        for name in ("transactions.jsonl", "categories.jsonl", "budgets.jsonl"):
            src = data_dir / name
            if src.exists():
                (target / name).write_bytes(src.read_bytes())
        return target
