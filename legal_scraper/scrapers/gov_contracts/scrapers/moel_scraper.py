"""
고용노동부 정책자료 스크래퍼 (requests)

목록 URL: https://www.moel.go.kr/policy/policydata/list.do?searchText={keyword}&pageIndex={N}
- table tbody tr 파싱
- 첨부파일 아이콘(ri-attachment-2) 있는 항목만 상세 페이지 방문
- 상세 URL: /policy/policydata/view.do?bbs_seq={id}
- 파일 URL: /common/downloadFile.do?file_seq=...&bbs_seq=...&bbs_id=29&file_ext=...
"""
from __future__ import annotations

import time
import urllib.parse

from bs4 import BeautifulSoup

from ..base_scraper import BaseGovScraper, FormItem
from ..utils.file_filter import CONTRACT_KEYWORDS

MINISTRY_NAME = "고용노동부"
BASE_URL = "https://www.moel.go.kr"
LIST_URL = f"{BASE_URL}/policy/policydata/list.do"
DETAIL_URL = f"{BASE_URL}/policy/policydata/view.do"


class MoelScraper(BaseGovScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.5

    def __init__(self, download_dir: str = "downloads/gov_contracts/고용노동부"):
        super().__init__()
        self.download_dir = download_dir

    def _init_session(self) -> None:
        super()._init_session()
        self.session.verify = False

    def fetch_items(self) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        for keyword in CONTRACT_KEYWORDS:
            page_num = 1
            while True:
                url = f"{LIST_URL}?searchText={urllib.parse.quote(keyword)}&pageIndex={page_num}"
                time.sleep(self.request_delay)
                try:
                    resp = self._request_with_retry(
                        lambda: self.session.get(url, timeout=30)
                    )
                    resp.raise_for_status()
                except Exception as e:
                    print(f"[MOEL] 목록 요청 최종 실패: {e}")
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                tbody = soup.find("tbody")
                if not tbody:
                    break

                rows = tbody.find_all("tr")
                if not rows:
                    break

                page_had_items = False
                for tr in rows:
                    tds = tr.find_all("td")
                    if len(tds) < 4:
                        continue

                    # 첨부파일 아이콘 확인
                    if not tr.find("i", class_="ri-attachment-2"):
                        continue

                    # 제목 및 bbs_seq 추출
                    title_td = tr.find("td", class_="txt_left")
                    if not title_td:
                        title_td = tds[1] if len(tds) > 1 else None
                    if not title_td:
                        continue

                    a = title_td.find("a", href=True)
                    if not a:
                        continue

                    title = a.get_text(strip=True)
                    href = a.get("href", "")
                    bbs_seq = ""
                    if "bbs_seq=" in href:
                        bbs_seq = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("bbs_seq", [""])[0]

                    registered_date = ""
                    for td in tds:
                        txt = td.get_text(strip=True)
                        import re
                        if re.match(r'\d{4}\.\d{2}\.\d{2}', txt):
                            registered_date = txt
                            break

                    department = ""
                    for td in tds:
                        txt = td.get_text(strip=True)
                        if txt and txt not in [title, registered_date] and not txt.isdigit() and "." not in txt:
                            department = txt
                            break

                    if not bbs_seq:
                        continue

                    source_url = f"{DETAIL_URL}?bbs_seq={bbs_seq}"
                    if bbs_seq in seen:
                        continue
                    seen.add(bbs_seq)

                    # 상세 페이지에서 파일 URL 추출
                    time.sleep(self.request_delay)
                    try:
                        dresp = self._request_with_retry(
                            lambda: self.session.get(source_url, timeout=30)
                        )
                        dresp.raise_for_status()
                    except Exception as e:
                        print(f"[MOEL] 상세 페이지 최종 실패: {e}")
                        continue

                    detail_soup = BeautifulSoup(dresp.text, "html.parser")
                    file_links = detail_soup.find_all("a", href=lambda h: h and "downloadFile.do" in h)

                    page_had_items = True
                    for fa in file_links:
                        file_href = fa.get("href", "")
                        file_name = fa.get_text(strip=True)
                        if not file_name:
                            file_name = file_href.rsplit("/", 1)[-1].split("?")[0]

                        # 다운로드 링크 중복 제거 (같은 파일이 두 번 나오는 경우)
                        if file_href in seen:
                            continue
                        seen.add(file_href)

                        file_url = file_href if file_href.startswith("http") else BASE_URL + file_href
                        qp = urllib.parse.parse_qs(urllib.parse.urlparse(file_href).query)
                        file_ext = qp.get("file_ext", [""])[0].lower()
                        if not file_ext and "." in file_name:
                            file_ext = file_name.rsplit(".", 1)[-1].lower()

                        all_items.append(FormItem(
                            ministry=MINISTRY_NAME,
                            title=title,
                            file_name=file_name,
                            file_url=file_url,
                            source_url=source_url,
                            registered_date=registered_date,
                            department=department,
                            file_ext=file_ext,
                        ))

                # 다음 페이지 확인
                next_btn = soup.find("a", class_=lambda c: c and "next" in " ".join(c) if c else False)
                if not next_btn or not page_had_items:
                    break

                page_num += 1

        return all_items
