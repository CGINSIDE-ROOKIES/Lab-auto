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
    ministry: str
    title: str
    file_name: str
    file_url: str
    source_url: str
    registered_date: str
    department: str = ""
    file_ext: str = ""
    local_path: str = ""

    def __post_init__(self):
        if not self.file_ext and self.file_name:
            parts = self.file_name.rsplit(".", 1)
            self.file_ext = parts[-1].lower() if len(parts) == 2 else ""

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
}


class BaseGovScraper(ABC):
    """정부부처 스크래퍼 기반 클래스 (requests 기반)"""

    ministry_name: str = ""
    request_delay: float = 1.0  # 요청 간 딜레이(초)

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(_DEFAULT_HEADERS)
        # 실시간 진행도 콜백: on_progress(수집건수, 메시지)
        self.on_progress: Callable[[int, str], None] | None = None

    # ── 추상 메서드 ────────────────────────────────────────────────

    @abstractmethod
    def fetch_items(self) -> list[FormItem]:
        """전체 서식 목록을 수집해서 반환 (필터링 전)"""
        ...

    # ── 공통 구현 ──────────────────────────────────────────────────

    _EXCLUDED_EXTS = {"jpg", "jpeg", "png", "gif", "bmp", "svg", "webp"}

    def filter_by_keyword(self, items: list[FormItem]) -> list[FormItem]:
        from .utils.file_filter import EXCLUDE_TITLE_KEYWORDS
        return [
            item for item in items
            if item.has_contract_keyword()
            and item.file_ext.lower() not in self._EXCLUDED_EXTS
            and not any(kw in item.title for kw in EXCLUDE_TITLE_KEYWORDS)
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
        resp = self.session.get(url, params=params, timeout=30, **kwargs)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    def post_html(
        self,
        url: str,
        data: Optional[dict] = None,
        **kwargs,
    ) -> BeautifulSoup:
        time.sleep(self.request_delay)
        resp = self.session.post(url, data=data, timeout=30, **kwargs)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
