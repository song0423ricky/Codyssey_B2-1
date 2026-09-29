import heapq
from collections.abc import Iterable

from .models import Transaction


def latest(transactions: Iterable[Transaction], limit: int) -> list[Transaction]:
    """날짜 최신순으로 상위 limit개를 돌려준다.

    전체를 메모리에 올리지 않고, limit개짜리 순위표만 유지하며 스트리밍으로 고른다.
    같은 날짜면 id가 큰(나중에 입력한) 거래가 먼저 온다.
    """
    return heapq.nlargest(limit, transactions, key=lambda t: (t.date, t.id))