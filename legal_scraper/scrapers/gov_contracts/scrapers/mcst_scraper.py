"""
문화체육관광부 표준계약서 스크래퍼 (curl_cffi — chrome TLS 흉내)

목록: GET/POST https://www.mcst.go.kr/site/s_data/generalData/dataList.jsp
  - GET  pMenuCD=0405050000          (1페이지)
  - POST pMenuCD=0405050000, pCurrentPage=N  (N≥2)
  - 결과: tbody tr → href dataView.jsp?pMenuCD=...&pSeq=N
  - 전체 페이지 수: onclick 내 movePage(N, ...) 최대값

상세: GET dataView.jsp?pMenuCD=0405050000&pSeq=N
  - onclick: file_download('URL인코딩원본명', '저장명', 'menuCD')
  - 다운로드: /site/common/file/fileDownload.jsp
      form POST  pFileNm, pSaveNm, pPath, pFlag

※ requests/curl_cffi 로 동작 (Playwright 불필요)
  mcst.go.kr 서버가 Playwright 헤드리스 크롬을 TLS 수준에서 차단하므로
  curl_cffi chrome 지문으로 우회합니다.
"""
from __future__ import annotations

import re
import time
import urllib.parse

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from ..base_scraper import BaseGovScraper, FormItem
from ..utils.file_filter import CONTRACT_KEYWORDS

MINISTRY_NAME = "문화체육관광부"
BASE_URL = "https://www.mcst.go.kr"
LIST_URL = f"{BASE_URL}/site/s_data/generalData/dataList.jsp"
VIEW_URL = f"{BASE_URL}/site/s_data/generalData/dataView.jsp"
MENU_CD = "0405050000"

_FILE_DL_RE = re.compile(
    r"file_download\('([^']+)',\s*'([^']+)',\s*'([^']+)'\)"
)
_MOVE_PAGE_RE = re.compile(r"movePage\((\d+)")


class McstScraper(BaseGovScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.5

    def __init__(self, download_dir: str = "downloads/gov_contracts/문화체육관광부"):
        super().__init__()
        self.download_dir = download_dir
        # curl_cffi 세션으로 교체 (chrome TLS 지문)
        self.session = cffi_requests.Session(impersonate="chrome")

    # ── 목록 페이지 ────────────────────────────────────────────────

    def _get_list_page(self, page_num: int) -> BeautifulSoup:
        time.sleep(self.request_delay)
        try:
            if page_num == 1:
                resp = self.session.get(
                    LIST_URL, params={"pMenuCD": MENU_CD}, timeout=30
                )
            else:
                resp = self.session.post(
                    LIST_URL,
                    data={
                        "pMenuCD": MENU_CD,
                        "pCurrentPage": str(page_num),
                        "pSeq": "",
                        "pSearchType": "",
                        "pSearchWord": "",
                    },
                    timeout=30,
                )
            resp.raise_for_status()
        except Exception as e:
            print(f"[MCST] 목록 페이지 {page_num} 실패: {e}")
            self.had_connection_error = True
            return BeautifulSoup("", "html.parser")
        return BeautifulSoup(resp.content, "html.parser")

    def _get_total_pages(self, soup: BeautifulSoup) -> int:
        pages = [
            int(m)
            for a in soup.find_all("a", onclick=True)
            for m in _MOVE_PAGE_RE.findall(a.get("onclick", ""))
        ]
        return max(pages) if pages else 1

    # ── 상세 페이지 ────────────────────────────────────────────────

    def _get_detail_page(self, p_seq: str) -> BeautifulSoup:
        time.sleep(self.request_delay)
        try:
            resp = self.session.get(
                VIEW_URL,
                params={"pMenuCD": MENU_CD, "pSeq": p_seq},
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"[MCST] 상세 페이지 pSeq={p_seq} 실패: {e}")
            return BeautifulSoup("", "html.parser")
        return BeautifulSoup(resp.content, "html.parser")

    # ── 수집 진입점 ───────────────────────────────────────────────

    def fetch_items(self) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        # 1단계: 전체 목록에서 pSeq 수집
        first_soup = self._get_list_page(1)
        total_pages = self._get_total_pages(first_soup)
        print(f"[MCST] 전체 {total_pages}페이지")

        row_data: list[tuple[str, str, str, str]] = []  # (pSeq, title, date, dept)
        for soup in [first_soup] + [self._get_list_page(p) for p in range(2, total_pages + 1)]:
            self._parse_list_rows(soup, row_data)

        print(f"[MCST] 목록 {len(row_data)}건 수집")

        # 2단계: 상세 페이지에서 파일 수집
        for p_seq, title, registered_date, department in row_data:
            detail_url = f"{VIEW_URL}?pMenuCD={MENU_CD}&pSeq={p_seq}"
            detail_soup = self._get_detail_page(p_seq)
            self._parse_detail_files(
                detail_soup, title, registered_date, department,
                detail_url, seen, all_items,
            )

            if self.on_progress:
                self.on_progress(len(all_items), f"{len(all_items)}건 수집 중...")

        return all_items

    def _parse_list_rows(
        self,
        soup: BeautifulSoup,
        row_data: list[tuple[str, str, str, str]],
    ) -> None:
        tbody = soup.find("tbody")
        if not tbody:
            return
        for tr in tbody.find_all("tr"):
            a_tag = tr.find("a", href=lambda h: h and "dataView.jsp" in (h or ""))
            if not a_tag:
                continue

            href = a_tag.get("href", "")
            m = re.search(r"pSeq=(\d+)", href)
            if not m:
                continue
            p_seq = m.group(1)

            title_p = a_tag.find("p", class_="tit")
            title = title_p.get_text(strip=True) if title_p else a_tag.get_text(strip=True)

            tds = tr.find_all("td")
            registered_date = tds[3].get_text(strip=True).rstrip(".") if len(tds) > 3 else ""
            department = tds[2].get_text(strip=True) if len(tds) > 2 else ""

            row_data.append((p_seq, title, registered_date, department))

    def _parse_detail_files(
        self,
        soup: BeautifulSoup,
        title: str,
        registered_date: str,
        department: str,
        detail_url: str,
        seen: set[str],
        items: list[FormItem],
    ) -> None:
        for fa in soup.find_all("a", onclick=_FILE_DL_RE.pattern if False else True):
            onclick = fa.get("onclick", "")
            m = _FILE_DL_RE.search(onclick)
            if not m:
                continue

            p_file_nm = m.group(1)   # URL 인코딩된 원본 파일명
            p_save_nm = m.group(2)   # 서버 저장 파일명
            p_path = m.group(3)      # menuCD

            file_url = (
                f"{BASE_URL}/site/common/file/fileDownload.jsp"
                f"?pFileNm={p_file_nm}&pSaveNm={p_save_nm}"
                f"&pPath={p_path}&pFlag="
            )

            file_name = urllib.parse.unquote_plus(p_file_nm)
            file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

            if file_url in seen:
                continue
            seen.add(file_url)

            items.append(FormItem(
                ministry=MINISTRY_NAME,
                title=title,
                file_name=file_name,
                file_url=file_url,
                source_url=detail_url,
                registered_date=registered_date,
                department=department,
                file_ext=file_ext,
            ))
