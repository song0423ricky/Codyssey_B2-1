"""공통 관심사(로그, 실행 시간 측정, 예외 처리)를 분리한 데코레이터 모음

- @log_execution : 명령 함수의 시작/종료와 실행 시간을 로그로 남긴다 (--verbose 시 표시)
- @handle_errors : 모든 오류를 스택트레이스 없이 '원인 + 힌트'로 출력하고 종료 코드를 정한다
"""
import functools
import logging
import sys
import time
from collections.abc import Callable
from typing import ParamSpec, TextIO, TypeVar

from .errors import BudgetAppError

P = ParamSpec("P")
R = TypeVar("R")

logger = logging.getLogger("budget_app")

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_UNEXPECTED = 3
EXIT_CANCELLED = 130


def print_error(message: str, hint: str = "", file: TextIO | None = None) -> None:
    out = file if file is not None else sys.stderr
    print(f"[오류] {message}", file=out)
    if hint:
        print(f"[힌트] {hint}", file=out)


def log_execution(func: Callable[P, R]) -> Callable[P, R]:
    """실행 로그 + 실행 시간 측정"""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        logger.debug("실행 시작: %s", func.__name__)
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            logger.debug("실행 종료: %s (%.4f초)", func.__name__, elapsed)

    return wrapper


def handle_errors(func: Callable[P, int]) -> Callable[P, int]:
    """예외를 잡아 친절한 메시지로 바꾸고, 0이 아닌 종료 코드를 돌려준다."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> int:
        try:
            return func(*args, **kwargs)
        except BudgetAppError as e:
            print_error(e.message, e.hint)
            return e.exit_code
        except (KeyboardInterrupt, EOFError):
            print("\n[취소] 입력이 중단되어 아무것도 저장하지 않았습니다.", file=sys.stderr)
            return EXIT_CANCELLED
        except OSError as e:
            target = e.filename or ""
            print_error(
                f"파일을 읽거나 쓸 수 없습니다: {target} ({e.strerror or e})",
                "경로가 맞는지, 다른 프로그램(엑셀 등)이 파일을 열고 있지 않은지, 쓰기 권한이 있는지 확인하세요.",
            )
            return EXIT_ERROR
        except Exception as e:  # 예상하지 못한 오류도 스택트레이스 없이 안내
            print_error(
                f"예상하지 못한 오류가 발생했습니다: {type(e).__name__}: {e}",
                "입력값과 data 폴더의 저장 파일을 확인하세요. 문제가 계속되면 backup 후 파일을 점검하세요.",
            )
            return EXIT_UNEXPECTED

    return wrapper
