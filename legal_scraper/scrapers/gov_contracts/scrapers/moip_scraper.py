"""
지식재산처 통합검색 스크래퍼 (Playwright)

검색 URL: POST https://www.moip.go.kr/ko/searchView.do
  schSelectVal=FILE, queryText={keyword}, query={keyword}, currentPageNo={N}

- 결과: ul.srchResult_list li → fn_download 파라미터 추출
- 파일 다운로드: POST https://www.moip.go.kr/ko/searchFileDown.do
  SYS_CD={v1}, BOARD_ID={v2}, SEQ={v3}, ATFL_SEQ={v4}
- 페이지네이션: currentPageNo 증가
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

MINISTRY_NAME = "지식재산처"
BASE_URL = "https://www.moip.go.kr"
SEARCH_URL = f"{BASE_URL}/ko/searchView.do"
DOWNLOAD_URL = f"{BASE_URL}/ko/searchFileDown.do"


class MoipScraper(BasePlaywrightScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.5

    def __init__(self, download_dir: str = "downloads/gov_contracts/지식재산처"):
        super().__init__()
        self.download_dir = download_dir

    def _scrape_page(self, page: Page) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        for keyword in CONTRACT_KEYWORDS:
            page_num = 1
            while True:
                # POST 방식: URL로 GET 후 폼 제출
                page.goto(SEARCH_URL, wait_until="networkidle", timeout=30000)
                time.sleep(0.5)

                # 폼 필드 설정 후 제출
                page.evaluate(f'''() => {{
                    let frm = document.searchForm;
                    if (!frm) return;
                    frm.schSelectVal.value = "FILE";
                    frm.queryText.value = {repr(keyword)};
                    frm.query.value = {repr(keyword)};
                    frm.currentPageNo.value = "{page_num}";
                    frm.action = "/ko/searchView.do";
                    frm.submit();
                }}''')
                page.wait_for_load_state("networkidle", timeout=15000)
                time.sleep(1)

                soup = BeautifulSoup(page.content(), "html.parser")
                items = soup.select("ul.srchResult_list li")
                if not items:
                    break

                found_any = False
                for li in items:
                    # fn_download 파라미터 추출
                    dl_a = li.find("a", onclick=re.compile(r"fn_download"))
                    if not dl_a:
                        continue

                    onclick = dl_a.get("onclick", "")
                    m = re.search(r"fn_download\('([^']+)',\s*'([^']+)',\s*'([^']+)',\s*'([^']+)'\)", onclick)
                    if not m:
                        continue

                    sys_cd, board_id, seq, atfl_seq = m.group(1), m.group(2), m.group(3), m.group(4)
                    file_name = dl_a.find("strong")
                    file_name = file_name.get_text(strip=True) if file_name else dl_a.get_text(strip=True)

                    # 파일 URL (POST form → GET URL로 표현)
                    file_url = (
                        f"{DOWNLOAD_URL}"
                        f"?SYS_CD={sys_cd}&BOARD_ID={urllib.parse.quote(board_id)}"
                        f"&SEQ={seq}&ATFL_SEQ={atfl_seq}"
                    )

                    dedup_key = file_url
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)

                    file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

                    # 출처 링크 (기사 페이지)
                    source_a = li.find("a", href=lambda h: h and "/ko/" in (h or "") and "searchFileDown" not in (h or ""))
                    source_url = ""
                    if source_a:
                        href = source_a.get("href", "")
                        source_url = href if href.startswith("http") else BASE_URL + href

                    found_any = True
                    all_items.append(FormItem(
                        source=MINISTRY_NAME,
                        title=file_name,
                        file_name=file_name,
                        file_url=file_url,
                        source_url=source_url or SEARCH_URL,
                        registered_date="",
                        file_format=file_ext,
                    ))

                if not found_any:
                    break

                # 다음 페이지 확인
                pager = soup.find("div", id="pagination")
                if not pager:
                    break
                next_a = pager.find("a", class_="next")
                if not next_a:
                    break

                page_num += 1

        return all_items
