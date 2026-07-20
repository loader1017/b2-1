# 파일 기반 가계부 콘솔 프로그램

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

### 왜 JSONL을 선택했는가 (JSONL vs CSV)

과제에서 JSONL/CSV 중 하나를 고르라고 했는데, JSONL을 선택했습니다.

| 기준 | JSONL | CSV |
| --- | --- | --- |
| 레코드 단위 append | O (한 줄 추가로 끝) | O (동일) |
| 스키마 유연성 | O (`tags`처럼 리스트/선택 필드를 자연스럽게 표현) | X (모든 값을 문자열로 펼쳐야 함, 쉼표 포함 값 이스케이프 필요) |
| 한 줄 = 한 레코드 → 스트리밍 파싱 | O (`json.loads`를 줄 단위로) | O (`csv.reader`도 줄 단위 가능) |
| 타입 보존 | O (숫자/문자열 구분이 파일에 그대로 남음) | X (전부 문자열, 매번 형변환 필요) |
| 사람이 눈으로 훑어보기 | 보통 | 좋음(엑셀로 바로 열림) |

`tags`(선택, 목록)처럼 있을 때도 있고 없을 때도 있는 필드, 그리고 값에 쉼표가 섞일 수 있는 `memo`를 다룰 때 JSONL이 더 안전합니다. CSV는 대신 "사람이 엑셀로 바로 열어본다"는 데 강점이 있어서, **내부 저장은 JSONL, 사람이 보거나 외부로 주고받는 용도(import/export)는 CSV**로 역할을 나눴습니다.

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

#### import 부분 실패 정책

CSV의 각 행을 먼저 전부 검증만 하고, 그 다음에만 실제로 파일에 씁니다(검증 → 커밋 순서). 그래서 "쓰다가 중간에 실패해서 일부만 이상하게 반영되는" 상황 자체가 생기지 않습니다.

- **기본 동작**: 유효한 행만 저장하고, 실패한 행은 몇 번째 행인지 + 왜 실패했는지 알려줍니다.
  ```bash
  $ python3 -m budget_app import --from mixed.csv
  [완료] imported=2, skipped=2
    [스킵] 행 3: 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
    [스킵] 행 4: 등록되지 않은 카테고리입니다: 'ghost'
  ```
- **`--strict` 옵션**: 단 한 행이라도 검증에 실패하면 아무것도 저장하지 않고 전체를 취소합니다(all-or-nothing).
  ```bash
  $ python3 -m budget_app import --from mixed.csv --strict
  [오류] 2건의 행에서 오류가 발견되어 가져오기를 중단했습니다 (아무 것도 저장되지 않음).
  [힌트] 예: 행 3 - 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
  ```

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

## 5. 대용량(10만 건 이상) 환경에서의 병목과 개선

거래가 10만 건까지 쌓인다고 가정했을 때 느려지는 지점과, 실제로 반영한/앞으로 필요한 개선입니다.

| 지점 | 문제 | 상태 |
| --- | --- | --- |
| `add` (id 발급) | 예전 구현은 새 id를 만들 때마다 파일 전체를 처음부터 끝까지 읽어 최댓값을 찾음 → 거래를 n번 추가하면 총 비용이 O(n²) | **반영됨**: `transactions.jsonl.counter`에 마지막 id 번호만 저장해두고 1줄만 읽어 O(1)로 계산하도록 변경 |
| `list --limit N` | `sorted()`로 전체를 메모리에 올린 뒤 앞 N개만 자르면, N이 작아도 10만 건이 전부 메모리에 올라감 | **반영됨**: `heapq.nlargest(N, ...)`로 크기 N짜리 힙만 유지하도록 변경 (파일은 여전히 한 줄씩 스트리밍해서 읽음) |
| `search` (조건 검색) | 결과 건수가 미리 정해져 있지 않아 매칭되는 전체 행을 리스트로 모아 정렬함 → 매칭 결과 자체가 많으면 메모리 사용량이 큼 | **개선 여지 있음(미반영)**: `--limit` 옵션을 추가해 상한을 두거나, 날짜 조건이 있을 때는 인덱스 파일로 후보 범위를 먼저 좁히는 방식이 필요 |
| `update` / `delete` | 파일 전체를 다시 써야 함(원자적 교체를 위해 의도된 설계) → 매 수정/삭제가 O(n) | **알려진 트레이드오프**: 안전성(원자성)을 위해 의도적으로 선택. 더 빠르게 하려면 "id → 파일 내 byte 위치"를 담은 인덱스 파일을 별도로 유지해야 하는데, JSONL은 줄마다 길이가 달라 제자리 수정이 불가능해 구조 변경이 필요함 (예: 고정폭 레코드 또는 별도 인덱스+삭제 마킹 방식) |
| `summary` | 해당 월의 거래만 걸러내려고 매번 전체 파일을 훑음 | **개선 여지 있음(미반영)**: 월별로 파일을 쪼개거나(`transactions-2024-01.jsonl`), 월 시작 위치를 캐시하면 훑는 범위를 줄일 수 있음 |

정리하면, "쓰기 성능(id 발급)"과 "조회 성능(list)"은 이번에 실제로 고쳤고, "검색/수정삭제/월별요약"은 지금 구조에서도 정상 동작하지만 10만 건 이상 규모에서 더 빠르게 하려면 인덱스 파일 도입이 다음 단계로 필요합니다.

### 데코레이터별 출력 예시

세 데코레이터는 모두 표준 에러(stderr)로 로그를 남겨서, 콘솔에 보이는 실제 결과(stdout)와 로그가 섞이지 않습니다.

```
[LOG 2024-01-15 10:00:00] 'cmd_add' 실행 시작
[LOG 2024-01-15 10:00:00] 'cmd_add' 실행 종료
[TIME] 'cmd_add' 실행 시간: 0.0054초
```

오류가 나면 `handle_errors`가 원인/힌트를 표준 출력(stdout)으로 내보내고 `exit(1)`로 종료합니다.

## 6. 오류 처리

모든 오류는 스택트레이스 없이 `[오류] 원인` + `[힌트] 해결 방법` 형태로 출력되며, 정상 종료는 exit code 0, 오류 종료는 0이 아닌 코드(1)로 종료합니다.

```bash
$ python3 -m budget_app add
날짜(YYYY-MM-DD): 2024-13-40
[오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).
[힌트] 예: 2024-01-15
```

## 7. 구조 (모듈화)

| 모듈 | 책임 | 핵심 계약(입력 → 출력) |
| --- | --- | --- |
| `models.py` | 데이터 모델(`Transaction`)과 공통 예외, `SummaryResult`(요약 반환 스키마) 정의 | `Transaction.from_dict(dict) -> Transaction`, `Transaction.to_dict() -> dict` |
| `validators.py` | 입력 값 검증 | `validate_date(str) -> str`(실패 시 `ValidationError`), 나머지도 동일 패턴 |
| `decorators.py` | 공통 관심사 분리 (`log_call`, `measure_time`, `handle_errors`) | 함수를 감싸 그대로 반환하되, `handle_errors`는 예외 시 `sys.exit(1)` |
| `storage.py` | 파일 I/O 저장소 계층 (`TransactionRepository`, `CategoryStore`, `BudgetStore`) — 제너레이터 스트리밍 + 원자적 갱신, id 카운터 캐싱 | `iter_all() -> Generator[Transaction]`, `next_id() -> str`(O(1)), `update/delete(id) -> Transaction`(없으면 `NotFoundError`) |
| `service.py` | 비즈니스 로직 (`BudgetService`) — storage의 결과를 검증 규칙과 결합 | `summary(month, top) -> SummaryResult`, `import_csv(path, strict) -> {"imported", "skipped", "errors"}` |
| `cli.py` | argparse 기반 명령어 파싱 + 대화형 입력 처리 | 사용자 입력 → `BudgetService` 호출 → 콘솔 출력만 담당(로직 없음) |
| `utils.py` | 출력 포맷 등 공통 유틸 | `format_transaction_line(Transaction) -> str`, `parse_tags(str) -> List[str]` |
| `__main__.py` | `python -m budget_app` 진입점 | `cli.run()` 호출 |