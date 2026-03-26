"""
관세청 통합검색 스크래퍼 (requests + BS4)

검색 URL: https://www.customs.go.kr/search/search.jsp
- POST searchField=SJ (제목 기준), collection=attach (첨부파일)
- startCount 로 페이지네이션 (0, 10, 20, …)
- div.resultBox > ul.kcs_file > li 파싱
  - 파일명/URL: a.kcs_file_t[title], a.kcs_file_t[href]
  - 날짜:       span.date

"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..base_scraper import BaseGovScraper, FormItem
from ..utils.file_filter import CONTRACT_KEYWORDS

MINISTRY_NAME = "관세청"
BASE_URL = "https://www.customs.go.kr"
SEARCH_URL = f"{BASE_URL}/search/search.jsp"
PAGE_SIZE = 10

# 총 건수 파싱: "총 <strong>42</strong>건" 또는 숫자만 포함된 요소
_TOTAL_RE = re.compile(r"총\s*([\d,]+)\s*건")


def _parse_total(soup: BeautifulSoup) -> int:
    """검색 결과 총 건수 반환 (파싱 실패 시 0)"""
    # 텍스트 전체에서 "총 N건" 패턴 탐색
    text = soup.get_text(" ", strip=True)
    m = _TOTAL_RE.search(text)
    if m:
        return int(m.group(1).replace(",", ""))
    return 0


def _parse_items(soup: BeautifulSoup, keyword: str) -> list[FormItem]:
    items: list[FormItem] = []

    for li in soup.select("div.resultBox ul.kcs_file li"):
        a_tag = li.select_one("a.kcs_file_t")
        if not a_tag:
            continue

        file_name = (a_tag.get("title") or a_tag.get_text(strip=True)).strip()
        href = a_tag.get("href", "").strip()
        if not href:
            continue

        file_url = BASE_URL + href if href.startswith("/") else href
        file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

        date_tag = li.select_one("span.date")
        reg_dt = date_tag.get_text(strip=True).replace(".", "-") if date_tag else ""
        # YYYY-MM-DD. → YYYY-MM-DD
        reg_dt = reg_dt.rstrip("-").strip()

        source_url = f"{SEARCH_URL}?query={keyword}&searchField=SJ&collection=attach"

        items.append(FormItem(
            source=MINISTRY_NAME,
            title=file_name,
            file_name=file_name,
            file_url=file_url,
            source_url=source_url,
            registered_date=reg_dt,
            file_format=file_ext,
        ))

    return items


class CustomsScraper(BaseGovScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.0

    def _post(self, keyword: str, start_count: int) -> str:
        data = {
            "query": keyword,
            "searchField": "SJ",
            "collection": "attach",
            "range": "A",
            "startCount": str(start_count),
            "mode": "basic",
            "boardSort": "RANK",
            "webpageSort": "RANK",
            "attachSort": "RANK",
            "menuSort": "RANK",
            "businessSort": "RANK",
            "mainInfoSort": "RANK",
            "mainAdminSort": "RANK",
            "mainNoticeSort": "RANK",
            "mainIntroSort": "RANK",
        }
        return self._request_with_retry(
            lambda: self.session.post(SEARCH_URL, data=data, timeout=30)
        ).text

    # ── BaseGovScraper 구현 ────────────────────────────────────────

    def fetch_items(self) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        for keyword in CONTRACT_KEYWORDS:
            print(f"[CUSTOMS] 키워드={keyword} 검색 시작")
            try:
                first_html = self._post(keyword, 0)
            except Exception as e:
                print(f"[CUSTOMS] 1페이지 요청 실패 ({keyword}): {e}")
                continue

            soup = BeautifulSoup(first_html, "html.parser")
            total = _parse_total(soup)
            total_pages = max(1, -(-total // PAGE_SIZE))  # ceiling division
            print(f"[CUSTOMS] 총 {total}건 / {total_pages}페이지")

            for page_idx in range(total_pages):
                start_count = page_idx * PAGE_SIZE
                try:
                    page_html = first_html if page_idx == 0 else self._post(keyword, start_count)
                except Exception as e:
                    print(f"[CUSTOMS] 페이지 {page_idx + 1} 요청 실패: {e}")
                    break

                page_soup = BeautifulSoup(page_html, "html.parser") if page_idx > 0 else soup
                items = _parse_items(page_soup, keyword)

                if not items:
                    print(f"[CUSTOMS] {page_idx + 1}페이지 결과 없음, 중단")
                    break

                for item in items:
                    if item.file_url not in seen:
                        seen.add(item.file_url)
                        all_items.append(item)

                if self.on_progress:
                    self.on_progress(len(all_items), f"{keyword} {page_idx + 1}/{total_pages}")
                print(f"[CUSTOMS] {keyword} {page_idx + 1}/{total_pages} - 누적 {len(all_items)}건")

        return all_items
