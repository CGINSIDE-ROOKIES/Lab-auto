"""
중소벤처기업부 스크래퍼 (유형 A-POST)

목록 URL: https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=605
- 목록이 소량(5건)이므로 전체 수집 후 '계약서' 필터
- 첨부파일 URL: 목록 페이지 tr > td.attached-files > span.single-file[data-href]
- SSL 인증서 오류 → verify=False 처리
"""
from __future__ import annotations

import re
import time
import urllib.parse

import requests
import urllib3
from bs4 import BeautifulSoup

from ..base_scraper import BaseGovScraper, FormItem

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MINISTRY_NAME = "중소벤처기업부"
LIST_URL = "https://www.mss.go.kr/site/smba/ex/bbs/List.do"
BASE_HOST = "https://www.mss.go.kr"
CB_IDX = "605"
MAX_PAGES = 200


class MssScraper(BaseGovScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.5

    def __init__(self, download_dir: str = "downloads/gov_contracts/중소벤처기업부"):
        super().__init__()
        self.download_dir = download_dir

    # ── 공개 메서드 ───────────────────────────────────────────────

    def fetch_items(self) -> list[FormItem]:
        """전체 페이지 순회 → FormItem 리스트 반환"""
        items: list[FormItem] = []

        for page in range(1, MAX_PAGES + 1):
            resp = None
            for attempt in range(3):
                time.sleep(self.request_delay if attempt == 0 else 3.0)
                try:
                    resp = self.session.get(
                        LIST_URL,
                        params={"cbIdx": CB_IDX, "pageIndex": str(page)},
                        timeout=30,
                        verify=False,
                    )
                    resp.raise_for_status()
                    break
                except requests.RequestException as e:
                    if attempt == 2:
                        print(f"[MSS] 페이지 {page} 요청 실패 (3회 재시도 후 포기): {e}")
                        resp = None
            if resp is None:
                break

            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = self._parse_rows(soup)

            if not rows:
                break

            items.extend(rows)

        return items

    # ── 내부 메서드 ───────────────────────────────────────────────

    def _parse_rows(self, soup: BeautifulSoup) -> list[FormItem]:
        tbody = soup.find("tbody")
        if not tbody:
            return []

        rows = tbody.find_all("tr")
        if not rows:
            return []

        items: list[FormItem] = []
        for tr in rows:
            # mobile td(마지막) 제외 — class="mobile" 인 td 건너뜀
            tds = [td for td in tr.find_all("td") if "mobile" not in (td.get("class") or [])]
            if len(tds) < 5:
                continue

            # 제목
            title_td = tds[1]
            title = title_td.get_text(strip=True)
            if not title:
                continue

            # 담당부서
            department = tds[2].get_text(strip=True)

            # 등록일
            registered_date = tds[4].get_text(strip=True)

            # 첨부파일 data-href
            file_td = tds[3]
            span = file_td.select_one("span.single-file[data-href]")
            if not span:
                continue

            data_href = span.get("data-href", "")
            file_url = BASE_HOST + data_href if data_href.startswith("/") else data_href

            # 파일 확장자: streFileNm 끝에서 추출 (UUID.ext 형식)
            m = re.search(r'streFileNm=[\w\-]+\.([a-zA-Z0-9]{2,5})', data_href)
            file_ext = m.group(1).lower() if m else ""

            items.append(
                FormItem(
                    ministry=MINISTRY_NAME,
                    title=title,
                    file_name="",   # UUID이므로 제목 기준 필터를 위해 비워둠
                    file_url=file_url,
                    source_url=LIST_URL + f"?cbIdx={CB_IDX}",
                    registered_date=registered_date,
                    department=department,
                    file_ext=file_ext,
                )
            )

        return items
