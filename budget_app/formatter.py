"""출력 포맷터: 외부 라이브러리 없이 문자열 폭을 계산해 표를 정렬한다.

한글은 터미널에서 2칸을 차지하므로 unicodedata로 실제 표시 폭을 계산한다.
"""
import unicodedata

from .models import MonthlySummary, Transaction


def won(amount: int) -> str:
    return f"{amount:,}원"


def display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def _pad(text: str, width: int, align: str) -> str:
    gap = " " * (width - display_width(text))
    return gap + text if align == "right" else text + gap


def format_table(headers: list[str], rows: list[list[str]], aligns: list[str]) -> str:
    widths = [
        max([display_width(h)] + [display_width(row[i]) for row in rows])
        for i, h in enumerate(headers)
    ]

    def line(cells: list[str]) -> str:
        return " | ".join(_pad(c, w, a) for c, w, a in zip(cells, widths, aligns)).rstrip()

    separator = "-+-".join("-" * w for w in widths)
    return "\n".join([line(headers), separator, *(line(r) for r in rows)])


def format_transactions(txs: list[Transaction]) -> str:
    headers = ["ID", "날짜", "타입", "카테고리", "금액", "메모", "태그"]
    aligns = ["left", "left", "left", "left", "right", "left", "left"]
    rows = [
        [t.id, t.date, t.type, t.category, f"{t.amount:,}", t.memo, ",".join(t.tags)]
        for t in txs
    ]
    return format_table(headers, rows, aligns)


def format_transaction_line(t: Transaction) -> str:
    tags = f" #{' #'.join(t.tags)}" if t.tags else ""
    return f"{t.id} | {t.date} | {t.type} | {t.category} | {won(t.amount)} | {t.memo}{tags}"


def format_summary(s: MonthlySummary) -> str:
    lines = [f"[{s.month} 월별 요약]"]

    if s.count == 0:
        lines.append("데이터 없음 (해당 월에 등록된 거래가 없습니다)")
    else:
        rows = [
            ["총 수입", won(s.income)],
            ["총 지출", won(s.expense)],
            ["잔액", won(s.balance)],
        ]
        width = max(display_width(r[1]) for r in rows)
        for label, value in rows:
            lines.append(f"{_pad(label, 8, 'left')}: {_pad(value, width, 'right')}")

    if s.budget is not None:
        rate = s.usage_rate or 0.0
        lines.append(f"예산: {won(s.budget)} (사용률 {rate:.1f}%)")
        if s.over_amount > 0:
            lines.append(f"[경고] 예산을 {won(s.over_amount)} 초과했습니다!")
        elif rate >= 80:
            lines.append("[주의] 예산의 80% 이상을 사용했습니다.")
    else:
        lines.append("예산: 미설정 (budget set --month YYYY-MM --amount 금액)")

    if s.count > 0:
        lines.append("")
        lines.append(f"지출 TOP {len(s.top_categories)}" if s.top_categories else "지출 내역 없음")
        for rank, (category, amount) in enumerate(s.top_categories, start=1):
            lines.append(f"{rank}) {category} {won(amount)}")

    return "\n".join(lines)
