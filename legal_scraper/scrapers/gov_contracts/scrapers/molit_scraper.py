"""
국토교통부 정책자료 스크래퍼

목록 URL: POST https://www.molit.go.kr/USR/policyData/m_34681/lst.jsp
  params: search={keyword}, srch_usr_nm=Y, srch_usr_titl=Y, srch_usr_ctnt=Y, psize=10, lcmspage={N}
  → 빈 tbody 또는 행 없으면 종료

상세 URL: GET https://www.molit.go.kr/USR/policyData/m_34681/dtl.jsp?id={id}
  → /portal/common/download/DownloadMltm2.jsp?FilePath=...&FileName=파일명.ext 링크에서 첨부파일 추출

필터: 붙임파일이 반드시 있고 그 파일명에 CONTRACT_KEYWORDS 포함 시만 수집
"""
from __future__ import annotations

import ssl
import time
import urllib.parse
import urllib3
from bs4 import BeautifulSoup

import requests
from requests.adapters import HTTPAdapter

from ..base_scraper import BaseGovScraper, FormItem
from ..utils.file_filter import CONTRACT_KEYWORDS

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MINISTRY_NAME = "국토교통부"
BASE_HOST = "https://www.molit.go.kr"
LIST_URL = f"{BASE_HOST}/USR/policyData/m_34681/lst.jsp"
DETAIL_URL = f"{BASE_HOST}/USR/policyData/m_34681/dtl.jsp"
DOWNLOAD_PREFIX = "/portal/common/download/DownloadMltm2.jsp"
PAGE_SIZE = 10


class _TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs["ssl_context"] = ctx
        return super().init_poolmanager(*args, **kwargs)


class MolitScraper(BaseGovScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.5

    def __init__(self, download_dir: str = "downloads/gov_contracts/국토교통부"):
        super().__init__()
        self.download_dir = download_dir
        self.session.mount("https://", _TLSAdapter())
        self.session.headers.update({
            "Referer": LIST_URL,
            "Origin": BASE_HOST,
        })

    def fetch_items(self) -> list[FormItem]:
        """
        CONTRACT_KEYWORDS마다 목록 전 페이지 순회 → 상세 페이지에서 첨부파일 추출.
        붙임파일이 있고 파일명에 키워드 포함된 것만 반환.
        """
        all_items: list[FormItem] = []
        seen: set[str] = set()  # (detail_id, file_url) 중복 방지

        for keyword in CONTRACT_KEYWORDS:
            page = 1
            while True:
                resp = None
                for attempt in range(3):
                    time.sleep(self.request_delay if attempt == 0 else 3.0)
                    try:
                        resp = self.session.post(
                            LIST_URL,
                            data={
                                "srch_usr_nm": "Y",
                                "srch_usr_titl": "Y",
                                "srch_usr_ctnt": "Y",
                                "search": keyword,
                                "psize": str(PAGE_SIZE),
                                "lcmspage": str(page),
                            },
                            timeout=30,
                            verify=False,
                        )
                        resp.raise_for_status()
                        break
                    except requests.RequestException as e:
                        if attempt == 2:
                            print(f"[MOLIT] {keyword} p{page} 요청 실패: {e}")
                if resp is None:
                    break

                resp.encoding = "utf-8"
                soup = BeautifulSoup(resp.text, "html.parser")
                tbody = soup.find("tbody")
                if not tbody:
                    break

                rows = tbody.find_all("tr")
                if not rows:
                    break

                for tr in rows:
                    items = self._process_row(tr, keyword, seen)
                    all_items.extend(items)

                # 마지막 페이지 판단: 행이 PAGE_SIZE 미만이면 종료
                if len(rows) < PAGE_SIZE:
                    break

                page += 1

        return all_items

    def _process_row(self, tr, keyword: str, seen: set) -> list[FormItem]:
        """목록 행에서 상세 페이지 ID를 추출하고 첨부파일을 가져온다."""
        tds = tr.find_all("td")
        if len(tds) < 4:
            return []

        # 제목 링크에서 id 추출
        title_link = tr.find("a", href=True)
        if not title_link:
            return []

        href = title_link.get("href", "")
        # id 파라미터 추출
        parsed = urllib.parse.urlparse(href)
        params = urllib.parse.parse_qs(parsed.query)
        detail_id = params.get("id", [""])[0]
        if not detail_id:
            return []

        title = title_link.get_text(strip=True)
        registered_date = tds[-1].get_text(strip=True) if tds else ""

        # 상세 페이지에서 첨부파일 추출
        resp = None
        for attempt in range(3):
            time.sleep(self.request_delay if attempt == 0 else 3.0)
            try:
                resp = self.session.get(
                    DETAIL_URL,
                    params={"id": detail_id},
                    timeout=30,
                    verify=False,
                )
                resp.raise_for_status()
                break
            except requests.RequestException as e:
                if attempt == 2:
                    print(f"[MOLIT] 상세 id={detail_id} 요청 실패: {e}")
        if resp is None:
            return []

        resp.encoding = "utf-8"
        detail_soup = BeautifulSoup(resp.text, "html.parser")
        source_url = f"{DETAIL_URL}?id={detail_id}"

        items = []
        for a in detail_soup.find_all("a", href=True):
            file_href = a.get("href", "")
            if DOWNLOAD_PREFIX not in file_href:
                continue

            # FileName 파라미터에서 파일명 추출
            fp = urllib.parse.urlparse(file_href)
            fp_params = urllib.parse.parse_qs(fp.query)
            file_name = urllib.parse.unquote(fp_params.get("FileName", [""])[0])
            if not file_name:
                file_name = a.get_text(strip=True)

            file_url = file_href if file_href.startswith("http") else BASE_HOST + file_href
            dedup_key = (detail_id, file_url)
            if dedup_key in seen:
                continue

            # 파일명에 키워드가 있는지 확인
            if not any(kw in file_name for kw in CONTRACT_KEYWORDS):
                continue

            seen.add(dedup_key)
            file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

            items.append(FormItem(
                source=MINISTRY_NAME,
                title=title,
                file_name=file_name,
                file_url=file_url,
                source_url=source_url,
                registered_date=registered_date,
                file_format=file_ext,
            ))

        return items

    def run(self) -> list[FormItem]:
        """fetch_items()가 이미 키워드 필터를 적용하므로 그대로 반환."""
        return self.fetch_items()
