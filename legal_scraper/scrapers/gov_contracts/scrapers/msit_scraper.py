"""
과학기술정보통신부 표준계약서 스크래퍼 (requests)

검색 URL: https://www.msit.go.kr/search/ko/searchKo.do
- POST 검색: qt=키워드, addDt=File (첨부파일 필터), pageNum=N
- 결과는 script 내 fcFile() 함수의 let dataJson={...} 에 JSON으로 임베딩
  → rows[].fields: file_dc(파일명), file_extsn(확장자), url(상세페이지), pstg_bgng_dt(날짜)
- 키워드 매칭 row만 상세 페이지(bbs/view.do) 방문
- 상세 페이지: ul.down_file li → fn_download(atchFileNo, fileOrd, ext) onclick 파싱
- 다운로드: POST /ssm/file/fileDown.do?atchFileNo=X&fileOrd=Y&fileBtn=A
"""
from __future__ import annotations

import json
import re
import time

import requests
from bs4 import BeautifulSoup

from ..base_scraper import BaseGovScraper, FormItem
from ..utils.file_filter import CONTRACT_KEYWORDS

MINISTRY_NAME = "과학기술정보통신부"
BASE_URL = "https://www.msit.go.kr"
SEARCH_URL = f"{BASE_URL}/search/ko/searchKo.do"
DOWNLOAD_URL = f"{BASE_URL}/ssm/file/fileDown.do"


class MsitScraper(BaseGovScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.0

    def __init__(self):
        super().__init__()

    def _init_session(self) -> None:
        super()._init_session()
        self.session.headers.update({
            "Referer": BASE_URL,
            "Origin": BASE_URL,
        })

    def fetch_items(self) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen_file_urls: set[str] = set()
        seen_detail_urls: set[str] = set()

        for keyword in CONTRACT_KEYWORDS:
            self._search_keyword(keyword, seen_file_urls, seen_detail_urls, all_items)

        return all_items

    # ── 검색 페이지 순회 ─────────────────────────────────────────────

    def _search_keyword(
        self,
        keyword: str,
        seen_file_urls: set[str],
        seen_detail_urls: set[str],
        all_items: list[FormItem],
    ) -> None:
        page_num = 1
        total_pages: int | None = None

        while True:
            data_json = self._post_search(keyword, page_num)
            result = data_json.get("result", {})
            rows = result.get("rows", [])
            total_count = result.get("total_count", 0)

            if not rows:
                break

            # 총 페이지 수 (첫 페이지에서 계산)
            if total_pages is None:
                per_page = len(rows)
                total_pages = (total_count + per_page - 1) // per_page if per_page else 1

            for row in rows:
                self._process_row(row, seen_file_urls, seen_detail_urls, all_items)

            if total_pages and page_num >= total_pages:
                break
            page_num += 1

    def _post_search(self, keyword: str, page_num: int) -> dict:
        """POST 검색 → HTML에서 fcFile() 내 let dataJson 추출."""
        empty = {"result": {"total_count": 0, "rows": []}}
        data = {
            "dateSt": "",
            "dateEn": "",
            "targetTb": "",
            "rangeCon": "",
            "orderBy": "0",
            "addDt": "File",
            "pageNum": str(page_num),
            "qtBefore": keyword,
            "qt": keyword,
        }
        try:
            time.sleep(self.request_delay)
            resp = self._request_with_retry(
                lambda: self.session.post(SEARCH_URL, data=data, verify=False, timeout=30)
            )
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return self._extract_fc_file_json(resp.text)
        except Exception as e:
            print(f"[MSIT] 최종 실패 (kw={keyword}, page={page_num}): {e}")
            return empty

    def _extract_fc_file_json(self, html: str) -> dict:
        """script 내 function fcFile() { let dataJson = {...}; } 에서 JSON 추출."""
        empty = {"result": {"total_count": 0, "rows": []}}

        # fcFile() 함수 위치 탐색
        m = re.search(r"function\s+fcFile\s*\(\s*\)", html)
        if not m:
            return empty

        # fcFile 함수 내에서 let dataJson = { 탐색
        search_start = m.start()
        m2 = re.search(r"let\s+dataJson\s*=\s*(\{)", html[search_start:])
        if not m2:
            return empty

        json_start = search_start + m2.start(1)

        # 중괄호 깊이 카운팅으로 JSON 끝 위치 탐색
        depth = 0
        i = json_start
        in_str = False
        escape = False
        while i < len(html):
            c = html[i]
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"' and not escape:
                in_str = not in_str
            elif not in_str:
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        json_str = html[json_start: i + 1]
                        try:
                            return json.loads(json_str)
                        except json.JSONDecodeError:
                            return empty
            i += 1

        return empty

    # ── 검색 결과 row 처리 ────────────────────────────────────────────

    def _process_row(
        self,
        row: dict,
        seen_file_urls: set[str],
        seen_detail_urls: set[str],
        all_items: list[FormItem],
    ) -> None:
        fields = row.get("fields", {})

        # 파일명: HTML 태그 제거
        file_dc = re.sub(r"<[^>]+>", "", fields.get("file_dc", "")).strip()

        url_path = fields.get("url", "")
        source_url = BASE_URL + url_path if url_path.startswith("/") else url_path

        # 날짜: "2024-10-31 12:00:00" → "2024-10-31"
        raw_date = fields.get("pstg_bgng_dt", "")
        registered_date = raw_date[:10] if raw_date else ""

        if source_url in seen_detail_urls:
            return
        seen_detail_urls.add(source_url)

        self._collect_detail_items(source_url, registered_date, seen_file_urls, all_items)
        time.sleep(self.request_delay)

    # ── 상세 페이지 파싱 ──────────────────────────────────────────────

    def _collect_detail_items(
        self,
        source_url: str,
        registered_date: str,
        seen_file_urls: set[str],
        all_items: list[FormItem],
    ) -> None:
        """상세 페이지 방문 → ul.down_file에서 키워드 매칭 파일 수집."""
        if not source_url:
            return
        try:
            resp = self.session.get(source_url, verify=False, timeout=30)
            resp.raise_for_status()
            resp.encoding = "utf-8"
        except Exception as e:
            print(f"[MSIT] 상세 페이지 로드 실패 {source_url}: {e}")
            return

        soup = BeautifulSoup(resp.text, "html.parser")

        # 게시글 제목: og:title 우선, 없으면 <title> 태그에서 사이트명 제거
        post_title = ""
        og = soup.select_one('meta[property="og:title"]')
        if og and og.get("content"):
            post_title = og["content"].strip()
        if not post_title:
            title_tag = soup.find("title")
            if title_tag and title_tag.string:
                # "제목 - 과학기술정보통신부" → 앞 부분만
                post_title = re.sub(r"\s*[-|]\s*과학기술정보통신부.*$", "", title_tag.string).strip()

        # 날짜 보완
        if not registered_date:
            for sel in [".date", ".reg_date", ".write_date"]:
                tag = soup.select_one(sel)
                if tag:
                    registered_date = tag.get_text(strip=True)
                    break

        for li in soup.select("ul.down_file li, ul.down_file_new li"):
            # 파일명: ico_file_* 클래스 a 태그 텍스트
            a_file = li.select_one("a[class*='ico_file']")
            file_name = a_file.get_text(strip=True) if a_file else ""

            # fn_download(atchFileNo, fileOrd, ext) 추출
            a_down = li.select_one("a.down[onclick*='fn_download']")
            if not a_down:
                continue
            onclick = a_down.get("onclick", "")
            m = re.search(r"fn_download\('(\d+)',\s*'(\d+)',\s*'([^']+)'\)", onclick)
            if not m:
                continue

            atch_file_no = m.group(1)
            file_ord = m.group(2)
            file_ext = m.group(3).lower()

            if not file_name:
                file_name = f"{post_title}.{file_ext}" if file_ext else post_title

            file_url = (
                f"{DOWNLOAD_URL}"
                f"?atchFileNo={atch_file_no}"
                f"&fileOrd={file_ord}"
                f"&fileBtn=A"
            )

            if file_url in seen_file_urls:
                continue
            seen_file_urls.add(file_url)

            all_items.append(FormItem(
                ministry=MINISTRY_NAME,
                title=post_title or file_name,
                file_name=file_name,
                file_url=file_url,
                source_url=source_url,
                registered_date=registered_date,
                file_ext=file_ext,
            ))
