"""공통 관심사를 분리하는 데코레이터 모음.

- log_call: 함수 실행 시작/종료를 표준 에러로 로깅
- measure_time: 함수 실행 소요 시간을 측정하여 로깅
- handle_errors: AppError 및 예기치 못한 예외를 스택트레이스 없이
  '원인 + 힌트' 형태로 출력하고, 0이 아닌 코드로 종료한다.
"""
from __future__ import annotations

import functools
import sys
import time
from datetime import datetime
from typing import Any, Callable, TypeVar

from .models import AppError

F = TypeVar("F", bound=Callable[..., Any])


def log_call(func: F) -> F:
    """함수 호출 시작/종료 시각을 로그로 남긴다."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[LOG {ts}] '{func.__name__}' 실행 시작", file=sys.stderr)
        try:
            return func(*args, **kwargs)
        finally:
            ts2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[LOG {ts2}] '{func.__name__}' 실행 종료", file=sys.stderr)

    return wrapper  # type: ignore[return-value]


def measure_time(func: F) -> F:
    """함수 실행 소요 시간을 측정하여 로그로 남긴다."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            print(f"[TIME] '{func.__name__}' 실행 시간: {elapsed:.4f}초", file=sys.stderr)

    return wrapper  # type: ignore[return-value]


def handle_errors(func: F) -> F:
    """AppError 및 예기치 못한 예외를 잡아 사용자 메시지로 변환하고 종료 코드를 정한다."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except AppError as exc:
            print(f"[오류] {exc.cause}")
            if exc.hint:
                print(f"[힌트] {exc.hint}")
            sys.exit(1)
        except KeyboardInterrupt:
            print("\n[중단] 사용자에 의해 취소되었습니다.")
            sys.exit(1)
        except Exception as exc:  # noqa: BLE001 - 스택트레이스 대신 요약 메시지만 노출
            print(f"[오류] 예기치 못한 문제가 발생했습니다: {exc}")
            print("[힌트] 입력 값을 확인하거나, 데이터 파일 상태를 점검하세요.")
            sys.exit(1)

    return wrapper  # type: ignore[return-value]
