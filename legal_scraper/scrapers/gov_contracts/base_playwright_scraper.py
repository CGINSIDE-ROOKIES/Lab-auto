"""
Playwright 기반 스크래퍼 (유형 C — JS 렌더링 필요)
"""
from __future__ import annotations

from typing import Callable

from playwright.sync_api import Page, sync_playwright

from .base_scraper import BaseGovScraper, FormItem


class BasePlaywrightScraper(BaseGovScraper):
    """Playwright sync API를 사용하는 스크래퍼 기반 클래스"""

    headless: bool = True

    def run_with_browser(self, task_fn: Callable[[Page], list[FormItem]]) -> list[FormItem]:
        """sync_playwright 컨텍스트를 안전하게 열고 task_fn 실행 후 닫는다."""
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="ko-KR",
                ignore_https_errors=True,
            )
            page = context.new_page()
            try:
                return task_fn(page)
            finally:
                context.close()
                browser.close()

    def fetch_items(self) -> list[FormItem]:
        return self.run_with_browser(self._scrape_page)

    def _scrape_page(self, page: Page) -> list[FormItem]:
        raise NotImplementedError(
            f"{self.__class__.__name__}._scrape_page() 를 구현하세요."
        )
