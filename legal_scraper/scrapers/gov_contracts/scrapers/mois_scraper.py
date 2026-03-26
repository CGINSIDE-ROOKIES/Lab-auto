"""
행정안전부 통합검색 스크래퍼 (Playwright)

검색 URL: https://www.mois.go.kr/srch.jsp?query={keyword}
- 첨부파일 탭(#Result_첨부파일) 하위 ul.C_Cts li.txt a 파싱
- 더보기 클릭으로 추가 항목 로딩
- 각 항목은 게시물 상세 페이지 링크 → 방문해서 실제 파일 다운로드 URL 추출
"""
from __future__ import annotations

import re
import time
import urllib.parse

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from ..base_playwright_scraper import BasePlaywrightScraper
from ..base_scraper import FormItem
from ..utils.file_filter import CONTRACT_KEYWORDS

MINISTRY_NAME = "행정안전부"
BASE_URL = "https://www.mois.go.kr"
SEARCH_URL = f"{BASE_URL}/srch.jsp"


class MoisScraper(BasePlaywrightScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.5

    def __init__(self, download_dir: str = "downloads/gov_contracts/행정안전부"):
        super().__init__()
        self.download_dir = download_dir

    def _scrape_page(self, page: Page) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        for keyword in CONTRACT_KEYWORDS:
            url = f"{SEARCH_URL}?query={urllib.parse.quote(keyword)}"
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # 더보기 버튼 반복 클릭 (최대 20회)
            for _ in range(20):
                try:
                    more_btn = page.query_selector(
                        "a[onclick*='doCollection'][onclick*='file'], "
                        ".thebogi a, p.thebogi a"
                    )
                    if not more_btn:
                        break
                    # 버튼이 보이지 않으면 scroll into view
                    more_btn.scroll_into_view_if_needed()
                    time.sleep(0.5)
                    more_btn.click(timeout=5000)
                    time.sleep(1.5)
                except Exception:
                    break

            soup = BeautifulSoup(page.content(), "html.parser")

            # 첨부파일 섹션 찾기
            file_section = soup.find("ul", id="Result_첨부파일")
            if not file_section:
                # fallback: 첨부파일 텍스트 포함 섹션
                for ul in soup.find_all("ul", class_="Cmenu_Title"):
                    if "첨부파일" in ul.get_text():
                        file_section = ul
                        break

            if not file_section:
                continue

            # C_Cts ul은 file_section의 형제 또는 부모의 형제
            c_cts_ul = None
            parent = file_section.parent
            if parent:
                c_cts_ul = parent.find("ul", class_="C_Cts")
            if not c_cts_ul:
                # fallback: 페이지 전체에서 찾기
                c_cts_ul = soup.find("ul", class_="C_Cts")

            if not c_cts_ul:
                continue

            file_items = c_cts_ul.find_all("li", class_="txt")
            if not file_items:
                file_items = c_cts_ul.find_all("li")

            for li in file_items:
                a = li.find("a", href=True)
                if not a:
                    continue

                file_name = re.sub(r'\s+', ' ', a.get_text()).strip()
                # 파일 크기 정보 제거: [238.3 KB] 또는 \xa0[ ... ]
                file_name = re.sub(r'\s*[\[\xa0].*?\]', '', file_name).strip()
                article_href = a.get("href", "")
                if not article_href or not file_name:
                    continue

                article_url = article_href if article_href.startswith("http") else BASE_URL + article_href
                dedup_key = article_url + file_name
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

                # 상세 페이지에서 실제 다운로드 URL 추출
                file_url = article_url  # fallback
                registered_date = ""
                try:
                    time.sleep(self.request_delay)
                    page.goto(article_url, wait_until="networkidle", timeout=30000)
                    time.sleep(0.5)
                    detail_soup = BeautifulSoup(page.content(), "html.parser")

                    # 파일 다운로드 링크 찾기
                    for dl_a in detail_soup.find_all("a", href=True):
                        dl_href = dl_a.get("href", "")
                        if any(x in dl_href for x in ["downloadFile", "download", "Download", "atchFile"]):
                            file_url = dl_href if dl_href.startswith("http") else BASE_URL + dl_href
                            dl_text = re.sub(r'\s+', ' ', dl_a.get_text()).strip()
                            dl_text = re.sub(r'\s*[\[\xa0].*?\]', '', dl_text).strip()
                            if dl_text and "." in dl_text:
                                file_name = dl_text
                                file_ext = file_name.rsplit(".", 1)[-1].lower()
                            break

                    # 등록일 추출
                    date_tag = detail_soup.find(class_=lambda c: c and "date" in " ".join(c).lower() if c else False)
                    if date_tag:
                        registered_date = date_tag.get_text(strip=True)

                    # 목록으로 복귀
                    page.goto(url, wait_until="networkidle", timeout=30000)
                    time.sleep(0.5)
                except Exception as e:
                    print(f"[MOIS] 상세 페이지 오류: {e}")

                all_items.append(FormItem(
                    source=MINISTRY_NAME,
                    title=file_name,
                    file_name=file_name,
                    file_url=file_url,
                    source_url=article_url,
                    registered_date=registered_date,
                    file_format=file_ext,
                ))

        return all_items
