"""파일 기반 저장소 계층.

거래(Transaction), 카테고리(Category), 예산(Budget) 데이터를
JSONL 파일 3개로 분리하여 영구 저장한다.

- 조회는 제너레이터로 한 줄씩 스트리밍 처리한다 (파일 전체를 한 번에 메모리에 올리지 않음).
- update/delete 처럼 파일 내용을 바꿔야 하는 경우, 임시 파일에 새 내용을 모두 쓴 뒤
  os.replace()로 원자적으로 교체하여 중간에 프로그램이 죽어도 원본이 깨지지 않도록 한다.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Generator, Iterable, List, Optional

from .models import NotFoundError, Transaction

DEFAULT_CATEGORIES = ["food", "transport", "rent", "etc"]


def _atomic_write_lines(path: Path, lines: Iterable[str]) -> None:
    """임시 파일에 쓴 뒤 rename으로 원자적 교체한다."""
    directory = path.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(directory), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line.rstrip("\n") + "\n")
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


class TransactionRepository:
    """거래 내역 파일 저장소 (transactions.jsonl).

    책임 범위: 파일을 읽고/쓰는 I/O만 담당한다. "이 category가 존재하는가",
    "금액이 양수인가" 같은 업무 규칙 검증은 이 클래스가 알지 못하며,
    그 판단은 상위 계층인 service.py(BudgetService)의 책임이다.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()
            print(f"[안내] 거래 저장 파일을 새로 생성했습니다: {self.path}")
        # id 발급용 카운터. transactions.jsonl과 나란히 둔 별도 파일에 마지막으로
        # 발급한 번호만 저장해서, add 할 때마다 전체 파일을 스캔하지 않도록 한다.
        # (거래 10만 건 환경에서 매 add마다 O(n) 스캔이 발생하는 것을 방지하는 최적화)
        self.counter_path = self.path.with_suffix(self.path.suffix + ".counter")
        if not self.counter_path.exists():
            self._rebuild_counter()

    def _rebuild_counter(self) -> None:
        """카운터 파일이 없을 때(최초 실행 등) 기존 데이터를 한 번만 스캔해 복구한다."""
        max_num = 0
        for tx in self.iter_all():
            try:
                num = int(tx.id.split("-")[-1])
                max_num = max(max_num, num)
            except (ValueError, IndexError):
                continue
        self.counter_path.write_text(str(max_num), encoding="utf-8")

    def iter_all(self) -> Generator[Transaction, None, None]:
        """파일 전체를 메모리에 올리지 않고 한 줄씩 읽어 스트리밍한다."""
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield Transaction.from_dict(json.loads(line))

    def append(self, tx: Transaction) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(tx.to_dict(), ensure_ascii=False) + "\n")
        try:
            num = int(tx.id.split("-")[-1])
            current = int(self.counter_path.read_text(encoding="utf-8").strip() or "0")
            if num > current:
                self.counter_path.write_text(str(num), encoding="utf-8")
        except (ValueError, IndexError):
            pass

    def next_id(self) -> str:
        """카운터 파일 1줄만 읽어 O(1)로 다음 id를 계산한다 (전체 스캔 없음)."""
        current = int(self.counter_path.read_text(encoding="utf-8").strip() or "0")
        return f"TX-{current + 1:06d}"

    def replace_all(self, transactions: Iterable[Transaction]) -> None:
        lines = (json.dumps(tx.to_dict(), ensure_ascii=False) for tx in transactions)
        _atomic_write_lines(self.path, lines)

    def update(self, tx_id: str, changes: Dict[str, object]) -> Transaction:
        found: Optional[Transaction] = None
        result: List[Transaction] = []
        for tx in self.iter_all():
            if tx.id == tx_id:
                data = tx.to_dict()
                data.update({k: v for k, v in changes.items() if v is not None})
                found = Transaction.from_dict(data)
                result.append(found)
            else:
                result.append(tx)
        if found is None:
            raise NotFoundError(
                f"id '{tx_id}' 에 해당하는 거래가 없습니다.",
                "list 명령으로 존재하는 id를 확인하세요.",
            )
        self.replace_all(result)
        return found

    def delete(self, tx_id: str) -> None:
        found = False
        result: List[Transaction] = []
        for tx in self.iter_all():
            if tx.id == tx_id:
                found = True
                continue
            result.append(tx)
        if not found:
            raise NotFoundError(
                f"id '{tx_id}' 에 해당하는 거래가 없습니다.",
                "list 명령으로 존재하는 id를 확인하세요.",
            )
        self.replace_all(result)

    def category_in_use(self, category: str) -> bool:
        return any(tx.category == category for tx in self.iter_all())


class CategoryStore:
    """카테고리 파일 저장소 (categories.jsonl).

    파일이 없거나 비어 있으면 기본 카테고리(food/transport/rent/etc)를 자동 생성한다.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not self.path.exists()
        if is_new:
            self.path.touch()
        if is_new or self._is_empty():
            self._write_defaults()
            print(f"[안내] 카테고리가 비어 있어 기본 카테고리를 생성했습니다: {', '.join(DEFAULT_CATEGORIES)}")

    def _is_empty(self) -> bool:
        return self.path.stat().st_size == 0

    def _write_defaults(self) -> None:
        _atomic_write_lines(
            self.path,
            (json.dumps({"name": name}, ensure_ascii=False) for name in DEFAULT_CATEGORIES),
        )

    def iter_all(self) -> Generator[str, None, None]:
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)["name"]

    def list(self) -> List[str]:
        return list(self.iter_all())

    def exists(self, name: str) -> bool:
        return name in self.list()

    def add(self, name: str) -> None:
        if self.exists(name):
            raise ValueError(f"이미 존재하는 카테고리입니다: {name}")
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"name": name}, ensure_ascii=False) + "\n")

    def remove(self, name: str) -> None:
        names = [n for n in self.list() if n != name]
        _atomic_write_lines(self.path, (json.dumps({"name": n}, ensure_ascii=False) for n in names))


class BudgetStore:
    """예산 파일 저장소 (budgets.jsonl). 월(month)별 금액을 관리한다."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def _load(self) -> Dict[str, int]:
        budgets: Dict[str, int] = {}
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                budgets[data["month"]] = int(data["amount"])
        return budgets

    def get(self, month: str) -> Optional[int]:
        return self._load().get(month)

    def set(self, month: str, amount: int) -> None:
        budgets = self._load()
        budgets[month] = amount
        _atomic_write_lines(
            self.path,
            (
                json.dumps({"month": m, "amount": a}, ensure_ascii=False)
                for m, a in sorted(budgets.items())
            ),
        )
