"""
국세청 세무서식 스크래퍼 (유형 B — 페이지 순회)

목록 URL: https://www.nts.go.kr/nts/ad/nf/nltFormatTotalApiList.do?mi=40178&pageIndex={N}

페이지네이션 특이사항:
  pageIndex=N 요청 시 '처음 N개' 행을 누적 반환 (일반 페이지 개념과 다름).
  → CHUNK_SIZE=100씩 요청하여 이전 total보다 새 행이 없으면 종료.
  → 예: pageIndex=100 → 행 1~100, pageIndex=200 → 행 1~200 (중 101~200이 신규)

첨부파일: law.go.kr 도메인 링크 (LSW/flDownload.do 또는 DRF/lawService.do)
"""
from __future__ import annotations

import ssl
import time
import urllib3
from bs4 import BeautifulSoup

import requests
from requests.adapters import HTTPAdapter

from ..base_scraper import BaseGovScraper, FormItem

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MINISTRY_NAME = "국세청"
LIST_URL = "https://www.nts.go.kr/nts/ad/nf/nltFormatTotalApiList.do"
LIST_PAGE_URL = f"{LIST_URL}?mi=40178"
MI = "40178"
CHUNK_SIZE = 100
MAX_CHUNKS = 500   # 최대 50,000건 안전장치


class _TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


class NtsScraper(BaseGovScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.5

    def __init__(self, download_dir: str = "downloads/gov_contracts/국세청"):
        super().__init__()
        self.download_dir = download_dir
        self.session.mount("https://", _TLSAdapter())

    def fetch_items(self) -> list[FormItem]:
        """
        pageIndex=CHUNK, CHUNK*2, ... 씩 늘려가며 신규 행만 파싱.
        신규 행이 0개면 전체 수집 완료로 간주하고 종료.
        """
        all_items: list[FormItem] = []
        prev_total = 0

        for chunk_num in range(1, MAX_CHUNKS + 1):
            page_index = chunk_num * CHUNK_SIZE
            time.sleep(self.request_delay)

            try:
                resp = self.session.get(
                    LIST_URL,
                    params={"mi": MI, "pageIndex": str(page_index)},
                    timeout=30,
                )
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"[NTS] pageIndex={page_index} 요청 실패: {e}")
                break

            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            tbody = soup.find("tbody")
            if not tbody:
                break

            all_rows = tbody.find_all("tr")
            current_total = len(all_rows)

            # 신규 행만 파싱
            new_rows = all_rows[prev_total:current_total]
            if not new_rows:
                break

            for tr in new_rows:
                item = self._parse_row(tr)
                if item:
                    all_items.append(item)

            prev_total = current_total

            # 마지막 청크: 신규 행이 CHUNK_SIZE보다 적으면 마지막 페이지
            if len(new_rows) < CHUNK_SIZE:
                break

        return all_items

    def _parse_row(self, tr) -> FormItem | None:
        tds = tr.find_all("td")
        if len(tds) < 6:
            return None

        # td[4]: 서식명
        title = tds[4].get_text(strip=True)
        if not title:
            return None

        # td[2]: 공포·발령일자
        registered_date = tds[2].get_text(strip=True)
        # YYYYMMDD → YYYY-MM-DD
        if len(registered_date) == 8 and registered_date.isdigit():
            registered_date = f"{registered_date[:4]}-{registered_date[4:6]}-{registered_date[6:]}"

        # td[1]: 구분 (법령서식 / 훈령고시서식)
        department = tds[1].get_text(strip=True)

        # td[5]: 첨부파일 링크 (law.go.kr)
        file_url = ""
        file_name = ""
        file_ext = ""
        source_url = ""

        for a in tds[5].find_all("a", href=True):
            href = a.get("href", "")
            if "law.go.kr" not in href:
                continue

            # HWP/PDF 다운로드 링크 우선 (flDownload.do)
            if "flDownload.do" in href:
                file_url = href
                img = a.find("img")
                if img:
                    src = img.get("src", "").lower()
                    alt = img.get("alt", "").lower()
                    for ext in ["hwpx", "hwp", "pdf", "xlsx", "xls", "zip", "docx", "doc"]:
                        if ext in src or ext in alt:
                            file_ext = ext
                            break
                break

            # HTML 뷰어 링크 (lawService.do) — 무시 (source_url은 NTS 목록 페이지 사용)

        if not file_url:
            return None

        # 파일명: 제목 + 확장자 (다운로드 URL에서 별도 추출 불가)
        if not file_name:
            file_name = f"{title}.{file_ext}" if file_ext else title

        return FormItem(
            ministry=MINISTRY_NAME,
            title=title,
            file_name=file_name,
            file_url=file_url,
            source_url=LIST_PAGE_URL,
            registered_date=registered_date,
            department=department,
            file_ext=file_ext,
        )
