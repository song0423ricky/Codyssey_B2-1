from dataclasses import dataclass, field, asdict #dataclass: 데이터 클래스 데코레이터, field: 필드 정의, asdict: 데이터 클래스 인스턴스를 딕셔너리로 변환하는 함수


@dataclass #데코레이터 
class Transaction:# 거래 1건을 표현하는데이터 클래스 
    id: str
    type: str          # "income" 또는 "expense"
    date: str          # "YYYY-MM-DD"
    amount: int
    category: str
    memo: str = ""     #기본값이 있는 필드는 반드시 기본값 없는 필드보다 뒤에 와야 에러안남.
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict: #객체를 딕셔너리로 바꾸기, JSON은 딕셔너리만 저장가능.
        return asdict(self) #asdict -> 데이터 클래스(dataclass) 인스턴스를 딕셔너리(dictionary)로 변환하는 표준 라이브러리 함수

    @classmethod #메서드를 클래스 이름으로 직접 부를 수 있고, 첫 번째 인자로 객체 대신 클래스 자신호출
    def from_dict(cls, data: dict) -> "Transaction": #cls = 클래스자체를 첫 번째 매개변수로 전달받기 위해 사용하는 관례적인 이름,self느낌인데 여기서는 Transaction클래스임
        """from_dict는 파일에서 딕셔너리 데이터 가져와야되서 to_dict과 다르게 객체가 부르는 시점에 없음
        -> 그래서 클래스 메서드로 정의하고, 첫 번째 매개변수로 cls를 받음, 즉 Transaction클래스를 객체느낌으로 사용"""
        return cls(**data) 
        """ data가 딕셔너리 형태임으로 **으로 딕셔너리를 "키=값" 형태로 풀어서 함수에 넣음
        -> **data = {id="TX-000001", type="expense", date="2024-01-15",amount=15000, category="food", memo="점심", tags=["meal"]}"""