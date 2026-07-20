# 파일 기반 가계부 콘솔 프로그램 만들기

Python 표준 라이브러리만 사용한 파일 기반 가계부 CLI 프로그램입니다.

## 1. 실행 방법

```bash
python3 -m budget_app <command> [options]
```

- Python 3.10 이상 필요, 외부 라이브러리 설치 불필요
- 모든 명령은 `--help` 로 사용법을 확인할 수 있습니다.
  - 예: `python3 -m budget_app add --help`
- 데이터 저장 폴더는 기본적으로 `./data` 이며, `--data-dir` 옵션으로 변경할 수 있습니다.
  - 예: `python3 -m budget_app --data-dir ./mydata list`

## 2. 저장 파일 위치 / 형식

저장 포맷은 **JSONL** 이며, 데이터는 아래 3개 파일로 분리 저장됩니다 (기본 폴더 `./data`).

| 파일 | 내용 |
| --- | --- |
| `data/transactions.jsonl` | 거래 내역 (한 줄 = 거래 1건의 JSON) |
| `data/categories.jsonl` | 카테고리 목록 |
| `data/budgets.jsonl` | 월별 예산 |

- 프로그램을 처음 실행하면 위 파일이 없을 경우 자동으로 생성되고, 카테고리가 비어 있으면 기본 카테고리(`food, transport, rent, etc`)가 자동으로 채워집니다.
- 거래 수정(update)/삭제(delete)는 전체 내용을 임시 파일에 다시 쓴 뒤 `os.replace()`로 원자적으로 교체하는 방식으로 처리되어, 도중에 오류가 발생해도 기존 파일이 깨지지 않습니다.
- 목록 조회(list)/검색(search)은 파일을 한 번에 메모리에 올리지 않고 제너레이터로 한 줄씩 읽어 처리합니다.

## 3. 데이터 모델

거래(Transaction)는 다음 필드를 가집니다.

- `id` (예: `TX-000001`, 유일)
- `type` (`income` 또는 `expense`)
- `date` (`YYYY-MM-DD`)
- `amount` (양수 정수)
- `category` (등록된 카테고리 중 하나)
- `memo` (선택)
- `tags` (선택, 목록)

## 4. 주요 명령 예시

### 거래 추가 (add, 대화형)

```bash
$ python3 -m budget_app add
날짜(YYYY-MM-DD): 2024-01-15
타입(income/expense): expense
카테고리: food
금액(양수): 15000
메모(선택): 점심
태그(쉼표로 구분, 없으면 엔터): meal
[저장 완료] id=TX-000012
```

### 목록 조회 (list)

```bash
$ python3 -m budget_app list --limit 3
TX-000012 | 2024-01-15 | expense | food | 15000 | 점심
TX-000011 | 2024-01-14 | income | salary | 3000000 |
TX-000010 | 2024-01-12 | expense | transport | 20000 |
```

### 검색 (search)

```bash
python3 -m budget_app search --from 2024-01-01 --to 2024-01-31 --category food --type expense --q 점심 --tag meal
```

### 월별 요약 + 예산 (summary, budget)

```bash
$ python3 -m budget_app budget set --month 2024-01 --amount 500000
[저장 완료] 2024-01 예산 500000원

$ python3 -m budget_app summary --month 2024-01 --top 3
총 수입: 3000000원
총 지출: 215000원
잔액: 2785000원
예산: 500000원 (사용률 43.0%)
지출 TOP 3
1) rent 150000원
2) food 45000원
3) transport 20000원
```

### 카테고리 관리 (category)

```bash
$ python3 -m budget_app category add
카테고리명: food
[저장 완료] category=food

$ python3 -m budget_app category list
- food
- transport

$ python3 -m budget_app category remove --name food
```
사용 중인(거래가 존재하는) 카테고리는 삭제할 수 없으며, 오류 메시지가 출력됩니다.

### 거래 수정 / 삭제 (update, delete)

update는 **옵션 인자 방식**으로 고정합니다 (대화형 방식은 지원하지 않음).

```bash
python3 -m budget_app update --id TX-000012 --amount 16000 --memo "점심(수정)"
python3 -m budget_app delete --id TX-000012
```

### 가져오기 / 내보내기 (import, export)

```bash
$ python3 -m budget_app export --out export.csv --month 2024-01
[완료] export.csv (12 records)

$ python3 -m budget_app import --from import.csv
[완료] imported=5, skipped=0
```

export는 `--month YYYY-MM` 또는 `--from/--to` 중 하나 이상을 반드시 지정해야 합니다.

#### CSV 스키마 (import/export 공통)

| column | required | 설명 |
| --- | --- | --- |
| date | Y | YYYY-MM-DD |
| type | Y | income / expense |
| category | Y | 등록된 카테고리 |
| amount | Y | 양수 정수 |
| memo | N | 문자열 |
| tags | N | 쉼표(,) 구분 문자열 |

공통: UTF-8 인코딩, 헤더 포함.

### 백업 (bonus)

```bash
python3 -m budget_app backup
```
`data/backup/<타임스탬프>/` 폴더에 3개 데이터 파일의 스냅샷을 생성합니다.

## 5. 오류 처리

모든 오류는 스택트레이스 없이 `[오류] 원인` + `[힌트] 해결 방법` 형태로 출력되며, 정상 종료는 exit code 0, 오류 종료는 0이 아닌 코드(1)로 종료합니다.

```bash
$ python3 -m budget_app add
날짜(YYYY-MM-DD): 2024-13-40
[오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
[힌트] 예: 2024-01-15
```

## 6. 구조 (모듈화)

| 모듈 | 책임 |
| --- | --- |
| `models.py` | 데이터 모델(`Transaction`)과 공통 예외 정의 |
| `validators.py` | 입력 값 검증 |
| `decorators.py` | 공통 관심사 분리 (`log_call`, `measure_time`, `handle_errors`) |
| `storage.py` | 파일 I/O 저장소 계층 (`TransactionRepository`, `CategoryStore`, `BudgetStore`) — 제너레이터 스트리밍 + 원자적 갱신 |
| `service.py` | 비즈니스 로직 (`BudgetService`) |
| `cli.py` | argparse 기반 명령어 파싱 + 대화형 입력 처리 |
| `utils.py` | 출력 포맷 등 공통 유틸 |
| `__main__.py` | `python -m budget_app` 진입점 |
