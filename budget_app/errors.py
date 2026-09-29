"""사용자에게 '원인 + 해결 힌트'로 보여줄 오류 종류 정의"""


class BudgetAppError(Exception):
    """이 프로그램에서 의도적으로 발생시키는 모든 오류의 부모 클래스"""

    exit_code: int = 1

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class ValidationError(BudgetAppError):
    """입력값 형식이 잘못됨 (날짜, 금액, 타입 등)"""


class NotFoundError(BudgetAppError):
    """존재하지 않는 데이터 (없는 id, 등록되지 않은 카테고리 등)"""


class ConflictError(BudgetAppError):
    """현재 상태와 충돌 (중복 등록, 사용 중인 카테고리 삭제 등)"""


class DataFileError(BudgetAppError):
    """저장 파일/CSV 파일 문제 (손상, 없음, 인코딩 오류 등)"""
