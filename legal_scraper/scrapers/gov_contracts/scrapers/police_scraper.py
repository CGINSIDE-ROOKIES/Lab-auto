"""
경찰청 통합검색 스크래퍼 (Playwright)

검색 URL: https://www.police.go.kr/user/search/ND_searchResult.do
- 검색창 찾아서 키워드 입력 → Enter 또는 검색 버튼 클릭
- NHN 표준 검색 결과 페이지 파싱
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

MINISTRY_NAME = "경찰청"
BASE_URL = "https://www.police.go.kr"
SEARCH_URL = f"{BASE_URL}/user/search/ND_searchResult.do"


class PoliceScraper(BasePlaywrightScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.5

    def __init__(self, download_dir: str = "downloads/gov_contracts/경찰청"):
        super().__init__()
        self.download_dir = download_dir

    def _scrape_page(self, page: Page) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        for keyword in CONTRACT_KEYWORDS:
            try:
                page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                print(f"[POLICE] 페이지 로드 실패: {e}")
                continue
            time.sleep(1.5)

            # 검색창 찾기 (Locator: visible 요소만 대상)
            specific_selectors = ["input[name='searchTerm']", "input[name='query']", "input[name='keyword']", "input[name='searchKeyword']"]
            generic_selector = "input[type='search'], input[placeholder*='검색'], form input[type='text']"
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
                    print(f"[POLICE] 검색창을 찾을 수 없음 (keyword={keyword})")
                    continue
            try:
                loc.fill(keyword)
                time.sleep(0.3)
                loc.press("Enter")
            except Exception:
                print(f"[POLICE] 검색 실행 실패 (keyword={keyword})")
                continue

            page.wait_for_load_state("networkidle")
            time.sleep(1.5)

            # 페이지네이션 루프
            page_num = 1
            while True:
                soup = BeautifulSoup(page.content(), "html.parser")
                items_found = self._parse_results(soup, seen, all_items)

                # NHN 검색 모듈의 다음 페이지 패턴
                next_btn = page.query_selector(
                    "a.next, a[class*='next'], li.next > a, "
                    "a[title='다음'], a[title='다음 페이지'], "
                    ".pagination a[rel='next'], .paging a[title*='다음']"
                )
                if not next_btn:
                    next_page_num = page_num + 1
                    next_btn = page.query_selector(
                        f"a[onclick*='{next_page_num}'], "
                        f".paging a:text-is('{next_page_num}'), "
                        f"a[href*='pageIndex={next_page_num}'], "
                        f"a[href*='page={next_page_num}']"
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
        """NHN 표준 검색 결과 파싱. 새 항목 추가 여부 반환."""
        found_any = False

        # NHN 표준 검색 결과 구조 및 일반 목록 구조 모두 시도
        result_rows = (
            soup.select(".ND_result li, .result_list li, .search_list li, "
                        ".searchResult li, .board_list li")
            or soup.select("table.board_list tbody tr, table.list tbody tr")
            or soup.select("ul.bd_list li, ul.list_type li")
        )

        for row in result_rows:
            # 제목
            title_tag = (
                row.find("a", class_=lambda c: c and any(x in " ".join(c) for x in ["tit", "title", "subject", "link"]) if c else False)
                or row.find("dt")
                or row.find("strong")
                or row.find("a", href=True)
            )
            if not title_tag:
                continue

            title = re.sub(r"\s+", " ", title_tag.get_text()).strip()
            # 하이라이트 태그 제거 후 재추출
            title = re.sub(r"<.*?>", "", title).strip()

            source_href = title_tag.get("href", "")
            source_url = (
                source_href if source_href.startswith("http")
                else BASE_URL + source_href if source_href.startswith("/")
                else ""
            )

            # 날짜
            date_tag = row.find(
                class_=lambda c: c and any(x in " ".join(c) for x in ["date", "time", "reg", "write"]) if c else False
            )
            registered_date = date_tag.get_text(strip=True) if date_tag else ""

            # 첨부파일 링크 탐색
            file_links = row.find_all(
                "a",
                href=lambda h: h and any(
                    x in h for x in [
                        "download", "Download", "atchFile", "fileDown",
                        "FileDown", "fileDownload", ".hwp", ".pdf", ".doc", ".xls", ".zip",
                    ]
                ),
            )
            if not file_links:
                file_links = row.find_all(
                    "a",
                    class_=lambda c: c and any(x in " ".join(c) for x in ["file", "attach", "down"]) if c else False,
                )
            # NHN 검색 결과에서 파일 항목 탐색 (dd 내 파일 목록)
            if not file_links:
                dd = row.find("dd", class_=lambda c: c and "file" in " ".join(c) if c else False)
                if dd:
                    file_links = dd.find_all("a", href=True)

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
                # 첨부파일 없음 → 키워드 매칭 제목 항목
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
