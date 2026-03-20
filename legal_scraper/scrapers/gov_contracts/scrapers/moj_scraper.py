"""
법무부 표준계약서 스크래퍼 (requests)

검색 URL: https://moj.go.kr/moj/3521/subview.do
- POST 검색: qt=키워드, collection=v_search_atchmnfl(자료), searchField=title(제목 필터)
- 페이지네이션: startCount=0,10,20,..., viewCount=10
- 결과: li.total-search-item
    → p.tit.m-hide  : 파일명(+확장자 포함)
    → span.i-date   : 날짜
    → a.download    : 다운로드 URL (/bbs/moj/{boardId}/{fileId}/download.do)
    → a[href*=artclView.do] : 상세 페이지 URL

※ 법무부 전용 키워드(MOJ_CONTRACT_KEYWORDS)를 사용하며,
   전역 CONTRACT_KEYWORDS(계약/약정서)와 완전히 독립적으로 동작합니다.
   새 키워드 추가 시 MOJ_CONTRACT_KEYWORDS 리스트에만 추가하면 됩니다.
"""
from __future__ import annotations

import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from ..base_scraper import BaseGovScraper, FormItem

MINISTRY_NAME = "법무부"
BASE_URL = "https://www.moj.go.kr"
SEARCH_URL = f"{BASE_URL}/moj/3521/subview.do"

# ── 법무부 전용 키워드 ────────────────────────────────────────────────
# 전역 CONTRACT_KEYWORDS 와 독립적으로 관리됩니다.
# 새 키워드가 필요하면 이 리스트에만 추가하세요.
MOJ_CONTRACT_KEYWORDS: list[str] = [
    "계약서",
]

VIEW_COUNT = 10


class MojScraper(BaseGovScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.0

    _POST_HEADERS = {
        "Origin": BASE_URL,
        "Referer": SEARCH_URL,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    def __init__(self):
        super().__init__()
        self._init_session()

    def _init_session(self) -> None:
        """세션 초기화 + 쿠키 확보 (ConnectionReset 후 재시도 시에도 호출)"""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "close",
        })
        try:
            self.session.get(SEARCH_URL, verify=False, timeout=30)
        except Exception:
            pass  # GET 실패 시 POST 단계에서 재시도

    # ── 키워드 필터 재정의 (전역 CONTRACT_KEYWORDS 와 독립) ─────────────

    def filter_by_keyword(self, items: list[FormItem]) -> list[FormItem]:
        from ..utils.file_filter import EXCLUDE_TITLE_KEYWORDS
        return [
            item for item in items
            if any(kw in (item.file_name or item.title) for kw in MOJ_CONTRACT_KEYWORDS)
            and item.file_ext.lower() not in self._EXCLUDED_EXTS
            and not any(kw in item.title for kw in EXCLUDE_TITLE_KEYWORDS)
        ]

    # ── 수집 진입점 ───────────────────────────────────────────────────

    def fetch_items(self) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen_file_urls: set[str] = set()

        for keyword in MOJ_CONTRACT_KEYWORDS:
            self._search_keyword(keyword, seen_file_urls, all_items)

        return all_items

    # ── 키워드별 페이지 순회 ──────────────────────────────────────────

    def _search_keyword(
        self,
        keyword: str,
        seen_file_urls: set[str],
        all_items: list[FormItem],
    ) -> None:
        start_count = 0
        while True:
            soup = self._post_search(keyword, start_count)
            items_on_page = self._parse_items(soup, seen_file_urls)
            all_items.extend(items_on_page)

            if self.on_progress:
                self.on_progress(len(all_items), f"{len(all_items)}건 수집 중...")

            if not items_on_page:
                break

            # 마지막 page-link 의 doPaging 값으로 최대 startCount 확인
            max_start = self._get_max_start_count(soup)
            if max_start is not None and start_count >= max_start:
                break

            if len(items_on_page) < VIEW_COUNT:
                break

            start_count += VIEW_COUNT

    def _post_search(self, keyword: str, start_count: int, max_retries: int = 3) -> BeautifulSoup:
        data = {
            "startCount": str(start_count),
            "viewCount": str(VIEW_COUNT),
            "startDate": "1970.01.01",
            "endDate": datetime.today().strftime("%Y.%m.%d"),
            "mStartDate": "",
            "mEndDate": "",
            "siteId": "moj",
            "sort": "RANK/DESC,DATE/DESC",
            "collection": "v_search_atchmnfl",
            "qt": keyword,
            "searchField": "title",
            "reQuery": "2",
            "realQuery": "",
            "mSearchField": "ALL",
            "mReQuery": "1",
            "mRealQuery": "",
        }
        for attempt in range(max_retries):
            if attempt > 0:
                wait = 2 ** attempt
                print(f"[MOJ] 재시도 {attempt}/{max_retries - 1}, {wait}초 대기 "
                      f"(startCount={start_count})")
                time.sleep(wait)
                self._init_session()  # 세션 재생성 후 쿠키 재확보

            try:
                time.sleep(self.request_delay)
                resp = self.session.post(
                    SEARCH_URL, data=data, verify=False, timeout=30,
                    headers=self._POST_HEADERS,
                )
                resp.raise_for_status()
                resp.encoding = "utf-8"
                return BeautifulSoup(resp.text, "html.parser")
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[MOJ] 요청 실패 (startCount={start_count}, "
                          f"시도={attempt + 1}): {e}")
                    continue
                print(f"[MOJ] 최종 실패 (startCount={start_count}): {e}")
                return BeautifulSoup("", "html.parser")  # 빈 soup → 루프 종료

    # ── 결과 파싱 ─────────────────────────────────────────────────────

    def _parse_items(
        self,
        soup: BeautifulSoup,
        seen_file_urls: set[str],
    ) -> list[FormItem]:
        items: list[FormItem] = []

        for li in soup.select("li.total-search-item"):
            # 날짜 (YYYY.MM.DD → YYYY-MM-DD)
            date_tag = li.select_one("span.i-date")
            registered_date = ""
            if date_tag:
                registered_date = date_tag.get_text(strip=True).replace(".", "-")

            # 파일명 / 제목: span.high-light 강조 태그 포함 전체 텍스트
            tit_tag = li.select_one("p.tit")
            if not tit_tag:
                tit_tag = li.select_one("p.tit.m-hide")
            if not tit_tag:
                continue
            raw_name = tit_tag.get_text(strip=True)

            # 상세 페이지 URL
            detail_a = li.select_one("a[href*='artclView.do']")
            source_url = ""
            if detail_a:
                href = detail_a.get("href", "")
                source_url = BASE_URL + href if href.startswith("/") else href

            # 다운로드 URL
            download_a = li.select_one("a[class*='download']")
            if not download_a:
                continue
            file_url = download_a.get("href", "").strip()
            if not file_url:
                continue
            if file_url.startswith("/"):
                file_url = BASE_URL + file_url

            if file_url in seen_file_urls:
                continue
            seen_file_urls.add(file_url)

            # 파일명·확장자 분리
            file_name = raw_name
            file_ext = ""
            if "." in raw_name:
                parts = raw_name.rsplit(".", 1)
                if len(parts[1]) <= 5:  # 확장자로 보이는 짧은 suffix
                    file_ext = parts[1].lower()

            title = raw_name.rsplit(".", 1)[0] if file_ext else raw_name

            items.append(FormItem(
                ministry=MINISTRY_NAME,
                title=title,
                file_name=file_name,
                file_url=file_url,
                source_url=source_url,
                registered_date=registered_date,
                file_ext=file_ext,
            ))

        return items

    # ── 페이지네이션 헬퍼 ────────────────────────────────────────────

    def _get_max_start_count(self, soup: BeautifulSoup) -> int | None:
        """페이지 링크 중 가장 큰 startCount 값을 반환."""
        max_val: int | None = None
        for a in soup.select("a.page-link"):
            href = a.get("href", "")
            m = re.search(r"doPaging\('(\d+)'\)", href)
            if m:
                val = int(m.group(1))
                if max_val is None or val > max_val:
                    max_val = val
        return max_val
