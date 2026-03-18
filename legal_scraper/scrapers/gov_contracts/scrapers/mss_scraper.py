"""
중소벤처기업부 표준약정서·계약서 스크래퍼 (Playwright)

목록 URL: https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=605
- 전체 목록 수집(소량, 약 5건)
- 각 항목 상세 페이지 진입: /site/smba/ex/bbs/View.do?cbIdx={cbIdx}&bcIdx={bcIdx}&parentSeq={bcIdx}
- 첨부파일 URL: /common/board/Download.do?bcIdx={bcIdx}&cbIdx={cbIdx}&streFileNm={uuid}.ext
"""
from __future__ import annotations

import re
import time
import urllib.parse

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from ..base_playwright_scraper import BasePlaywrightScraper
from ..base_scraper import FormItem

MINISTRY_NAME = "중소벤처기업부"
BASE_URL = "https://www.mss.go.kr"
LIST_URL = f"{BASE_URL}/site/smba/ex/bbs/List.do"
VIEW_URL = f"{BASE_URL}/site/smba/ex/bbs/View.do"
CB_IDX = "605"


class MssScraper(BasePlaywrightScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 2.0

    def __init__(self, download_dir: str = "downloads/gov_contracts/중소벤처기업부"):
        super().__init__()
        self.download_dir = download_dir

    def _scrape_page(self, page: Page) -> list[FormItem]:
        all_items: list[FormItem] = []

        # 목록 페이지 로드
        page.goto(f"{LIST_URL}?cbIdx={CB_IDX}", wait_until="networkidle", timeout=30000)
        time.sleep(1.5)

        soup = BeautifulSoup(page.content(), "html.parser")
        # 실제 게시물 행이 있는 tbody 탐색 (onclick 있는 tr 포함)
        tbody = None
        for tb in soup.find_all("tbody"):
            if tb.find("tr", onclick=True):
                tbody = tb
                break
        if not tbody:
            return []

        rows = tbody.find_all("tr")
        row_data = []

        for tr in rows:
            onclick = tr.get("onclick", "")
            m = re.search(r"doBbsFView\('(\d+)',\s*'(\d+)'", onclick)
            if not m:
                a = tr.find("a", onclick=True)
                if a:
                    m = re.search(r"doBbsFView\('(\d+)',\s*'(\d+)'", a.get("onclick", ""))
            if not m:
                continue

            cb_idx = m.group(1)
            bc_idx = m.group(2)

            tds = tr.find_all("td")
            title = ""
            for td in tds:
                txt = td.get_text(strip=True)
                if txt and len(txt) > 5 and not txt.isdigit():
                    title = txt
                    break

            row_data.append((cb_idx, bc_idx, title))

        for cb_idx, bc_idx, list_title in row_data:
            detail_url = f"{VIEW_URL}?cbIdx={cb_idx}&bcIdx={bc_idx}&parentSeq={bc_idx}"

            time.sleep(self.request_delay)
            page.goto(detail_url, wait_until="networkidle", timeout=30000)
            time.sleep(1)

            detail_soup = BeautifulSoup(page.content(), "html.parser")

            # 등록일
            registered_date = ""
            for th in detail_soup.find_all("th"):
                if "등록일" in th.get_text():
                    td = th.find_next_sibling("td")
                    if td:
                        registered_date = td.get_text(strip=True)
                    break

            # 제목 (상세 페이지)
            title = list_title
            title_td = detail_soup.find("td", class_=lambda c: c and "subject" in " ".join(c) if c else False)
            if title_td:
                title = title_td.get_text(strip=True)

            # 첨부파일
            file_links = detail_soup.find_all("a", href=lambda h: h and "Download.do" in (h or ""))
            for fa in file_links:
                file_href = fa.get("href", "")
                file_url = file_href if file_href.startswith("http") else BASE_URL + file_href

                # 파일명: div.link의 형제 div.info > span.name
                file_name = ""
                li_parent = fa.parent
                while li_parent and li_parent.name != "li":
                    li_parent = li_parent.parent
                if li_parent:
                    name_span = li_parent.find("span", class_="name")
                    if name_span:
                        file_name = name_span.get_text(strip=True).split("[")[0].strip()

                if not file_name:
                    qp = urllib.parse.parse_qs(urllib.parse.urlparse(file_href).query)
                    file_name = qp.get("streFileNm", [""])[0]

                file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

                all_items.append(FormItem(
                    ministry=MINISTRY_NAME,
                    title=title,
                    file_name=file_name,
                    file_url=file_url,
                    source_url=detail_url,
                    registered_date=registered_date,
                    file_ext=file_ext,
                ))

        return all_items
