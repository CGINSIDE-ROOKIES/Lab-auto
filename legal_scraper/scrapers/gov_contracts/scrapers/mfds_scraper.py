"""
식품의약품안전처 훈령전문 스크래퍼 (requests 기반)

목록: GET /brd/m_212/list.do?srchWord={keyword}&srchTp=0&page={N}&...
  - 건수/페이지: div.bbs_data_info "전체 N건, 현재페이지 P/T"
  - 게시글 링크: a[href*='./view.do?seq=']
상세: GET /brd/m_212/view.do?seq={seq}
  - 파일 영역: div.bv_file_box ul.bbs_file_view_list li div.bbs_file_cont
    - 파일명: strong 텍스트
    - 다운로드: a.bbs_icon_filedown[href]
다운로드: /brd/m_212/down.do?brd_id=data0006&seq={seq}&data_tp=A&file_seq={N}
"""
from __future__ import annotations

import re
import time
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup

from ..base_scraper import BaseGovScraper, FormItem
from ..utils.file_filter import CONTRACT_KEYWORDS

MINISTRY_NAME = "식품의약품안전처"
BASE_URL = "https://www.mfds.go.kr"
LIST_URL = f"{BASE_URL}/brd/m_212/list.do"
DETAIL_BASE = f"{BASE_URL}/brd/m_212"
SOURCE_URL = f"{BASE_URL}/brd/m_212/list.do"

_LIST_PARAMS = {
    "multi_itm_seq": "0",
    "board_id": "data0006",
    "seq": "",
    "itm_seq_1": "",
    "data_stts_gubun": "C9999",
    "srchTp": "0",
}


class MfdsScraper(BaseGovScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.0

    def __init__(self, download_dir: str = "downloads/gov_contracts/식품의약품안전처"):
        super().__init__()
        self.download_dir = download_dir

    def _init_session(self) -> None:
        super()._init_session()
        self.session.verify = False
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "Referer": SOURCE_URL,
        })

    def fetch_items(self) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        for keyword in CONTRACT_KEYWORDS:
            self._scrape_keyword(keyword, seen, all_items)

        return all_items

    def _scrape_keyword(
        self,
        keyword: str,
        seen: set[str],
        all_items: list[FormItem],
    ) -> None:
        page = 1
        while True:
            seqs, total_pages = self._fetch_list_page(keyword, page)
            if not seqs:
                break

            for seq in seqs:
                self._process_detail(seq, keyword, seen, all_items)
                time.sleep(self.request_delay)

            if page >= total_pages:
                break
            page += 1
            time.sleep(self.request_delay)

    def _fetch_list_page(self, keyword: str, page: int) -> tuple[list[str], int]:
        """목록 페이지 → (seq 목록, 전체 페이지 수)"""
        params = {**_LIST_PARAMS, "srchWord": keyword, "page": str(page)}
        try:
            resp = self._request_with_retry(
                lambda: self.session.get(LIST_URL, params=params, timeout=30, verify=False)
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"[MFDS] 목록 조회 실패 (keyword={keyword}, page={page}): {e}")
            return [], 0

        soup = BeautifulSoup(resp.text, "html.parser")

        # 전체 페이지 수: "전체 N건, 현재페이지 P/T"
        total_pages = 1
        info = soup.select_one(".bbs_data_info")
        if info:
            m = re.search(r"현재페이지\s*<b>\d+</b>\s*/\s*<b>(\d+)</b>", str(info))
            if m:
                total_pages = int(m.group(1))

        # 게시글 seq 추출 — ./view.do?seq=N 패턴
        seqs: list[str] = []
        for a in soup.select("a[href*='view.do']"):
            href = a.get("href", "")
            # 설문조사 등 외부 링크 제외
            if not (href.startswith("./view.do") or href.startswith("/brd/m_212/view.do")):
                continue
            m = re.search(r"[?&]seq=(\d+)", href)
            if m:
                seq = m.group(1)
                if seq not in seqs:
                    seqs.append(seq)

        return seqs, total_pages

    def _process_detail(
        self,
        seq: str,
        keyword: str,
        seen: set[str],
        items: list[FormItem],
    ) -> None:
        """상세 페이지에서 파일 목록 추출"""
        detail_url = f"{DETAIL_BASE}/view.do?seq={seq}&srchWord={keyword}&srchTp=0&multi_itm_seq=0"
        try:
            resp = self._request_with_retry(
                lambda: self.session.get(detail_url, timeout=30, verify=False)
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"[MFDS] 상세 조회 실패 (seq={seq}): {e}")
            return

        soup = BeautifulSoup(resp.text, "html.parser")

        # 제목
        title_el = soup.select_one(".bv_title")
        title = title_el.get_text(strip=True) if title_el else ""

        # 등록일
        registered_date = ""
        for li in soup.select(".bv_txt01 ul li"):
            span = li.select_one("span")
            if span and "등록일" in span.get_text():
                text = li.get_text(strip=True)
                registered_date = text.replace("등록일", "").strip()
                break

        # 첨부파일 영역: div.bv_file_box ul.bbs_file_view_list li
        for li in soup.select(".bv_file_box .bbs_file_view_list li"):
            cont = li.select_one(".bbs_file_cont")
            if not cont:
                continue

            # 파일명
            name_el = cont.select_one("strong")
            file_name = name_el.get_text(strip=True) if name_el else ""

            # 다운로드 링크
            dl_a = cont.select_one("a.bbs_icon_filedown")
            if not dl_a:
                continue
            href = dl_a.get("href", "")
            if not href:
                continue

            # 절대 URL 구성: ./down.do?... → BASE_URL/brd/m_212/down.do?...
            if href.startswith("./"):
                file_url = f"{DETAIL_BASE}/{href[2:]}"
            elif href.startswith("/"):
                file_url = BASE_URL + href
            else:
                file_url = href

            # 확장자
            file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

            dedup_key = file_url
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            items.append(FormItem(
                source=MINISTRY_NAME,
                title=title,
                file_name=file_name,
                file_url=file_url,
                source_url=detail_url,
                registered_date=registered_date,
                file_format=file_ext,
            ))
