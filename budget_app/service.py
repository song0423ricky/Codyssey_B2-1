"""서비스 계층: 가계부의 규칙과 계산을 담당한다 (파일 형식·화면 출력은 모름).

- 저장소(repository)에서 받은 제너레이터를 걸러내고/집계하고/정렬한다.
- 업무 규칙(등록된 카테고리만 사용, 사용 중 카테고리 삭제 금지 등)을 지킨다.
"""
import dataclasses
import heapq
from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from .csv_io import iter_csv_rows, write_csv
from .errors import BudgetAppError, ConflictError, NotFoundError, ValidationError
from .models import ImportResult, MonthlySummary, SearchFilter, Transaction
from .repository import BudgetStore, CategoryStore, TransactionRepository, backup_files
from .validators import parse_amount, parse_date, parse_tags, parse_type


def latest_of(transactions: Iterable[Transaction], limit: int) -> list[Transaction]:
    """날짜 최신순 상위 limit개. 전체를 모으지 않고 limit개짜리 순위표만 유지한다.
    같은 날짜면 id가 큰(나중에 입력한) 거래가 먼저 온다."""
    return heapq.nlargest(limit, transactions, key=lambda t: (t.date, t.id))


class BudgetService:
    def __init__(
        self,
        transactions: TransactionRepository,
        categories: CategoryStore,
        budgets: BudgetStore,
    ) -> None:
        self.transactions = transactions
        self.categories = categories
        self.budgets = budgets

    # ---------------- 카테고리 ----------------

    def list_categories(self) -> list[str]:
        return self.categories.list_all()

    def require_category(self, name: str, known: set[str] | None = None) -> str:
        """등록된 카테고리인지 확인하고 그대로 돌려준다. 아니면 NotFoundError"""
        names = known if known is not None else set(self.categories.list_all())
        if name not in names:
            available = ", ".join(self.categories.list_all()) or "(없음)"
            raise NotFoundError(
                f"등록되지 않은 카테고리입니다: '{name}'",
                f"사용 가능: {available} / 새 카테고리는 'category add'로 먼저 등록하세요.",
            )
        return name

    def add_category(self, name: str) -> None:
        if self.categories.exists(name):
            raise ConflictError(
                f"이미 등록된 카테고리입니다: '{name}'",
                "category list로 목록을 확인하세요.",
            )
        self.categories.add(name)

    def remove_category(self, name: str) -> None:
        """사용 중인 카테고리는 삭제를 막는다."""
        if not self.categories.exists(name):
            raise NotFoundError(
                f"등록되지 않은 카테고리입니다: '{name}'",
                "category list로 목록을 확인하세요.",
            )
        used = sum(1 for t in self.transactions.iter_all() if t.category == name)
        if used:
            raise ConflictError(
                f"'{name}' 카테고리를 사용하는 거래가 {used}건 있어 삭제할 수 없습니다.",
                f"search --category {name}로 거래를 확인한 뒤 "
                f"update --id <id> --category <다른 카테고리>로 바꾸거나 delete로 지우세요.",
            )
        self.categories.remove(name)

    # ---------------- 거래 ----------------

    def add_transaction(
        self,
        *,
        date: str,
        tx_type: str,
        category: str,
        amount: int,
        memo: str = "",
        tags: list[str] | None = None,
    ) -> Transaction:
        self.require_category(category)
        tx = Transaction(
            id=self.transactions.next_id(),
            type=tx_type,
            date=date,
            amount=amount,
            category=category,
            memo=memo,
            tags=tags or [],
        )
        self.transactions.add(tx)
        return tx

    def latest(self, limit: int) -> list[Transaction]:
        return latest_of(self.transactions.iter_all(), limit)

    def search(self, flt: SearchFilter, limit: int) -> tuple[list[Transaction], int]:
        """조건에 맞는 거래를 최신순 limit개와 전체 일치 건수로 돌려준다."""
        self._check_range(flt)
        total = 0

        def matched() -> Iterator[Transaction]:
            nonlocal total
            for tx in self.transactions.iter_all():      # 저장소: 한 줄씩
                if flt.matches(tx):                       # 서비스: 조건 검사
                    total += 1
                    yield tx

        rows = latest_of(matched(), limit)
        return rows, total

    def get_transaction(self, tx_id: str) -> Transaction:
        tx = self.transactions.find(tx_id)
        if tx is None:
            raise NotFoundError(
                f"id={tx_id} 거래가 없습니다.",
                "list 또는 search로 존재하는 id를 확인하세요.",
            )
        return tx

    def update_transaction(
        self, tx_id: str, changes: dict[str, Any]
    ) -> tuple[Transaction, Transaction]:
        """changes에 들어온 필드만 바꾼다. (수정 전, 수정 후)를 돌려준다."""
        if not changes:
            raise ValidationError(
                "수정할 항목이 없습니다.",
                "예: update --id TX-000001 --amount 20000 --memo 저녁",
            )
        before = self.get_transaction(tx_id)
        if "category" in changes:
            self.require_category(changes["category"])
        after = dataclasses.replace(before, **changes)
        self.transactions.update(after)
        return before, after

    def delete_transaction(self, tx_id: str) -> Transaction:
        tx = self.get_transaction(tx_id)
        self.transactions.delete(tx_id)
        return tx

    # ---------------- 요약 / 예산 ----------------

    def monthly_summary(self, month: str, top: int) -> MonthlySummary:
        income = expense = count = 0
        by_category: dict[str, int] = defaultdict(int)
        prefix = month + "-"
        for tx in self.transactions.iter_all():          # 스트리밍 집계
            if not tx.date.startswith(prefix):
                continue
            count += 1
            if tx.type == "income":
                income += tx.amount
            else:
                expense += tx.amount
                by_category[tx.category] += tx.amount
        top_categories = heapq.nlargest(top, by_category.items(), key=lambda kv: kv[1])
        return MonthlySummary(
            month=month,
            count=count,
            income=income,
            expense=expense,
            top_categories=top_categories,
            budget=self.budgets.get(month),
        )

    def set_budget(self, month: str, amount: int) -> int | None:
        """예산을 저장하고, 이전에 설정돼 있던 금액(없으면 None)을 돌려준다."""
        previous = self.budgets.get(month)
        self.budgets.set(month, amount)
        return previous

    def get_budget(self, month: str) -> int | None:
        return self.budgets.get(month)

    def all_budgets(self) -> dict[str, int]:
        return self.budgets.all()

    # ---------------- CSV 가져오기 / 내보내기 ----------------

    def export_csv(self, out: Path, flt: SearchFilter) -> int:
        if not (flt.month or flt.date_from or flt.date_to):
            raise ValidationError(
                "export에는 기간 조건이 필요합니다.",
                "--month YYYY-MM 또는 --from YYYY-MM-DD / --to YYYY-MM-DD 중 하나 이상을 지정하세요.",
            )
        self._check_range(flt)
        matched = (t for t in self.transactions.iter_all() if flt.matches(t))
        return write_csv(out, matched)

    def import_csv(self, src: Path) -> ImportResult:
        """올바른 행만 새 id로 추가하고, 잘못된 행은 이유와 함께 건너뛴다."""
        result = ImportResult()
        known = set(self.categories.list_all())
        next_num = self.transactions.max_number() + 1

        def valid_transactions() -> Iterator[Transaction]:
            nonlocal next_num
            for line_no, row in iter_csv_rows(src):
                try:
                    tx = Transaction(
                        id=f"TX-{next_num:06d}",
                        date=parse_date(row.get("date", "")),
                        type=parse_type(row.get("type", "")),
                        category=self.require_category(row.get("category", ""), known),
                        amount=parse_amount(row.get("amount", "")),
                        memo=row.get("memo", ""),
                        tags=parse_tags(row.get("tags", "")),
                    )
                except BudgetAppError as e:
                    result.skipped += 1
                    result.errors.append(f"{line_no}행: {e.message}")
                    continue
                next_num += 1
                result.imported += 1
                yield tx

        self.transactions.add_many(valid_transactions())
        return result

    # ---------------- 백업 ----------------

    def backup(self) -> Path:
        files = [self.transactions.path, self.categories.path, self.budgets.path]
        return backup_files(files, self.transactions.path.parent / "backups")

    # ---------------- 내부 도우미 ----------------

    @staticmethod
    def _check_range(flt: SearchFilter) -> None:
        if flt.date_from and flt.date_to and flt.date_from > flt.date_to:
            raise ValidationError(
                f"기간이 올바르지 않습니다: --from {flt.date_from}이(가) --to {flt.date_to}보다 늦습니다.",
                "--from에는 시작 날짜, --to에는 끝 날짜를 넣으세요.",
            )
