"""
국가유산청 법령정보 스크래퍼 (Playwright)

목록 URL:
  https://www.khs.go.kr/lawBbz/selectLawBbzList.do
  ?mn=NS_03_01_01&searchCnd=1&searchWrd={keyword}&pageIndex={N}

- 목록: table.tbl tbody tr → a.b_tit (제목/상세URL), td[data-column=기간] (날짜)
- 상세: a.krds-btn[href*=FileDown.do] → href=다운로드URL, title=파일명
  파일명 title 형식: "(설명) 실제파일명.ext" → 괄호 앞부분 제거
- jsessionid는 URL에서 제거 후 사용
- 목록 행 수 < PAGE_SIZE 이면 마지막 페이지
"""
from __future__ import annotations

import re
import time
import urllib.parse

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from ..base_playwright_scraper import BasePlaywrightScraper
from ..base_scraper import FormItem
from ..utils.file_filter import CONTRACT_KEYWORDS

MINISTRY_NAME = "국가유산청"
BASE_URL = "https://www.khs.go.kr"
LIST_URL = f"{BASE_URL}/lawBbz/selectLawBbzList.do"
PAGE_SIZE = 10

_JSESSIONID_RE = re.compile(r';jsessionid=[^?&#]*')


def _clean_url(path: str) -> str:
    """jsessionid 제거 후 절대 URL 반환"""
    path = _JSESSIONID_RE.sub("", path)
    return path if path.startswith("http") else BASE_URL + path


def _extract_filename(title_attr: str) -> str:
    """'(설명) 파일명.ext' → '파일명.ext'"""
    return re.sub(r'^\([^)]*\)\s*', '', title_attr).strip()


class KhsScraper(BasePlaywrightScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.0

    def __init__(self, download_dir: str = "downloads/gov_contracts/국가유산청"):
        super().__init__()
        self.download_dir = download_dir

    def _scrape_page(self, page: Page) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        for keyword in CONTRACT_KEYWORDS:
            page_idx = 1

            while True:
                list_url = (
                    f"{LIST_URL}?mn=NS_03_01_01&searchCnd=1"
                    f"&searchWrd={urllib.parse.quote(keyword)}"
                    f"&pageIndex={page_idx}"
                )
                page.goto(list_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(self.request_delay)

                soup = BeautifulSoup(page.content(), "html.parser")
                rows = soup.select("table.tbl tbody tr")
                if not rows:
                    break

                for row in rows:
                    title_a = row.select_one("a.b_tit")
                    if not title_a:
                        continue

                    span = title_a.find("span")
                    title = span.get_text(strip=True) if span else title_a.get_text(strip=True)
                    title = re.sub(r'\s+', ' ', title)

                    detail_href = title_a.get("href", "")
                    source_url = _clean_url(detail_href)

                    # 날짜: "기간" 열 (시작일만 사용)
                    date_td = row.find("td", {"data-column": lambda v: v and "기간" in v if v else False})
                    registered_date = ""
                    if date_td:
                        m = re.search(r'\d{4}-\d{2}-\d{2}', date_td.get_text())
                        registered_date = m.group(0) if m else ""

                    # 상세 페이지 방문
                    page.goto(source_url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(self.request_delay)

                    detail_soup = BeautifulSoup(page.content(), "html.parser")

                    for fa in detail_soup.select('a[href*="FileDown.do"]'):
                        raw_href = fa.get("href", "")
                        file_url = _clean_url(raw_href)
                        raw_title = fa.get("title", "").strip()
                        file_name = _extract_filename(raw_title) if raw_title else fa.get_text(strip=True)
                        file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

                        if file_url in seen:
                            continue
                        seen.add(file_url)

                        all_items.append(FormItem(
                            source=MINISTRY_NAME,
                            title=title,
                            file_name=file_name,
                            file_url=file_url,
                            source_url=source_url,
                            registered_date=registered_date,
                            file_format=file_ext,
                        ))

                if len(rows) < PAGE_SIZE:
                    break
                page_idx += 1

        return all_items
