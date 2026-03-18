"""
보건복지부 통합검색 스크래퍼 (Playwright)

검색 URL: https://www.mohw.go.kr/react/search/search.jsp
- React SPA: 검색창에 키워드 입력 → Enter 또는 검색 버튼 클릭
- networkidle 대기 필수
- 결과: 첨부파일 링크 또는 게시물 제목에서 파일 추출
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

MINISTRY_NAME = "보건복지부"
BASE_URL = "https://www.mohw.go.kr"
SEARCH_URL = f"{BASE_URL}/react/search/search.jsp"


class MohwScraper(BasePlaywrightScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 2.0

    def __init__(self, download_dir: str = "downloads/gov_contracts/보건복지부"):
        super().__init__()
        self.download_dir = download_dir

    def _scrape_page(self, page: Page) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        for keyword in CONTRACT_KEYWORDS:
            try:
                page.goto(SEARCH_URL, wait_until="networkidle", timeout=30000)
            except Exception as e:
                print(f"[MOHW] 페이지 로드 실패: {e}")
                continue
            time.sleep(3)  # React hydration 충분히 대기

            # name='query'가 visible input (DOM에서 hidden input보다 뒤에 위치)
            # 구체적인 name 우선, 실패 시 generic fallback
            specific_selectors = ["input[name='query']", "input[name='keyword']", "input[name='searchKeyword']"]
            generic_selector = "input[placeholder*='검색'], form input[type='text']"
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
                    print(f"[MOHW] 검색창을 찾을 수 없음 (keyword={keyword})")
                    continue
            try:
                loc.fill(keyword)
                time.sleep(0.3)
                loc.press("Enter")
                page.wait_for_load_state("networkidle")
                time.sleep(2)
            except Exception:
                print(f"[MOHW] 검색 실행 실패 (keyword={keyword})")
                continue

            page.wait_for_load_state("networkidle")
            time.sleep(2)

            # 페이지네이션 루프
            page_num = 1
            while True:
                soup = BeautifulSoup(page.content(), "html.parser")
                items_found = self._parse_results(soup, seen, all_items)

                # 다음 페이지 탐색
                next_btn = page.query_selector(
                    "a.next, a[class*='next'], button[class*='next'], "
                    "li.next > a, .paging a[title*='다음'], .pagination a[title*='다음'], "
                    "a[title='다음 페이지'], a[aria-label*='다음']"
                )
                if not next_btn:
                    next_page_num = page_num + 1
                    next_btn = page.query_selector(
                        f"a[onclick*='page({next_page_num})'], "
                        f"a[href*='page={next_page_num}'], "
                        f".paging a:text-is('{next_page_num}')"
                    )

                if not next_btn or not items_found:
                    break

                try:
                    next_btn.click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(2)
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
        """결과 페이지에서 파일 항목 추출. 새 항목 추가 여부 반환."""
        found_any = False

        # 결과 목록 파싱 (React 렌더링 후 DOM)
        result_rows = (
            soup.select("ul.search_list li, ul.result_list li, .searchResult li, "
                        ".board_list li, ul.list li, div.result_list li")
            or soup.select("table.board_list tbody tr, table.list tbody tr")
            or soup.select("div.result_wrap article, div.srch_list li")
        )

        for row in result_rows:
            # 제목 및 상세 링크
            title_tag = (
                row.find("a", class_=lambda c: c and any(x in " ".join(c) for x in ["tit", "title", "subject"]) if c else False)
                or row.find("h3", recursive=True)
                or row.find("strong")
                or row.find("a", href=True)
            )
            if not title_tag:
                continue

            title = re.sub(r"\s+", " ", title_tag.get_text()).strip()
            source_href = title_tag.get("href", "")
            source_url = (
                source_href if source_href.startswith("http")
                else BASE_URL + source_href if source_href.startswith("/")
                else ""
            )

            # 날짜
            date_tag = row.find(
                class_=lambda c: c and any(x in " ".join(c) for x in ["date", "time", "reg"]) if c else False
            )
            registered_date = date_tag.get_text(strip=True) if date_tag else ""

            # 첨부파일 링크 탐색
            file_links = row.find_all(
                "a",
                href=lambda h: h and any(
                    x in h for x in [
                        "download", "Download", "atchFile", "fileDown",
                        "FileDown", "fileDownload", "BbsFileDown", ".hwp", ".pdf", ".doc", ".xls", ".zip",
                    ]
                ),
            )
            if not file_links:
                file_links = row.find_all(
                    "a",
                    class_=lambda c: c and any(x in " ".join(c) for x in ["file", "attach", "down"]) if c else False,
                )

            if file_links:
                for fa in file_links:
                    file_href = fa.get("href", "")
                    if not file_href:
                        continue

                    file_url = (
                        file_href if file_href.startswith("http")
                        else BASE_URL + file_href if file_href.startswith("/")
                        else BASE_URL + "/" + file_href
                    )
                    file_name = re.sub(r"\s+", " ", fa.get_text()).strip()
                    file_name = re.sub(r"\s*\[.*?\]", "", file_name).strip()

                    if not file_name or "." not in file_name:
                        qs = urllib.parse.parse_qs(urllib.parse.urlparse(file_href).query)
                        file_name = (
                            qs.get("originalFileName", qs.get("fileName", qs.get("atchFileNm", [""])))[-1]
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
                        title=title,
                        file_name=file_name,
                        file_url=file_url,
                        source_url=source_url,
                        registered_date=registered_date,
                        file_ext=file_ext,
                    ))
            else:
                # 첨부파일 없음 → 키워드 매칭된 제목 항목
                if any(kw in title for kw in CONTRACT_KEYWORDS) and source_url:
                    dedup_key = source_url + title
                    if dedup_key not in seen:
                        seen.add(dedup_key)
                        found_any = True
                        all_items.append(FormItem(
                            ministry=MINISTRY_NAME,
                            title=title,
                            file_name="",
                            file_url=source_url,
                            source_url=source_url,
                            registered_date=registered_date,
                            file_ext="",
                        ))

        return found_any
