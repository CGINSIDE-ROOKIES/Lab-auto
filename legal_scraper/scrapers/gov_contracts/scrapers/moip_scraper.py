"""
지식재산처 통합검색 스크래퍼 (Playwright)

검색 URL: POST https://www.moip.go.kr/ko/searchView.do
  schSelectVal=FILE, queryText={keyword}, query={keyword}, currentPageNo={N}

흐름:
  각 li → fn_download onclick 파라미터 추출 → searchFileDown.do 파일 URL 구성
  breadcrumb menuCd + fn_download SEQ/BOARD_ID → source_url(상세 페이지 URL) 구성
  등록일은 수집 불가(JS 렌더링, 상세 페이지 URL 매핑 불확실) → 빈 문자열 유지
  페이지네이션: currentPageNo 증가, div#pagination a.next 없으면 종료
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
DETAIL_BASE = f"{BASE_URL}/ko/kpoBultnDetail.do"

_FN_RE = re.compile(r"fn_download\('([^']+)',\s*'([^']+)',\s*'([^']+)',\s*'([^']+)'\)")
_MENU_RE = re.compile(r"menuCd=([^&]+)")


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
            print(f"[MOIP] 키워드={keyword} 검색 시작")

            while True:
                page.goto(SEARCH_URL, wait_until="networkidle", timeout=30000)
                time.sleep(0.5)

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
                lis = soup.select("ul.srchResult_list li")
                if not lis:
                    print(f"[MOIP] {keyword} p{page_num} -- 결과 없음, 종료")
                    break

                print(f"[MOIP] {keyword} p{page_num} -- {len(lis)}건")

                for li in lis:
                    a = li.find("a", onclick=_FN_RE)
                    if not a:
                        continue
                    m = _FN_RE.search(a.get("onclick", ""))
                    if not m:
                        continue
                    sys_cd, board_id, seq, atfl_seq = m.group(1), m.group(2), m.group(3), m.group(4)

                    dedup_key = f"{seq}_{atfl_seq}"
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)

                    strong = a.find("strong")
                    file_name = strong.get_text(strip=True) if strong else a.get_text(strip=True)

                    file_url = (
                        f"{DOWNLOAD_URL}"
                        f"?SYS_CD={sys_cd}&BOARD_ID={urllib.parse.quote(board_id)}"
                        f"&SEQ={seq}&ATFL_SEQ={atfl_seq}"
                    )

                    # breadcrumb에서 source_url 구성
                    source_url = SEARCH_URL
                    bc_a = li.find("a", href=_MENU_RE)
                    if bc_a:
                        mc = _MENU_RE.search(bc_a.get("href", ""))
                        if mc:
                            source_url = (
                                f"{DETAIL_BASE}"
                                f"?menuCd={mc.group(1)}&ntatcSeq={seq}"
                                f"&sysCd=SCD02&aprchId={board_id}"
                            )

                    file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
                    all_items.append(FormItem(
                        source=MINISTRY_NAME,
                        title=file_name,
                        file_name=file_name,
                        file_url=file_url,
                        source_url=source_url,
                        registered_date="",
                        file_format=file_ext,
                    ))

                    if self.on_progress:
                        self.on_progress(len(all_items), f"{keyword} p{page_num}")

                pager = soup.find("div", id="pagination")
                if not pager or not pager.find("a", class_="next"):
                    break
                page_num += 1

        return all_items
