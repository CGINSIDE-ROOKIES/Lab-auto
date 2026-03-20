"""
Playwright 기반 스크래퍼 (유형 C — JS 렌더링 필요)

Windows + Streamlit 환경에서 sync_playwright()는 ProactorEventLoop가 필요하다.
Streamlit이 이미 asyncio 루프를 점유하고 있어 메인 스레드에서 직접 호출하면
NotImplementedError(_make_subprocess_transport)가 발생하므로,
별도 스레드를 생성해 ProactorEventLoop를 명시적으로 설정한 뒤 실행한다.
"""
from __future__ import annotations

import asyncio
import sys
import threading
from typing import Callable

from playwright.sync_api import Page, sync_playwright

from .base_scraper import BaseGovScraper, FormItem


class BasePlaywrightScraper(BaseGovScraper):
    """Playwright sync API를 사용하는 스크래퍼 기반 클래스"""

    headless: bool = True

    def run_with_browser(self, task_fn: Callable[[Page], list[FormItem]]) -> list[FormItem]:
        """
        sync_playwright를 별도 스레드에서 실행한다.

        Windows에서 sync_playwright()는 내부적으로 asyncio 이벤트 루프를 생성하는데,
        Streamlit 실행 환경에서는 ProactorEventLoop를 명시적으로 지정하지 않으면
        subprocess를 지원하지 않는 SelectorEventLoop가 선택돼 NotImplementedError가 발생한다.
        별도 스레드를 생성하고 그 안에서 ProactorEventLoop를 설정함으로써 회피한다.
        """
        result: list[FormItem] = []
        exc_holder: list[BaseException] = []

        def _run() -> None:
            if sys.platform == "win32":
                loop = asyncio.ProactorEventLoop()
                asyncio.set_event_loop(loop)
            try:
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
                        items = task_fn(page)
                        result.extend(items or [])
                    finally:
                        context.close()
                        browser.close()
            except BaseException as e:
                exc_holder.append(e)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join()

        if exc_holder:
            raise exc_holder[0]
        return result

    def fetch_items(self) -> list[FormItem]:
        return self.run_with_browser(self._scrape_page)

    def _scrape_page(self, page: Page) -> list[FormItem]:
        raise NotImplementedError(
            f"{self.__class__.__name__}._scrape_page() 를 구현하세요."
        )
