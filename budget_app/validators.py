"""입력 검증: 문자열을 받아 올바른 값으로 변환하거나 ValidationError를 발생시킨다.

대화형 입력, 옵션 인자, CSV import가 모두 같은 규칙을 쓰도록 한 곳에 모았다.
"""
import re
from datetime import datetime

from .errors import ValidationError

VALID_TYPES = ("income", "expense")
_TX_ID_PATTERN = re.compile(r"^TX-\d+$")


def parse_date(value: str) -> str:
    """'2024-1-5' 같은 입력도 받아서 항상 '2024-01-05' 형식으로 정규화한다."""
    raw = value.strip()
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        raise ValidationError(
            f"날짜 형식이 올바르지 않습니다 (YYYY-MM-DD): '{raw}'",
            "예: 2024-01-15 (존재하는 날짜여야 합니다)",
        ) from None
    return parsed.strftime("%Y-%m-%d")


def parse_month(value: str) -> str:
    """'2024-1' 같은 입력도 받아서 항상 '2024-01' 형식으로 정규화한다."""
    raw = value.strip()
    try:
        parsed = datetime.strptime(raw, "%Y-%m")
    except ValueError:
        raise ValidationError(
            f"월 형식이 올바르지 않습니다 (YYYY-MM): '{raw}'",
            "예: 2024-01",
        ) from None
    return parsed.strftime("%Y-%m")


def parse_type(value: str) -> str:
    raw = value.strip().lower()
    if raw not in VALID_TYPES:
        raise ValidationError(
            f"허용되지 않은 타입입니다: '{value.strip()}'",
            "income(수입) 또는 expense(지출) 중 하나를 입력하세요.",
        )
    return raw


def parse_amount(value: str) -> int:
    """양의 정수만 허용한다. 음수, 0, 소수, 쉼표(15,000)는 거부한다."""
    raw = value.strip()
    if not (raw.isascii() and raw.isdigit()) or int(raw) <= 0:
        raise ValidationError(
            f"금액은 0보다 큰 정수여야 합니다: '{raw}'",
            "예: 15000 (쉼표, 소수점, 음수 불가)",
        )
    return int(raw)


def parse_category_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise ValidationError("카테고리명이 비어 있습니다.", "예: food")
    if len(name) > 30:
        raise ValidationError("카테고리명은 30자 이하여야 합니다.", "짧은 이름을 사용하세요. 예: food")
    return name


def parse_tags(value: str) -> list[str]:
    """'meal, lunch,,meal' -> ['meal', 'lunch'] (공백 제거, 빈 값·중복 제거)"""
    tags = [t.strip() for t in value.split(",") if t.strip()]
    return list(dict.fromkeys(tags))


def parse_tx_id(value: str) -> str:
    """'tx-000012'는 대문자로, 숫자만 입력한 '12'는 'TX-000012'로 바꿔준다."""
    raw = value.strip().upper()
    if raw.isdigit():
        raw = f"TX-{int(raw):06d}"
    if not _TX_ID_PATTERN.match(raw):
        raise ValidationError(
            f"거래 id 형식이 올바르지 않습니다: '{value.strip()}'",
            "예: TX-000012 (id는 list 또는 search로 확인할 수 있습니다)",
        )
    return raw
