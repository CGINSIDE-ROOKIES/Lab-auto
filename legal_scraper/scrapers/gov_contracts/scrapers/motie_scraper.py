"""
산업통상자원부 통합검색 스크래퍼 (Playwright)

검색 URL: https://www.motie.go.kr/kor/search?site=main&kwd={keyword}&category={cat}&currentPage={N}
- 카테고리별 순회: c1(알림·뉴스), c2(정책·정보), c3(예산·법령)
- 각 검색 결과 li에서 div.file_box .file href → 직접 다운로드 URL
- 페이지네이션: currentPage 증가, rowPerPage=10
"""
from __future__ import annotations

import time
import urllib.parse

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from ..base_playwright_scraper import BasePlaywrightScraper
from ..base_scraper import FormItem
from ..utils.file_filter import CONTRACT_KEYWORDS

MINISTRY_NAME = "산업통상자원부"
BASE_URL = "https://www.motie.go.kr"
SEARCH_URL = f"{BASE_URL}/kor/search"

# 순회할 카테고리
CATEGORIES = ["c1", "c2", "c3"]


class MotieScraper(BasePlaywrightScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.5

    def __init__(self, download_dir: str = "downloads/gov_contracts/산업통상자원부"):
        super().__init__()
        self.download_dir = download_dir

    def _scrape_page(self, page: Page) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        for keyword in CONTRACT_KEYWORDS:
            for category in CATEGORIES:
                page_num = 1
                while True:
                    url = (
                        f"{SEARCH_URL}?site=main"
                        f"&kwd={urllib.parse.quote(keyword)}"
                        f"&category={category}"
                        f"&currentPage={page_num}"
                        f"&rowPerPage=10"
                    )
                    page.goto(url, wait_until="networkidle", timeout=30000)
                    time.sleep(1)

                    soup = BeautifulSoup(page.content(), "html.parser")

                    # 검색 결과 li 파싱
                    result_items = soup.select("ul li")
                    found_any = False

                    for li in result_items:
                        # 제목 링크
                        title_a = li.select_one("a[href*='/kor/article'], a[href*='/kor/'] p.title")
                        if not title_a:
                            title_a = li.find("a", href=lambda h: h and "/kor/" in (h or ""))
                        if not title_a:
                            continue

                        title_text = li.select_one("p.title")
                        title = title_text.get_text(strip=True) if title_text else title_a.get_text(strip=True)

                        # 날짜
                        date_span = li.select_one("p.title span, span.date")
                        registered_date = date_span.get_text(strip=True) if date_span else ""

                        # 파일 박스에서 직접 다운로드 링크 추출
                        file_box = li.find("div", class_="file_box")
                        if not file_box:
                            continue

                        file_links = file_box.find_all("a", class_="file")
                        if not file_links:
                            continue

                        source_href = title_a.get("href", "")
                        source_url = source_href if source_href.startswith("http") else BASE_URL + source_href

                        for fa in file_links:
                            file_href = fa.get("href", "")
                            if not file_href:
                                continue

                            file_url = file_href if file_href.startswith("http") else BASE_URL + file_href
                            file_name = fa.get_text(strip=True)
                            if not file_name:
                                file_name = file_href.rsplit("/", 1)[-1]

                            dedup_key = file_url
                            if dedup_key in seen:
                                continue
                            seen.add(dedup_key)

                            file_ext = ""
                            # li 클래스에서 확장자 추출 (e.g. class="hwpx")
                            li_class = fa.parent.get("class", []) if fa.parent else []
                            for cls in li_class:
                                if cls.lower() in ["hwp", "hwpx", "pdf", "xlsx", "xls", "docx", "doc", "zip"]:
                                    file_ext = cls.lower()
                                    break
                            if not file_ext and "." in file_name:
                                file_ext = file_name.rsplit(".", 1)[-1].lower()

                            found_any = True
                            all_items.append(FormItem(
                                source=MINISTRY_NAME,
                                title=title,
                                file_name=file_name,
                                file_url=file_url,
                                source_url=source_url,
                                registered_date=registered_date,
                                file_format=file_ext,
                            ))

                    # 다음 페이지 확인
                    next_btn = soup.find("a", class_=lambda c: c and "next" in " ".join(c).lower() if c else False)
                    if not next_btn or not found_any:
                        break

                    page_num += 1

        return all_items
