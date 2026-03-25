"""
행정중심복합도시건설청 표준계약서 스크래퍼 (requests)

검색 URL: https://naacc.go.kr/WEB/contents/N4040200000.do
- GET 검색: schM=list, page=N, viewCount=10, schStr=키워드
- 결과 테이블: table.listType tbody tr
    → td.boardTitle a[onclick="fn_goView('ID')"] : 상세 ID
    → tds[3] : 담당부서
    → tds[4] : 등록일 (YYYY.MM.DD)
- 상세 페이지: schM=view&id=XXX
    → a.fileName : 첨부파일명 + href=/afile/fileDownload/XXX
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..base_scraper import BaseGovScraper, FormItem
from ..utils.file_filter import CONTRACT_KEYWORDS

MINISTRY_NAME = "행정중심복합도시건설청"
BASE_URL = "https://naacc.go.kr"
BOARD_URL = f"{BASE_URL}/WEB/contents/N4040200000.do"
VIEW_COUNT = 10


class NaaccScraper(BaseGovScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.0

    # ── 수집 진입점 ───────────────────────────────────────────────────

    def fetch_items(self) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen_urls: set[str] = set()

        for keyword in CONTRACT_KEYWORDS:
            self._search_keyword(keyword, seen_urls, all_items)

        return all_items

    # ── 키워드별 페이지 순회 ──────────────────────────────────────────

    def _search_keyword(
        self,
        keyword: str,
        seen_urls: set[str],
        all_items: list[FormItem],
    ) -> None:
        page = 1
        while True:
            params = {
                "schM": "list",
                "page": str(page),
                "viewCount": str(VIEW_COUNT),
                "schStr": keyword,
            }
            try:
                soup = self.parse_html(BOARD_URL, params=params)
            except Exception as e:
                print(f"[{MINISTRY_NAME}] 목록 요청 실패 (page={page}): {e}")
                break

            rows = self._parse_list_rows(soup)
            if not rows:
                break

            for row_id, title, dept, date in rows:
                items = self._fetch_detail(row_id, title, dept, date, seen_urls)
                all_items.extend(items)

                if self.on_progress:
                    self.on_progress(len(all_items), f"{len(all_items)}건 수집 중...")

            if len(rows) < VIEW_COUNT:
                break
            page += 1

    # ── 목록 파싱 ─────────────────────────────────────────────────────

    def _parse_list_rows(
        self, soup: BeautifulSoup
    ) -> list[tuple[str, str, str, str]]:
        """목록 테이블에서 (id, title, department, date) 튜플 리스트 반환"""
        rows = []
        for tr in soup.select("table.listType tbody tr"):
            # onclick="fn_goView('66001')" 에서 ID 추출
            title_a = tr.select_one("td.boardTitle a")
            if not title_a:
                continue
            onclick = title_a.get("onclick", "")
            m = re.search(r"fn_goView\('(\d+)'\)", onclick)
            if not m:
                continue
            row_id = m.group(1)

            span = title_a.select_one("span.tit")
            title = span.get_text(strip=True) if span else title_a.get_text(strip=True)

            tds = tr.find_all("td")
            dept = ""
            date = ""
            if len(tds) >= 5:
                # mShow800 레이블(모바일 전용) 제거 후 순수 텍스트 추출
                dept = re.sub(r"^담당부서\s*:\s*\xa0?", "", tds[3].get_text(strip=True))
                raw_date = re.sub(r"^등록일\s*:\s*\xa0?", "", tds[4].get_text(strip=True))
                date = raw_date.replace(".", "-")  # YYYY.MM.DD → YYYY-MM-DD

            rows.append((row_id, title, dept, date))
        return rows

    # ── 상세 페이지 첨부파일 수집 ─────────────────────────────────────

    def _fetch_detail(
        self,
        row_id: str,
        title: str,
        dept: str,
        date: str,
        seen_urls: set[str],
    ) -> list[FormItem]:
        params = {"schM": "view", "id": row_id}
        try:
            soup = self.parse_html(BOARD_URL, params=params)
        except Exception as e:
            print(f"[{MINISTRY_NAME}] 상세 페이지 실패 (id={row_id}): {e}")
            return []

        items = []
        for a in soup.select("a.fileName"):
            href = a.get("href", "").strip()
            if not href:
                continue
            file_url = BASE_URL + href if href.startswith("/") else href
            if file_url in seen_urls:
                continue
            seen_urls.add(file_url)

            file_name = a.get_text(strip=True)
            file_ext = ""
            if "." in file_name:
                parts = file_name.rsplit(".", 1)
                if len(parts[1]) <= 5:
                    file_ext = parts[1].lower()

            items.append(FormItem(
                ministry=MINISTRY_NAME,
                title=title,
                file_name=file_name,
                file_url=file_url,
                source_url=f"{BOARD_URL}?schM=view&id={row_id}",
                registered_date=date,
                department=dept,
                file_ext=file_ext,
            ))
        return items
