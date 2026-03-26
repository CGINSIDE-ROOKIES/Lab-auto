"""
기반 스크래퍼 — requests 기반 (유형 A/B/D)
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional

import requests
from bs4 import BeautifulSoup


@dataclass
class FormItem:
    source: str
    title: str
    file_name: str
    file_url: str
    source_url: str
    registered_date: str
    department: str = ""
    file_format: str = ""
    local_path: str = ""
    download_post_data: dict | None = None

    def __post_init__(self):
        if not self.file_format and self.file_name:
            parts = self.file_name.rsplit(".", 1)
            self.file_format = parts[-1].lower() if len(parts) == 2 else ""

    def has_contract_keyword(self) -> bool:
        """파일명 우선, 없으면 제목에서 계약서·약정서 검사"""
        from .utils.file_filter import CONTRACT_KEYWORDS
        target = self.file_name if self.file_name else self.title
        return any(kw in target for kw in CONTRACT_KEYWORDS)


_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "close",   # 매 요청마다 새 TCP 연결 사용 → Keep-Alive 리셋 방지
}


class BaseGovScraper(ABC):
    """정부부처 스크래퍼 기반 클래스 (requests 기반)"""

    ministry_name: str = ""
    request_delay: float = 1.0  # 요청 간 딜레이(초)

    def __init__(self):
        self._init_session()
        # 실시간 진행도 콜백: on_progress(수집건수, 메시지)
        self.on_progress: Callable[[int, str], None] | None = None
        # 연결 오류 발생 여부 (run_all.py retry 판단용)
        self.had_connection_error: bool = False

    def _init_session(self) -> None:
        """세션 재초기화. 서브클래스에서 오버라이드 가능."""
        self.session = requests.Session()
        self.session.headers.update(_DEFAULT_HEADERS)

    def _request_with_retry(self, fn: Callable, max_retries: int = 3):
        """
        fn()을 호출하고 실패 시 세션 재초기화 후 재시도.
        모든 scrapers의 requests 호출에 공통 적용되는 재시도 래퍼.

        재시도가 한 번이라도 발생한 경우 had_connection_error = True 설정.
        세션 리셋 후 서버가 빈 200 응답을 반환하는 경우에도 retry 대상 포함되도록.
        """
        for attempt in range(max_retries):
            if attempt > 0:
                wait = 2 ** attempt
                print(f"[{self.ministry_name}] 재시도 {attempt}/{max_retries - 1}, {wait}초 대기")
                time.sleep(wait)
                self._init_session()
            try:
                resp = fn()
                if attempt > 0:
                    # 이전에 연결 오류 발생 후 세션 리셋으로 성공 — 빈 응답일 수 있으므로 플래그 설정
                    self.had_connection_error = True
                return resp
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[{self.ministry_name}] 요청 실패 (시도={attempt + 1}): {e}")
                    continue
                self.had_connection_error = True
                raise

    # ── 추상 메서드 ────────────────────────────────────────────────

    @abstractmethod
    def fetch_items(self) -> list[FormItem]:
        """전체 서식 목록을 수집해서 반환 (필터링 전)"""
        ...

    # ── 공통 구현 ──────────────────────────────────────────────────

    _EXCLUDED_EXTS = {"jpg", "jpeg", "png", "gif", "bmp", "svg", "webp", "xlsx", "xls"}

    def filter_by_keyword(self, items: list[FormItem]) -> list[FormItem]:
        from .utils.file_filter import EXCLUDE_TITLE_KEYWORDS
        return [
            item for item in items
            if item.has_contract_keyword()
            and item.file_format.lower() not in self._EXCLUDED_EXTS
            and not any(kw in item.title or kw in item.file_name for kw in EXCLUDE_TITLE_KEYWORDS)
        ]

    def run(self) -> list[FormItem]:
        items = self.fetch_items()
        return self.filter_by_keyword(items)

    # ── 헬퍼 메서드 ───────────────────────────────────────────────

    def parse_html(
        self,
        url: str,
        params: Optional[dict] = None,
        **kwargs,
    ) -> BeautifulSoup:
        time.sleep(self.request_delay)
        resp = self._request_with_retry(
            lambda: self.session.get(url, params=params, timeout=30, **kwargs)
        )
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    def post_html(
        self,
        url: str,
        data: Optional[dict] = None,
        **kwargs,
    ) -> BeautifulSoup:
        time.sleep(self.request_delay)
        resp = self._request_with_retry(
            lambda: self.session.post(url, data=data, timeout=30, **kwargs)
        )
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
