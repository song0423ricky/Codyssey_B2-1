"""CSV 가져오기/내보내기 파일 입출력 (import/export 전용)

CSV 스키마 (UTF-8, 헤더 포함)
    date,type,category,amount,memo,tags
"""
import csv
from collections.abc import Iterable, Iterator
from pathlib import Path

from .errors import DataFileError
from .models import Transaction

CSV_COLUMNS = ["date", "type", "category", "amount", "memo", "tags"]
REQUIRED_COLUMNS = ["date", "type", "category", "amount"]


def iter_csv_rows(path: Path) -> Iterator[tuple[int, dict[str, str]]]:
    """(줄 번호, 행 딕셔너리)를 한 줄씩 내보낸다. 헤더 검사도 여기서 한다."""
    if not path.is_file():
        raise DataFileError(
            f"가져올 CSV 파일을 찾을 수 없습니다: {path}",
            "파일 경로를 확인하세요. 상대 경로는 현재 터미널 위치 기준입니다.",
        )
    try:
        # utf-8-sig: 엑셀이 붙이는 BOM이 있어도 헤더가 깨지지 않게 한다
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise DataFileError(
                    f"CSV 파일이 비어 있습니다: {path}",
                    f"첫 줄에 헤더가 있어야 합니다: {','.join(CSV_COLUMNS)}",
                )
            reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]
            missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
            if missing:
                raise DataFileError(
                    f"CSV 헤더에 필수 컬럼이 없습니다: {', '.join(missing)}",
                    f"헤더 예시: {','.join(CSV_COLUMNS)}",
                )
            for row in reader:
                clean = {k: (v or "").strip() for k, v in row.items() if k is not None}
                yield reader.line_num, clean
    except UnicodeDecodeError:
        raise DataFileError(
            f"CSV 파일을 UTF-8로 읽을 수 없습니다: {path}",
            "엑셀에서 'CSV UTF-8(쉼표로 분리)' 형식으로 다시 저장하세요.",
        ) from None
    except csv.Error as e:
        raise DataFileError(
            f"CSV 형식이 올바르지 않습니다: {e}",
            "따옴표가 짝이 맞는지 확인하세요.",
        ) from None


def write_csv(path: Path, txs: Iterable[Transaction]) -> int:
    """거래를 CSV로 저장하고 저장한 건수를 돌려준다 (같은 이름 파일은 덮어씀)."""
    if not path.parent.exists():
        raise DataFileError(
            f"저장할 폴더가 없습니다: {path.parent}",
            "폴더를 먼저 만들거나 --out 경로를 확인하세요.",
        )
    count = 0
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for tx in txs:
            writer.writerow({
                "date": tx.date,
                "type": tx.type,
                "category": tx.category,
                "amount": tx.amount,
                "memo": tx.memo,
                "tags": ",".join(tx.tags),
            })
            count += 1
    return count
