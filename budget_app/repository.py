#페키지 -> 여러 개의 파이썬 모듈(파일)을 계층적인 디렉터리(폴더) 구조로 모아 놓은 묶음
#모듈(Module): 함수, 변수, 클래스 등을 담고 있는 하나의 파이썬(.py) 파일
#점(Dot, .) 연산자: 패키지명.모듈명 형태로 하위 모듈에 접근하여 사용

import json
from collections.abc import Iterator #collections.abc -> 자료구조의 **종류(형태)**를 정의해둔 모음" ,Iterator가 제너레이터처럼 값을 하나씩 꺼낼 수 있는 것을 의미하는데 이게 임포트 안하면 기본적으로 없어서 타입힌트 지정할떄 오류생김, 타입힌트도 실행은 되는 코드라 그럼
from pathlib import Path #파일 경로를 객체로 다루게 해주는 도구, data_dir / "transactions.jsonl"처럼 /로 경로를 이어 붙일 수 있음

from .models import Transaction #같은 패키지(.) 안의 models.py에서 Transaction 클래스를 가져오기, 거래 1건을 표현하는 클래스이고, to_dict()와 from_dict()를 가지고 있다고 가정한 코드.


class TransactionRepository:#거래를 파일에 저장하고 읽어오는 클래스
    def __init__(self, data_dir: Path) -> None:       #객체 만들떄 데이터 폴더 경로 받아서, 그 경로에 transactions.jsonl 파일이 없으면 만들어주는 생성자
        self.path = data_dir / "transactions.jsonl"   # data_dir 폴더 안의 transactions.jsonl 파일 경로를 만들어 파일경로를 self.path에 저장
        data_dir.mkdir(parents=True, exist_ok=True)   # data_dir 경로로 폴더 생성. parents=True → 상위 폴더 없으면 같이 만듦(경로에 적혀있는 이름대로), exist_ok=True → 이미 있어도 에러 안 냄
        self.path.touch(exist_ok=True)                # transactions.jsonl 파일이 없으면 빈 파일 생성 (나중에 읽을 때 "파일 없음" 에러 방지)

    def iter_all(self) -> Iterator[Transaction]: #파일을 한 줄씩 읽어서 Transaction을 하나씩 내보내는 제너레이터를 반환하는 메소드
        with self.path.open("r", encoding="utf-8") as f:          #파일을 읽기 모드("r")로 dufrh, with를 쓰면 블록이 끝날 때 파일이 자동으로 닫힘,utf-8은 한글이 깨지지 않게 하기 위함
            for line in f:                                        #한줄씩 읽기
                line = line.strip()                               #줄 앞뒤의 공백과 줄바꿈(\n)을 제거
                if line:                                          # 빈 문자열은 False로 취급되므로, 내용이 있는 줄만 처리, 빈 줄은 건너뜀
                    yield Transaction.from_dict(json.loads(line)) #제너레이터
                    """ 먼저 json.loads(line)이 문자열을 딕셔너리로 바꾸고, Transaction.from_dict(...)가 그 딕셔너리로 객체를 만든 뒤, 
                        yield가 그 객체를 하나 내보내고 대기."""

    def next_id(self) -> str:
        """지금까지 가장 큰 번호 + 1로 새 id를 만듦"""
        max_num = 0                         #지금까지 본 가장 큰 번호를 저장할 변수,거래가 하나도 없으면 0
        for tx in self.iter_all():          #위에서 만든 제너레이터로 모든 거래를 하나씩 꺼내기
            num = int(tx.id.split("-")[1])  # "TX-000012".split("-")는 ["TX", "000012"]가 되고, [1]로 "000012"를 꺼낸 뒤 int()로 숫자 12로 바꿈, ex) "TX-000012" → 12
            max_num = max(max_num, num)     #기존 최댓값과 비교해서 더 큰 값을 남김
        return f"TX-{max_num + 1:06d}"      #f-string으로 새 id를 만듬, :06d -> "정수를 6자리로, 빈자리는 0으로 채움"이라는 뜻이라 13이 000013이 되어 "TX-000013"이 됨

    def add(self, tx: Transaction) -> None: #거래 한건을 파일 맨 끝에 추가(한줄추가됨)
        with self.path.open("a", encoding="utf-8") as f:                 #"a"는 append 모드, 기존 내용을 지우지 않고 파일 끝에 이어씀
            f.write(json.dumps(tx.to_dict(), ensure_ascii=False) + "\n") 
            """ tx.to_dict()가 객체를 딕셔너리로 바꾸고, json.dumps(...)가 딕셔너리를 JSON 문자열로 바꿈
                ensure_ascii=False를 주면 한글이 \uc2dd 같은 코드 대신 "식비"처럼 그대로 저장됨
                마지막으로 + "\n"으로 줄바꿈을 붙여서 한 줄에 거래 하나가 되게 함"""