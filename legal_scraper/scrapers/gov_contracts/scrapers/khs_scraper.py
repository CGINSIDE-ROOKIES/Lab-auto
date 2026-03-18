"""
국가유산청 통합검색 스크래퍼 (Playwright)

검색 AJAX URL:
  https://search.khs.go.kr/srch_org/search/search_sub.jsp
  ?home=homepage&subHome=0&sort=2&searchField=1&page={N}&query={keyword}

- 결과: div.sch_list 파싱
- 파일 링크: a.file-link[href*='jsDownGosi'] 또는 a[href*='DownloadGosi']
- 파일명: em.file-link-subject 텍스트
- 다운로드 URL: https://jikimi.khs.go.kr/jikimi/servlet/DownloadGosi?idNum={idNum}
  jsDownGosi('base64') → base64.decode → strip → idNum
- 페이지네이션: page=N, 결과 없으면 종료
"""
from __future__ import annotations

import base64
import re
import time
import urllib.parse

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from ..base_playwright_scraper import BasePlaywrightScraper
from ..base_scraper import FormItem
from ..utils.file_filter import CONTRACT_KEYWORDS

MINISTRY_NAME = "국가유산청"
SEARCH_HOST = "https://search.khs.go.kr"
KHS_HOST = "https://www.khs.go.kr"
AJAX_URL = f"{SEARCH_HOST}/srch_org/search/search_sub.jsp"
DOWNLOAD_HOST = "https://jikimi.khs.go.kr"
DOWNLOAD_PATH = "/jikimi/servlet/DownloadGosi"


def _decode_idnum(b64_param: str) -> str:
    """jsDownGosi 파라미터(이중 base64) → idNum (숫자 문자열)"""
    try:
        # 1차 디코딩 → 또 다른 base64 문자열
        step1 = base64.b64decode(b64_param.strip()).decode("utf-8", errors="replace").strip()
        # 2차 디코딩 → 실제 idNum
        step2 = base64.b64decode(step1.strip()).decode("utf-8", errors="replace").strip()
        return step2
    except Exception:
        return b64_param.strip()


class KhsScraper(BasePlaywrightScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.5

    def __init__(self, download_dir: str = "downloads/gov_contracts/국가유산청"):
        super().__init__()
        self.download_dir = download_dir

    def _scrape_page(self, page: Page) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        for keyword in CONTRACT_KEYWORDS:
            page_num = 1
            while True:
                url = (
                    f"{AJAX_URL}"
                    f"?home=homepage&subHome=0&sort=2&searchField=1"
                    f"&page={page_num}"
                    f"&query={urllib.parse.quote(keyword)}"
                )
                page.goto(url, wait_until="networkidle", timeout=30000)
                time.sleep(1)

                soup = BeautifulSoup(page.content(), "html.parser")
                sch_lists = soup.find_all("div", class_="sch_list")
                if not sch_lists:
                    break

                found_any = False
                for div in sch_lists:
                    # 제목 링크
                    h5 = div.find("h5")
                    title_a = h5.find("a", href=True) if h5 else None
                    if not title_a:
                        continue

                    title = re.sub(r'\s+', ' ', title_a.get_text(strip=True))
                    source_url = title_a.get("href", "")
                    if not source_url.startswith("http"):
                        source_url = KHS_HOST + source_url

                    # 날짜
                    date_span = div.find("span")
                    registered_date = ""
                    if date_span:
                        date_text = date_span.get_text(strip=True)
                        m = re.search(r'\d{4}-\d{2}-\d{2}', date_text)
                        registered_date = m.group(0) if m else date_text

                    # 파일 링크 추출
                    file_lis = div.find_all("li", class_="file")
                    if not file_lis:
                        file_lis = div.find_all("li", class_=lambda c: c and "file" in " ".join(c) if c else False)

                    for li in file_lis:
                        fa = li.find("a", class_="file-link")
                        if not fa:
                            fa = li.find("a", href=True)
                        if not fa:
                            continue

                        href = fa.get("href", "")
                        onclick = fa.get("onclick", "") or ""
                        # href와 onclick 모두 확인 (jsDownGosi는 href에 있을 수 있음)
                        combined = href + " " + onclick

                        # 파일명
                        file_name_tag = fa.find("em", class_="file-link-subject")
                        file_name = file_name_tag.get_text(strip=True) if file_name_tag else fa.get_text(strip=True)
                        file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

                        # 다운로드 URL 구성
                        if "DownloadGosi" in href and not href.startswith("javascript"):
                            file_url = href if href.startswith("http") else DOWNLOAD_HOST + href
                        elif "jsDownGosi" in combined:
                            m = re.search(r"jsDownGosi\(['\"](.+?)['\"]\)", combined, re.DOTALL)
                            if m:
                                id_num = _decode_idnum(m.group(1))
                                file_url = f"{DOWNLOAD_HOST}{DOWNLOAD_PATH}?idNum={urllib.parse.quote(id_num)}"
                            else:
                                continue
                        else:
                            continue

                        dedup_key = file_url
                        if dedup_key in seen:
                            continue
                        seen.add(dedup_key)
                        found_any = True

                        all_items.append(FormItem(
                            ministry=MINISTRY_NAME,
                            title=title,
                            file_name=file_name,
                            file_url=file_url,
                            source_url=source_url,
                            registered_date=registered_date,
                            file_ext=file_ext,
                        ))

                if not found_any:
                    break

                # 다음 페이지 확인
                pager = soup.find("div", class_="page")
                if pager:
                    last_page = 1
                    page_links = pager.find_all("a", href=lambda h: h and "goPage" in (h or ""))
                    if page_links:
                        try:
                            last_page = max(
                                int(re.search(r'goPage\((\d+)\)', a.get("href", "")).group(1))
                                for a in page_links
                                if re.search(r'goPage\((\d+)\)', a.get("href", ""))
                            )
                        except Exception:
                            pass
                    if page_num >= last_page:
                        break
                else:
                    break

                page_num += 1

        return all_items
