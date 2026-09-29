"""모델 계층: 프로그램에서 주고받는 데이터의 '모양'만 정의한다 (파일 I/O, 출력 없음)."""
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Transaction:
    """거래 내역 한 건"""

    id: str
    type: str          # "income" 또는 "expense"
    date: str          # "YYYY-MM-DD"
    amount: int        # 양의 정수
    category: str
    memo: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """파일에 저장하기 위한 딕셔너리로 변환"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Transaction":
        """파일에서 읽은 딕셔너리를 Transaction으로 변환 (필수 키가 없으면 KeyError)"""
        tags = data.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        return cls(
            id=str(data["id"]),
            type=str(data["type"]),
            date=str(data["date"]),
            amount=int(data["amount"]),
            category=str(data["category"]),
            memo=str(data.get("memo") or ""),
            tags=[str(t) for t in tags],
        )


@dataclass
class SearchFilter:
    """검색/내보내기 조건. None인 조건은 검사하지 않는다 (모든 조건은 AND)."""

    date_from: str | None = None   # 이 날짜 이후 (포함)
    date_to: str | None = None     # 이 날짜 이전 (포함)
    month: str | None = None       # "YYYY-MM"
    category: str | None = None
    tx_type: str | None = None
    keyword: str | None = None     # 메모에 포함된 글자 (대소문자 무시)
    tag: str | None = None         # 태그 중 하나와 일치 (대소문자 무시)

    def matches(self, tx: Transaction) -> bool:
        if self.date_from and tx.date < self.date_from:
            return False
        if self.date_to and tx.date > self.date_to:
            return False
        if self.month and not tx.date.startswith(self.month + "-"):
            return False
        if self.category and tx.category != self.category:
            return False
        if self.tx_type and tx.type != self.tx_type:
            return False
        if self.keyword and self.keyword.lower() not in tx.memo.lower():
            return False
        if self.tag and self.tag.lower() not in (t.lower() for t in tx.tags):
            return False
        return True


@dataclass
class MonthlySummary:
    """월별 요약 결과"""

    month: str
    count: int
    income: int
    expense: int
    top_categories: list[tuple[str, int]]
    budget: int | None = None

    @property
    def balance(self) -> int:
        return self.income - self.expense

    @property
    def usage_rate(self) -> float | None:
        """예산 대비 지출 비율(%). 예산이 없으면 None"""
        if not self.budget:
            return None
        return self.expense / self.budget * 100

    @property
    def over_amount(self) -> int:
        """예산 초과 금액. 초과하지 않았거나 예산이 없으면 0"""
        if not self.budget:
            return 0
        return max(0, self.expense - self.budget)


@dataclass
class ImportResult:
    """CSV 가져오기 결과"""

    imported: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
