# 용돈 기입장 (budget_app)

파일 기반(JSONL)으로 수입/지출을 기록하는 Python 콘솔 가계부입니다.
거래 추가·목록·검색·수정·삭제, 월별 요약, 예산 경고, 카테고리 관리, CSV 가져오기/내보내기, 백업을 지원합니다.

- Python 3.10 이상, **표준 라이브러리만 사용** (pip install 불필요)
- 파일을 한 번에 읽지 않고 **제너레이터로 스트리밍 처리**
- 공통 관심사(예외 처리, 실행 로그/시간 측정)는 **데코레이터로 분리**
- 모든 함수·데이터 구조에 **타입 힌트** 적용

---

## 1. 실행 방법

프로젝트 폴더(`budget_app` 폴더가 보이는 위치)에서 실행합니다.

```bash
python -m budget_app <command> [options]
python -m budget_app --help            # 전체 명령 목록
python -m budget_app <command> --help  # 명령별 사용법
```

> Windows에서 `python`이 동작하지 않으면 `py -m budget_app ...`으로 실행하세요.

### 전역 옵션 (명령 이름보다 **앞**에 씁니다)

| 옵션 | 설명 |
|---|---|
| `--data-dir <경로>` | 저장 폴더 변경 (기본값 `./data`) |
| `--verbose` | 실행 로그와 실행 시간 출력 |
| `--version` | 버전 출력 |

```bash
python -m budget_app --data-dir ./mydata list
python -m budget_app --verbose summary --month 2024-01
```

---

## 2. 저장 파일 위치와 형식

기본 위치는 `./data/`이며, **JSONL**(한 줄에 JSON 객체 하나) 형식으로 3개 파일에 나누어 저장합니다.

| 파일 | 내용 | 한 줄 예시 |
|---|---|---|
| `transactions.jsonl` | 거래 내역 | `{"id": "TX-000001", "type": "expense", "date": "2024-01-15", "amount": 15000, "category": "food", "memo": "점심", "tags": ["meal"]}` |
| `categories.jsonl` | 카테고리 목록 | `{"name": "food"}` |
| `budgets.jsonl` | 월 예산 | `{"month": "2024-01", "amount": 500000}` |

### 초기 실행

- 저장 폴더/파일이 없으면 **자동 생성**하고 안내 메시지를 출력합니다.
- 카테고리 파일이 비어 있으면 **기본 카테고리를 자동 등록**합니다 (안 A): `food, transport, rent, salary, etc`

### 거래(Transaction) 필드

| 필드 | 설명 |
|---|---|
| `id` | `TX-000001` 형식, 자동 생성 (삭제된 번호는 재사용하지 않음) |
| `type` | `income` 또는 `expense` |
| `date` | `YYYY-MM-DD` (`2024-1-5`로 입력해도 `2024-01-05`로 저장) |
| `amount` | 양의 정수 |
| `category` | 등록된 카테고리만 허용 |
| `memo` | 선택 |
| `tags` | 선택, 여러 개 가능 |

---

## 3. 주요 명령 예시

### 거래 추가 (대화형)

```text
$ python -m budget_app add
새 거래를 입력하세요. (중단: Ctrl+C)
날짜(YYYY-MM-DD): 2024-01-15
타입(income/expense): expense
  등록된 카테고리: food, transport, rent, salary, etc
카테고리: food
금액(양수): 15000
메모(선택): 점심
태그(쉼표로 구분, 없으면 엔터): meal
[저장 완료] id=TX-000001
```

잘못된 값(없는 날짜, 음수/0 금액, 허용되지 않은 타입, 미등록 카테고리)은 오류와 힌트를 보여주고 **다시 입력**받습니다.

### 목록 / 검색 (날짜 최신순)

```bash
python -m budget_app list                     # 기본 10건
python -m budget_app list --limit 5
python -m budget_app search --from 2024-01-01 --to 2024-01-31
python -m budget_app search --category food --type expense
python -m budget_app search --q 점심            # 메모 키워드 (대소문자 무시)
python -m budget_app search --tag meal --limit 50
```

- 검색 조건을 여러 개 쓰면 **모두 만족**(AND)하는 거래만 출력합니다.
- `search`의 `--limit` 기본값은 20이며, 전체 일치 건수를 함께 표시합니다.

### 월별 요약 + 예산

```text
$ python -m budget_app budget set --month 2024-01 --amount 500000
[저장 완료] 2024-01 예산 500,000원

$ python -m budget_app summary --month 2024-01 --top 3
[2024-01 월별 요약]
총 수입 : 3,000,000원
총 지출 :   215,000원
잔액    : 2,785,000원
예산: 500,000원 (사용률 43.0%)

지출 TOP 3
1) rent 150,000원
2) food 45,000원
3) transport 20,000원
```

- 예산 초과 시 `[경고] 예산을 N원 초과했습니다!`, 80% 이상이면 `[주의]`를 출력합니다.
- 거래가 없는 달은 `데이터 없음`을 출력합니다.
- `budget show [--month YYYY-MM]`로 예산을 조회합니다 (월 생략 시 전체).

### 카테고리 관리

```bash
python -m budget_app category list
python -m budget_app category add               # 대화형
python -m budget_app category add --name cafe   # 옵션
python -m budget_app category remove --name cafe
```

- **사용 중인 카테고리는 삭제를 막습니다.** 사용 건수와 함께 해결 방법(update로 카테고리 변경 또는 delete)을 안내합니다.
- 중복 등록은 오류로 처리합니다.

### 거래 수정 / 삭제

**update는 옵션 방식(안 A)으로 고정**했습니다. 지정한 필드만 바뀝니다.

```bash
python -m budget_app update --id TX-000001 --amount 20000 --memo 저녁
python -m budget_app update --id TX-000001 --category transport --tags "bus,work"
python -m budget_app update --id TX-000001 --memo ""       # 메모 비우기
python -m budget_app delete --id TX-000001
```

- 옵션: `--date --type --category --amount --memo --tags` (최소 1개 필요)
- id는 `TX-000001`, `tx-000001`, `1` 모두 같은 거래로 인식합니다.
- 없는 id는 `[오류] id=... 거래가 없습니다.`를 출력하고 종료 코드 1로 끝납니다.
- 수정/삭제는 **임시 파일에 쓴 뒤 `os.replace`로 교체**하여, 중간에 멈춰도 원본이 손상되지 않습니다.

### CSV 가져오기 / 내보내기

```text
$ python -m budget_app export --out export.csv --month 2024-01
[완료] export.csv (12 records)

$ python -m budget_app export --out q1.csv --from 2024-01-01 --to 2024-03-31

$ python -m budget_app import --from sample_import.csv
[완료] imported=5, skipped=3
  - 건너뜀 7행: 등록되지 않은 카테고리입니다: 'unknown'
  - 건너뜀 8행: 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD): '2024-13-01'
  - 건너뜀 9행: 금액은 0보다 큰 정수여야 합니다: '-500'
```

- `export`는 `--month` 또는 `--from`/`--to` 중 **하나 이상 필수**입니다. 같은 이름 파일은 덮어씁니다.
- `import`는 올바른 행만 새 id로 추가하고, 잘못된 행은 행 번호와 이유를 보여주고 건너뜁니다. 한 건도 가져오지 못하면 종료 코드 1입니다.
- 같은 CSV를 두 번 가져오면 거래가 중복 등록됩니다.

### 백업 (보너스)

```bash
python -m budget_app backup
# [완료] 백업 생성: data/backups/20240115-093000
```

복구는 백업 폴더의 파일 3개를 `data/`에 복사해 덮어쓰면 됩니다.

---

## 4. import / export CSV 스키마

UTF-8, 첫 줄 헤더 포함 (엑셀의 BOM이 있어도 읽을 수 있음)

| column | required | 설명 |
|---|---|---|
| `date` | Y | `YYYY-MM-DD` |
| `type` | Y | `income` / `expense` |
| `category` | Y | 등록된 카테고리 |
| `amount` | Y | 양수 정수 |
| `memo` | N | 문자열 |
| `tags` | N | 쉼표(`,`) 구분 문자열 (쉼표가 있으면 따옴표로 감쌈) |

```csv
date,type,category,amount,memo,tags
2024-01-03,income,salary,3000000,1월 월급,"monthly,work"
2024-01-07,expense,food,12000,점심 김밥,meal
```

`id`는 CSV에 포함하지 않으며, 가져올 때 새로 부여합니다. 예제 파일: `sample_import.csv`

---

## 5. 오류 처리와 종료 코드

오류는 스택트레이스 없이 **원인 + 해결 힌트**로 출력합니다.

```text
[오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD): '2024-13-40'
[힌트] 예: 2024-01-15 (존재하는 날짜여야 합니다)
```

| 종료 코드 | 의미 |
|---|---|
| 0 | 정상 종료 |
| 1 | 입력/데이터 오류 (없는 id, 미등록 카테고리, 파일 손상 등) |
| 2 | 명령어/옵션 사용법 오류 (argparse) |
| 3 | 예상하지 못한 오류 |
| 130 | 사용자가 입력 중 Ctrl+C로 취소 |

---

## 6. 프로젝트 구조와 설계

```
budget_app/
├── __main__.py     진입점 (python -m budget_app)
├── cli.py          CLI 계층: argparse, 대화형 입력, 화면 출력
├── service.py      서비스 계층: 검색·요약·예산·카테고리 규칙, CSV 처리 흐름
├── repository.py   저장소 계층: JSONL 파일 읽기/쓰기, 원자적 저장, 백업
├── csv_io.py       CSV 파일 입출력
├── models.py       모델 계층: Transaction, SearchFilter, MonthlySummary, ImportResult
├── validators.py   입력 검증 (대화형·옵션·CSV가 같은 규칙 사용)
├── decorators.py   @handle_errors, @log_execution
├── formatter.py    표 정렬 출력 (한글 폭 계산)
└── errors.py       오류 클래스 (메시지 + 힌트)
```

### 계층별 책임

| 계층 | 하는 일 | 모르는 것 |
|---|---|---|
| CLI | 입력을 받아 서비스 호출, 결과 출력 | 파일 형식 |
| 서비스 | 가계부 규칙과 계산 | 화면 출력, 파일 형식 |
| 저장소 | 파일 읽기/쓰기 | 규칙, 화면 |
| 모델 | 데이터의 모양 | 나머지 전부 |

저장소가 항상 `Transaction` 객체를 돌려주기 때문에, 저장 형식을 CSV 등으로 바꿔도 서비스와 CLI는 수정할 필요가 없습니다.

### 제너레이터 스트리밍

- `TransactionRepository.iter_all()`은 파일을 한 줄씩 읽어 `yield`로 거래를 하나씩 내보냅니다.
- `list`/`search`는 `heapq.nlargest(limit, 제너레이터, key=(date, id))`로 **상위 N개만 유지**하며 날짜 최신순을 고릅니다. 파일은 입력 순서로 쌓이지만 최신순은 날짜 기준이어야 하기 때문입니다. 메모리 사용량은 파일 크기가 아니라 `--limit`에 비례합니다.
- `summary`는 한 줄씩 읽으며 합계만 누적하고, `update`/`delete`는 원본을 한 줄씩 읽으면서 임시 파일에 한 줄씩 씁니다.
- 카테고리/예산은 개수가 적은 설정 데이터라 한 번에 읽습니다.

### 데코레이터

- `@handle_errors` (`run`에 적용): 모든 예외를 잡아 `[오류]/[힌트]`로 출력하고 종료 코드를 정합니다. 각 명령 함수에 `try/except`를 반복하지 않아도 됩니다.
- `@log_execution` (모든 `cmd_*`에 적용): 실행 시작/종료와 실행 시간을 기록합니다. `--verbose`일 때만 표시됩니다.

### 타입 힌트

예: `TransactionRepository.find(tx_id: str) -> Transaction | None`
반환 타입에 `None`이 명시되어 있어 호출하는 쪽(`BudgetService.get_transaction`)이 "없는 id" 처리를 빠뜨리지 않게 되고, 에디터가 누락을 경고해 줍니다.

---

## 7. 보너스 과제 구현 여부

| 항목 | 구현 |
|---|---|
| 백업 기능 (`backup`) | O |
| 출력 포맷 테이블 정렬 (외부 라이브러리 없이, 한글 폭 계산) | O |
| 저장 원자성 강화 (임시 파일 + `os.replace`) | O |
| 반복 내역 기능 | X |
