import argparse               #터미널 명령어 인자 해석 표준 터미널
from datetime import datetime #날짜 형식이 맞는지 검사하는 데 사용
from pathlib import Path      #경로호출 클래스

from .models import Transaction                #거래 1건 클래스
from .repository import TransactionRepository  #저장소 클래스
from .service import latest  #????

def ask_date() -> str:                            #날짜 확인
    while True:
        raw = input("날짜(YYYY-MM-DD): ").strip() #입력받기
        try:
           parsed = datetime.strptime(raw, "%Y-%m-%d")
        except ValueError:                                              #형식 틀리면
            print("[오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).")  #오류출력후 재시도
            print("[힌트] 예: 2004-04-23")
            continue
        return parsed.strftime("%Y-%m-%d")


def ask_type() -> str: #income,expense 판단
    while True:
        raw = input("타입(income/expense): ").strip().lower()    #소문자로 바꿔서 income,expense 판단
        if raw in ("income", "expense"):                         #둘중 하나면 반환
            return raw
        print("[오류] income 또는 expense만 입력할 수 있습니다.") #아니면 오류후 재입력


def ask_category() -> str:                #카테고리 입력
    while True:
        raw = input("카테고리: ").strip() 
        if raw:                               #뭐라도 입력하면 통과
            return raw
        print("[오류] 카테고리를 입력하세요.") #아니면 재입력


def ask_amount() -> int:                    #금액 입력
    while True:
        raw = input("금액(양수): ").strip() #금액 입력받기
        try:
            amount = int(raw)              #int로 바꿔보기
        except ValueError:                 #안되면 0
            amount = 0
        if amount > 0:                     #0이 아니면(오류가 아니면) 반환
            return amount
        print("[오류] 금액은 0보다 큰 정수여야 합니다.") #0이면 int변환 안되거나 amount<=0 임으로 오류 출력
        print("[힌트] 예: 15000 (쉼표 없이)")


def ask_tags() -> list[str]:                                #태그 입력
    raw = input("태그(쉼표로 구분, 없으면 엔터): ")         
    return [t.strip() for t in raw.split(",") if t.strip()] #리스트 컴프리헨션으로 쉼표 기준으로 자르고 공백 빼고 내용이 있으면 공백 뺀 값을 추가해서 리스트로 리턴

def positive_int(value: str) -> int: #????
    """argparse용: 옵션 값이 양의 정수인지 검사"""
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"양의 정수를 입력하세요 (입력값: {value})")
    if n <= 0:
        raise argparse.ArgumentTypeError(f"1 이상이어야 합니다 (입력값: {value})")
    return n


def format_tx(tx: Transaction) -> str:#???
    """거래 한 건을 한 줄 문자열로"""
    return f"{tx.id} | {tx.date} | {tx.type:<7} | {tx.category} | {tx.amount} | {tx.memo}"

# ---------- 명령 ----------

def cmd_add(repo: TransactionRepository) -> int: #main()에서 호출되는 add 명령 처리 함수, repo는 TransactionRepository 객체
    date = ask_date()
    tx_type = ask_type()
    category = ask_category()
    amount = ask_amount()
    memo = input("메모(선택): ").strip() #메모는 선택사항이라 검사없이 넣기, 비정상 입력 시 프로그램이 죽지 않아야 하면 수정
    tags = ask_tags()

    tx = Transaction(      #받은 값들로 Transaction 객체 생성
        id=repo.next_id(),
        type=tx_type,
        date=date,
        amount=amount,
        category=category,
        memo=memo,
        tags=tags,
    )
    repo.add(tx)#완성된 거래 객체를 저장소의 add()에 넘겨서 transactions.jsonl 파일 끝에 한 줄로 저장
    print(f"[저장 완료] id={tx.id}")
    return 0 #0 반환해서 끝내기 

def cmd_list(repo: TransactionRepository, limit: int) -> int:#????
    rows = latest(repo.iter_all(), limit)
    if not rows:
        print("거래 내역이 없습니다.")
        print("[힌트] add 명령으로 거래를 먼저 추가하세요: py -m budget_app add")
        return 0
    for tx in rows:
        print(format_tx(tx))
    return 0

# ---------- 명령어 해석 ----------

def build_parser() -> argparse.ArgumentParser: #터미널에 입력한 명령어를 어떻게 해석할지 규칙을 정하기
    parser = argparse.ArgumentParser(          #명령어 해석기 객체를 만들어 parser에 저장합니다. 괄호 안에 설정값을 넣음
        prog="budget_app",                     #프로그램 이름을 budget_app으로 정함,도움말이나 오류 메시지에 이 이름이 표시됨
        description="용돈 기입장 콘솔 프로그램", # --help를 입력하면 보이는 프로그램 설명
    )
    parser.add_argument("--data-dir", default="./data",         # --data-dir이라는 옵션을 등록, -- ->  넣어도 되고 안 넣어도 되는 선택 옵션, default="./data" ->  옵션을 안 넣었을 때 쓰는 기본값
                        help="데이터 저장 폴더 (기본값: ./data)")

    sub = parser.add_subparsers(dest="command", required=True) #하위 명령어를 넣을 공간을 만들어 sub에 저장,dest="command" -> 입력된 명령어 이름을 args.command에 저장, required=True -> 명령어를 꼭 입력해야 한다는 뜻
    sub.add_parser("add", help="거래 추가 (대화형 입력)")       #add라는 하위 명령어를 등록,사용자가 add를 입력하면 args.command에 "add"가 들어감

    p_list = sub.add_parser("list", help="거래 목록 (최신순)")#?????
    p_list.add_argument("--limit", type=positive_int, default=10,
                        help="출력할 최대 개수 (기본값: 10)")
    return parser #설정이 끝난 해석기 반환, 실제 해석은 main의 parser.parse_args(argv)에서함


def main(argv: list[str] | None = None) -> int:  
    """ argv->"argument vector"의 줄임말로, 명령어 뒤에 붙은 단어들의 목록을 뜻하는 전통적인 이름
        list[str] | None**, 타입 힌트로, "문자열 리스트이거나 None"이라는 뜻, | ->"또는" 이라는 뜻
        __main__.py에서는 main()을 인자 없이 부름으로 평소엔 첫 번째 방식으로 동작, 두 번째는 나중에 터미널을 안 거치고 코드로 직접 테스트하고 싶을 때사용 
        ~ -> int 는 이 값이 __main__.py의 sys.exit(main())으로 넘어가서 운영체제에 전달된다는뜻"""
    
    parser = build_parser()                          #이 프로그램은 --data-dir 옵션이 있고, add라는 명령이 있다" 같은 규칙을 등록한 argparse 객체를 돌려줌,아직 사용자 입력을 읽은 건 아니고, 규칙표만 만든 상태
    args = parser.parse_args(argv)                   #규칙표를 가지고 실제 입력을 해석하는 줄, argv가 None이면 argparse가 알아서 터미널에 입력된 내용(sys.argv[1:])을 가져다 사용, 리스트가 들어오면 그걸 해석, 결과로 나오는 args는 해석 결과를 담은 상자예요. 점(.)으로 꺼내 사용
    repo = TransactionRepository(Path(args.data_dir))# 해석된 폴더 경로(기본값 ./data)를 Path로 감싸 저장소 생성. 이때 폴더와 transactions.jsonl 파일이 없으면 만들어짐


    if args.command == "add": # 입력된 명령어가 add면
        return cmd_add(repo)  #거래 추가 실행하고, 그 결과(성공 시 0)를 그대로 돌려줌
    if args.command == "list": #????
        return cmd_list(repo, args.limit)
    return 1                  # 처리할 수 없는 명령어면 1(실패) 반환