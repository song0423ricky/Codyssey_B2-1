import sys #종료 코드를 운영체제에 넘기는 sys.exit()를 쓰려고 가져옴 -> 원할떄 0반환후 종료


def main() -> int: #리턴타입 int
    print("용돈 기입장 프로그램입니다.")
    return 0 #정상 종료일떄 0 리턴


if __name__ == "__main__":#파이썬은 직접 실행하면 __name__ 에 "__main__"이 들어가고, 다른 파일에서 import하면 __name__에 import한 모듈이름이 들어감
    sys.exit(main())      #main()을 실행하고, 돌려받은 숫자(0)를 종료 코드로 삼아 프로그램을 끝냅니다.