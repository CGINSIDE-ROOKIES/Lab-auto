"""
성평등가족부 통합검색 스크래퍼 (requests 기반)

검색: POST /as/asl/as_asl_s001.do
  - params: searchTerm={kw}, category={cat}, currentPage={N}, searcharea=15,
            searchType=AND, searchareaGroup=IDX_TITLE,IDX_CONT
  - 카테고리: NEWS(알림·소식), SUB(정책정보), INFO(민원·참여·정보공개), EDU(기타)
  - 전체 페이지 수: hidden input[name="pageSize"] 값
결과 구조:
  - li > div.search_title a : 제목 (strong 태그 포함 텍스트)
  - span.display_pc          : 등록일 (YYYY-MM-DD)
  - dd.siteFile ol li a.iconFileDown[onclick]
      → fn_fileDownload(atfileSn, atfileSeq, atfileDir, atfileSysNm, atfileOrgNm)
다운로드: POST /file/download.do?filedir={atfileDir}&sysnm={atfileSysNm}&orgnm={encoded_orgnm}
  form body: atfileSn={atfileSn}&atfileSeq={atfileSeq}
  file_url  : https://www.mogef.go.kr/file/download.do?filedir={atfileDir}&sysnm={atfileSysNm}
"""
from __future__ import annotations

import re
import time
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from ..base_scraper import BaseGovScraper, FormItem
from ..utils.file_filter import CONTRACT_KEYWORDS

MINISTRY_NAME = "성평등가족부"
BASE_URL = "https://www.mogef.go.kr"
SEARCH_URL = f"{BASE_URL}/as/asl/as_asl_s001.do"
SOURCE_URL = SEARCH_URL

# 검색할 카테고리 코드
CATEGORIES = ["NEWS", "SUB", "INFO", "ETC", "EDU"]

_BASE_PARAMS = {
    "searchType": "AND",
    "searcharea": "15",
    "engcategory": "ENG",
    "sortType": "",
    "reSearch": "",
    "pagingStart": "0",
    "pagingEnd": "0",
    "pageSize": "0",
    "realSize": "0",
    "subTotal": "1",
    "total": "1",
    "cateCheck": "",
    "detailCheck": "",
    "searchareaGroup": "IDX_TITLE,IDX_CONT",
    "startDt": "",
    "endDt": "",
}


class MogefScraper(BaseGovScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.0

    def __init__(self, download_dir: str = "downloads/gov_contracts/성평등가족부"):
        super().__init__()
        self.download_dir = download_dir

    def _init_session(self) -> None:
        super()._init_session()
        self.session.verify = False
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": SOURCE_URL,
            "Origin": BASE_URL,
        })

    def fetch_items(self) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        for keyword in CONTRACT_KEYWORDS:
            for category in CATEGORIES:
                self._scrape_category(keyword, category, seen, all_items)

        return all_items

    def _scrape_category(
        self,
        keyword: str,
        category: str,
        seen: set[str],
        all_items: list[FormItem],
    ) -> None:
        page = 1
        while True:
            soup, total_pages = self._fetch_page(keyword, category, page)
            if soup is None:
                break

            self._parse_items(soup, keyword, seen, all_items)

            if page >= total_pages:
                break
            page += 1
            time.sleep(self.request_delay)

    def _fetch_page(
        self,
        keyword: str,
        category: str,
        page: int,
    ) -> tuple[BeautifulSoup | None, int]:
        """검색 결과 페이지 요청 → (soup, 전체 페이지 수)."""
        data = {
            **_BASE_PARAMS,
            "searchTerm": keyword,
            "totalTerm": keyword,
            "currentPage": str(page),
            "category": category,
        }
        try:
            resp = self._request_with_retry(
                lambda: self.session.post(SEARCH_URL, data=data, timeout=30, verify=False)
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"[MOGEF] 최종 실패 (kw={keyword}, cat={category}, page={page}): {e}")
            return None, 0

        soup = BeautifulSoup(resp.content, "html.parser")

        ps_input = soup.find("input", {"name": "pageSize"})
        total_pages = 1
        if ps_input:
            try:
                val = int(ps_input.get("value", "1") or "1")
                total_pages = max(val, 1)
            except ValueError:
                pass

        return soup, total_pages

    def _parse_items(
        self,
        soup: BeautifulSoup,
        keyword: str,
        seen: set[str],
        items: list[FormItem],
    ) -> None:
        """soup에서 li 아이템을 순회해 파일 목록 추출"""
        # 각 section 내 결과 li 순회
        for li in soup.select("div.searchSection li"):
            # 서버 HTML에서 dt 또는 div로 올 수 있음
            title_el = li.select_one("dt.search_title a, div.search_title a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)

            date_el = li.select_one("span.display_pc")
            registered_date = date_el.get_text(strip=True) if date_el else ""

            # dd.siteFile > ol > li > a.iconFileDown
            for file_li in li.select("dd.siteFile ol li"):
                dl_a = file_li.select_one("a.iconFileDown")
                if not dl_a:
                    continue

                # href="javascript:fn_fileDownload(...)" 패턴
                onclick = dl_a.get("href", "") or dl_a.get("onclick", "")
                params = _parse_fn_filedownload(onclick)
                if not params:
                    continue

                atfile_sn, atfile_seq, atfile_dir, atfile_sysnm, atfile_orgnm = params

                file_name = atfile_orgnm
                file_url = (
                    f"{BASE_URL}/file/download.do"
                    f"?filedir={quote(atfile_dir)}&sysnm={quote(atfile_sysnm)}"
                    f"&orgnm={quote(atfile_orgnm)}"
                )
                file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

                dedup_key = f"{atfile_sn}_{atfile_seq}"
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                items.append(FormItem(
                    source=MINISTRY_NAME,
                    title=title,
                    file_name=file_name,
                    file_url=file_url,
                    source_url=SOURCE_URL,
                    registered_date=registered_date,
                    file_format=file_ext,
                    download_post_data={"atfileSn": atfile_sn, "atfileSeq": atfile_seq},
                ))


def _parse_fn_filedownload(onclick: str) -> tuple[str, str, str, str, str] | None:
    """
    fn_fileDownload('sn','seq','dir','sysnm','orgnm') 파싱
    → (atfileSn, atfileSeq, atfileDir, atfileSysNm, atfileOrgNm)
    """
    m = re.search(
        r"fn_fileDownload\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*\)",
        onclick,
    )
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
