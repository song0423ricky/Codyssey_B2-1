"""저장소 계층: JSONL 파일 읽기/쓰기만 담당한다 (검증·계산·출력 없음).

저장 파일 3개
- transactions.jsonl : 거래 내역 (한 줄에 거래 1건)
- categories.jsonl   : 카테고리 목록 (한 줄에 {"name": ...})
- budgets.jsonl      : 월 예산 (한 줄에 {"month": ..., "amount": ...})
"""
import json
import os
import shutil
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import DataFileError
from .models import Transaction

DEFAULT_CATEGORIES = ["food", "transport", "rent", "salary", "etc"]


class JsonlFile:
    """JSONL 파일 하나를 다루는 공통 도구 (세 저장소가 모두 사용)"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.created = False
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.touch()
            self.created = True

    def iter_records(self) -> Iterator[tuple[int, dict[str, Any]]]:
        """(줄 번호, 딕셔너리)를 한 줄씩 내보낸다. 파일 전체를 메모리에 올리지 않는다."""
        try:
            with self.path.open("r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        raise self.corrupted(line_no) from None
                    if not isinstance(record, dict):
                        raise self.corrupted(line_no)
                    yield line_no, record
        except UnicodeDecodeError:
            raise DataFileError(
                f"저장 파일을 UTF-8로 읽을 수 없습니다: {self.path}",
                "파일을 UTF-8 인코딩으로 다시 저장하거나 백업에서 복구하세요.",
            ) from None

    def corrupted(self, line_no: int) -> DataFileError:
        return DataFileError(
            f"저장 파일이 손상되었습니다: {self.path} ({line_no}번째 줄)",
            "해당 줄을 직접 고치거나 지우세요. backup으로 만든 백업이 있다면 그 파일로 복구할 수 있습니다.",
        )

    def append(self, record: dict[str, Any]) -> None:
        self.append_many([record])

    def append_many(self, records: Iterable[dict[str, Any]]) -> int:
        """파일 끝에 여러 줄을 덧붙이고 추가한 개수를 돌려준다."""
        count = 0
        with self.path.open("a", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
        return count

    def rewrite(self, records: Iterable[dict[str, Any]]) -> None:
        """원자적 저장: 임시 파일에 전부 쓴 뒤 os.replace로 한 번에 교체한다.

        쓰는 도중 프로그램이 멈춰도 원본 파일은 그대로 남는다.
        """
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as f:
                for record in records:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise


class TransactionRepository:
    """거래 내역 저장소"""

    FILE_NAME = "transactions.jsonl"

    def __init__(self, data_dir: Path) -> None:
        self._file = JsonlFile(data_dir / self.FILE_NAME)

    @property
    def path(self) -> Path:
        return self._file.path

    @property
    def created(self) -> bool:
        return self._file.created

    def iter_all(self) -> Iterator[Transaction]:
        """저장된 거래를 하나씩 내보내는 제너레이터 (스트리밍)"""
        for line_no, record in self._file.iter_records():
            try:
                tx = Transaction.from_dict(record)
            except (KeyError, TypeError, ValueError):
                raise self._file.corrupted(line_no) from None
            yield tx

    def find(self, tx_id: str) -> Transaction | None:
        for tx in self.iter_all():
            if tx.id == tx_id:
                return tx
        return None

    def max_number(self) -> int:
        """지금까지 쓰인 가장 큰 id 번호 (삭제로 번호가 비어도 재사용하지 않기 위함)"""
        max_num = 0
        for tx in self.iter_all():
            _, _, digits = tx.id.partition("-")
            if digits.isdigit():
                max_num = max(max_num, int(digits))
        return max_num

    def next_id(self) -> str:
        return f"TX-{self.max_number() + 1:06d}"

    def add(self, tx: Transaction) -> None:
        self._file.append(tx.to_dict())

    def add_many(self, txs: Iterable[Transaction]) -> int:
        return self._file.append_many(tx.to_dict() for tx in txs)

    def update(self, tx: Transaction) -> bool:
        """같은 id의 거래를 tx로 교체. 없으면 False"""
        return self._replace(tx.id, tx)

    def delete(self, tx_id: str) -> bool:
        """id의 거래를 삭제. 없으면 False"""
        return self._replace(tx_id, None)

    def _replace(self, tx_id: str, replacement: Transaction | None) -> bool:
        if self.find(tx_id) is None:
            return False

        def records() -> Iterator[dict[str, Any]]:
            # 원본을 한 줄씩 읽으면서 임시 파일에 한 줄씩 쓴다 (스트리밍 재작성)
            for tx in self.iter_all():
                if tx.id != tx_id:
                    yield tx.to_dict()
                elif replacement is not None:
                    yield replacement.to_dict()

        self._file.rewrite(records())
        return True


class CategoryStore:
    """카테고리 저장소. 파일이 비어 있으면 기본 카테고리를 자동 생성한다 (안 A)."""

    FILE_NAME = "categories.jsonl"

    def __init__(self, data_dir: Path) -> None:
        self._file = JsonlFile(data_dir / self.FILE_NAME)
        self.created_defaults = False
        if not self.list_all():
            self._write_all(DEFAULT_CATEGORIES)
            self.created_defaults = True

    @property
    def path(self) -> Path:
        return self._file.path

    @property
    def created(self) -> bool:
        return self._file.created

    def list_all(self) -> list[str]:
        """카테고리는 개수가 적은 설정 데이터라 한 번에 읽어도 된다."""
        names: list[str] = []
        for line_no, record in self._file.iter_records():
            name = record.get("name")
            if not isinstance(name, str) or not name:
                raise self._file.corrupted(line_no)
            names.append(name)
        return names

    def exists(self, name: str) -> bool:
        return name in self.list_all()

    def add(self, name: str) -> None:
        self._file.append({"name": name})

    def remove(self, name: str) -> None:
        self._write_all([n for n in self.list_all() if n != name])

    def _write_all(self, names: list[str]) -> None:
        self._file.rewrite({"name": n} for n in names)


class BudgetStore:
    """월 예산 저장소 (월별로 하나의 예산)"""

    FILE_NAME = "budgets.jsonl"

    def __init__(self, data_dir: Path) -> None:
        self._file = JsonlFile(data_dir / self.FILE_NAME)

    @property
    def path(self) -> Path:
        return self._file.path

    @property
    def created(self) -> bool:
        return self._file.created

    def all(self) -> dict[str, int]:
        budgets: dict[str, int] = {}
        for line_no, record in self._file.iter_records():
            try:
                budgets[str(record["month"])] = int(record["amount"])
            except (KeyError, TypeError, ValueError):
                raise self._file.corrupted(line_no) from None
        return budgets

    def get(self, month: str) -> int | None:
        return self.all().get(month)

    def set(self, month: str, amount: int) -> None:
        """같은 월이 이미 있으면 덮어쓴다 (원자적 재작성)"""
        budgets = self.all()
        budgets[month] = amount
        self._file.rewrite(
            {"month": m, "amount": a} for m, a in sorted(budgets.items())
        )


def backup_files(files: list[Path], backup_root: Path) -> Path:
    """타임스탬프 폴더를 만들고 저장 파일들을 복사한다. 만든 폴더 경로를 돌려준다."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = backup_root / stamp
    n = 1
    while dest.exists():                      # 같은 초에 두 번 실행한 경우
        dest = backup_root / f"{stamp}-{n}"
        n += 1
    dest.mkdir(parents=True)
    for src in files:
        shutil.copy2(src, dest / src.name)
    return dest
