"""
농촌진흥청 통합검색 스크래퍼 (Playwright)

검색 URL: https://www.rda.go.kr/search/engineSearch.do
- 검색창 찾아서 키워드 입력 → Enter 또는 검색 버튼 클릭
- 결과 파싱: 첨부파일 링크 또는 게시물 제목 추출
- 다음 페이지 클릭 방식 페이지네이션
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

MINISTRY_NAME = "농촌진흥청"
BASE_URL = "https://www.rda.go.kr"
SEARCH_URL = f"{BASE_URL}/search/engineSearch.do"


class RdaScraper(BasePlaywrightScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.5

    def __init__(self, download_dir: str = "downloads/gov_contracts/농촌진흥청"):
        super().__init__()
        self.download_dir = download_dir

    def _scrape_page(self, page: Page) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        for keyword in CONTRACT_KEYWORDS:
            page.goto(SEARCH_URL, wait_until="networkidle", timeout=30000)
            time.sleep(1)

            # 검색창 찾기 (Locator: visible 요소만 대상)
            specific_selectors = ["input[name='searchVal']", "input[name='query']", "input[name='keyword']", "input[name='searchWord']", "input[name='searchKeyword']"]
            generic_selector = "input[type='search'], input[placeholder*='검색'], .search_input input, .searchWrap input, form input[type='text']"
            loc = None
            for sel in specific_selectors:
                candidate = page.locator(sel).first
                try:
                    candidate.wait_for(state="visible", timeout=3000)
                    loc = candidate
                    break
                except Exception:
                    continue
            if loc is None:
                try:
                    loc = page.locator(generic_selector).first
                    loc.wait_for(state="visible", timeout=8000)
                except Exception:
                    print(f"[RDA] 검색창을 찾을 수 없음 (keyword={keyword})")
                    continue
            try:
                loc.fill(keyword)
                time.sleep(0.3)
                loc.press("Enter")
            except Exception:
                print(f"[RDA] 검색 실행 실패 (keyword={keyword})")
                continue

            page.wait_for_load_state("networkidle")
            time.sleep(1.5)

            # 페이지네이션 루프
            page_num = 1
            while True:
                soup = BeautifulSoup(page.content(), "html.parser")
                items_found = self._parse_results(soup, seen, all_items)

                # 다음 페이지 탐색
                next_btn = page.query_selector(
                    "a.next, a[class*='next'], li.next > a, "
                    "a[title='다음'], a[title='다음 페이지'], "
                    ".pagination a[rel='next'], .paging a[title*='다음'], "
                    "a[aria-label*='다음'], button[aria-label*='다음']"
                )
                if not next_btn:
                    next_page_num = page_num + 1
                    next_btn = page.query_selector(
                        f"a[onclick*='{next_page_num}'], "
                        f".paging a:text-is('{next_page_num}'), "
                        f"a[href*='pageIndex={next_page_num}'], "
                        f"a[href*='page={next_page_num}'], "
                        f"a[href*='currentPage={next_page_num}']"
                    )

                if not next_btn or not items_found:
                    break

                try:
                    next_btn.click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(1.5)
                    page_num += 1
                except Exception:
                    break

        return all_items

    def _parse_results(
        self,
        soup: BeautifulSoup,
        seen: set[str],
        all_items: list[FormItem],
    ) -> bool:
        """결과 페이지에서 파일 항목 추출. 새 항목 추가 여부 반환.

        RDA 검색 결과 구조:
          <li class="total-search-item">
            <p class="info-top">
              <span class="krds-badge">첨부파일</span>
              <span class="i-date">2004.06.22</span>
            </p>
            <div class="info-body">
              <a href="/fileDownLoadDw.do?boardId=...&dataNo=...&sortNo=0">
                <div class="in"><div class="text"><p class="tit">파일명.hwp</p></div></div>
              </a>
            </div>
          </li>
        """
        found_any = False

        # 농촌진흥청 전용: li.total-search-item
        result_rows = soup.select("li.total-search-item")

        # fallback: 일반 검색 결과 구조
        if not result_rows:
            result_rows = (
                soup.select(".search_list li, .result_list li, .searchResult li, ul.list li")
                or soup.select("table tbody tr")
            )

        for row in result_rows:
            # 날짜
            date_tag = row.find("span", class_="i-date") or row.find(
                class_=lambda c: c and any(x in " ".join(c) for x in ["date", "time", "reg"]) if c else False
            )
            registered_date = date_tag.get_text(strip=True) if date_tag else ""

            # 첨부파일 링크 탐색 (RDA 전용 패턴 우선)
            file_links = row.find_all(
                "a",
                href=lambda h: h and any(
                    x in h for x in [
                        "fileDownLoadDw", "download", "Download", "atchFile",
                        "fileDown", "FileDown", ".hwp", ".pdf", ".doc", ".xls", ".zip",
                    ]
                ),
            )
            if not file_links:
                file_links = row.find_all(
                    "a",
                    class_=lambda c: c and any(x in " ".join(c) for x in ["file", "attach", "down"]) if c else False,
                )

            for fa in file_links:
                file_href = fa.get("href", "")
                if not file_href:
                    continue

                file_url = (
                    file_href if file_href.startswith("http")
                    else BASE_URL + file_href if file_href.startswith("/")
                    else BASE_URL + "/" + file_href
                )

                # 파일명: p.tit 우선, 없으면 a 텍스트
                tit_p = fa.find("p", class_="tit")
                if tit_p:
                    file_name = re.sub(r"\s+", " ", tit_p.get_text()).strip()
                else:
                    file_name = re.sub(r"\s+", " ", fa.get_text()).strip()
                    file_name = re.sub(r"\s*\[.*?\]", "", file_name).strip()

                if not file_name or "." not in file_name:
                    qs = urllib.parse.parse_qs(urllib.parse.urlparse(file_href).query)
                    file_name = (
                        qs.get("originalFileName", qs.get("fileName", [""])) [-1]
                        or file_href.rsplit("/", 1)[-1]
                    )

                file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
                dedup_key = file_url
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                found_any = True

                all_items.append(FormItem(
                    ministry=MINISTRY_NAME,
                    title=file_name,
                    file_name=file_name,
                    file_url=file_url,
                    source_url=BASE_URL + "/search/engineSearch.do",
                    registered_date=registered_date,
                    file_ext=file_ext,
                ))

        return found_any
