"""
농림축산식품부 통합검색 스크래퍼 (requests)

POST https://www.mafra.go.kr/search/front/Search.jsp
  qt={keyword}, menu=첨부파일, nh=20, st=1, ...

- 결과: div#file_sc dl.C_Cts a → artclView.do 상세 페이지
- 상세 페이지: /bbs/.../download.do 링크 추출
- 페이지네이션: st 파라미터 (1-based, nh=20씩)
"""
from __future__ import annotations

import time
import urllib.parse

import requests
from bs4 import BeautifulSoup

from ..base_scraper import BaseGovScraper, FormItem
from ..utils.file_filter import CONTRACT_KEYWORDS

MINISTRY_NAME = "농림축산식품부"
BASE_URL = "https://www.mafra.go.kr"
SEARCH_URL = f"{BASE_URL}/search/front/Search.jsp"
NH = 20  # 페이지당 결과 수


class MafraScraper(BaseGovScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.5

    def __init__(self, download_dir: str = "downloads/gov_contracts/농림축산식품부"):
        super().__init__()
        self.download_dir = download_dir

    def _init_session(self) -> None:
        super()._init_session()
        self.session.verify = False
        self.session.headers.update({"Referer": SEARCH_URL})

    def fetch_items(self) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        for keyword in CONTRACT_KEYWORDS:
            start = 1
            while True:
                data = {
                    "qt": keyword,
                    "menu": "첨부파일",
                    "nh": str(NH),
                    "st": str(start),
                    "adv": "0",
                    "sw": "0",
                    "searchType": "0",
                    "sDate": "",
                    "eDate": "",
                    "sPeriod": "",
                    "rf": "",
                    "field": "",
                }
                time.sleep(self.request_delay)
                try:
                    resp = self._request_with_retry(
                        lambda: self.session.post(SEARCH_URL, data=data, timeout=30)
                    )
                    resp.raise_for_status()
                except Exception as e:
                    print(f"[MAFRA] POST 최종 실패: {e}")
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                file_sc = soup.find("div", id="file_sc")
                if not file_sc:
                    break

                dls = file_sc.find_all("dl", class_="C_Cts")
                if not dls:
                    break

                found_any = False
                for dl in dls:
                    a = dl.find("a", href=True)
                    if not a:
                        continue

                    article_url = a.get("href", "")
                    if not article_url.startswith("http"):
                        article_url = BASE_URL + article_url

                    if article_url in seen:
                        continue
                    seen.add(article_url)

                    list_title = a.get_text(strip=True)
                    file_name = list_title
                    file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

                    # 상세 페이지에서 실제 다운로드 링크 추출
                    file_url = article_url
                    registered_date = ""
                    try:
                        time.sleep(self.request_delay)
                        dresp = self._request_with_retry(
                            lambda: self.session.get(article_url, timeout=30)
                        )
                        dresp.raise_for_status()
                        dsoup = BeautifulSoup(dresp.text, "html.parser")

                        for dl_a in dsoup.find_all("a", href=True):
                            dl_href = dl_a.get("href", "")
                            if "download.do" in dl_href.lower():
                                file_url = dl_href if dl_href.startswith("http") else BASE_URL + dl_href
                                break

                        for tag in dsoup.find_all(["td", "span", "dd"]):
                            txt = tag.get_text(strip=True)
                            if any(x in txt for x in ["등록일", "작성일"]):
                                sib = tag.find_next_sibling()
                                if sib:
                                    registered_date = sib.get_text(strip=True)
                                break
                    except Exception as e:
                        print(f"[MAFRA] 상세 페이지 오류: {e}")

                    found_any = True
                    all_items.append(FormItem(
                        ministry=MINISTRY_NAME,
                        title=list_title,
                        file_name=file_name,
                        file_url=file_url,
                        source_url=article_url,
                        registered_date=registered_date,
                        file_ext=file_ext,
                    ))

                if not found_any or len(dls) < NH:
                    break

                start += NH

        return all_items
