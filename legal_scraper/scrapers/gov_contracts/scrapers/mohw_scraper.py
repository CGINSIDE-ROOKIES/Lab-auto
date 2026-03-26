"""
보건복지부 통합검색 스크래퍼 (Playwright)

검색 URL: https://www.mohw.go.kr/react/search/search.jsp
- React SPA: 검색창(input[name='query'])에 키워드 입력 → Enter
- 결과: ul.tsr_mohw_lst > li 구조, 카테고리 뱃지로 "자료" 구분
- 자료 더보기: button[value='DATA'] 클릭 → 전체 자료 목록
- 다운로드: button onclick="location.href='/boardDownload.es?bid=...&list_no=...&seq=...'"
"""
from __future__ import annotations

import re
import time

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from ..base_playwright_scraper import BasePlaywrightScraper
from ..base_scraper import FormItem
from ..utils.file_filter import CONTRACT_KEYWORDS

MINISTRY_NAME = "보건복지부"
BASE_URL = "https://www.mohw.go.kr"
SEARCH_URL = f"{BASE_URL}/react/search/search.jsp"

_FILE_EXTS = {"hwp", "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip", "hwpx"}


class MohwScraper(BasePlaywrightScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 2.0

    def __init__(self, download_dir: str = "downloads/gov_contracts/보건복지부"):
        super().__init__()
        self.download_dir = download_dir

    def _scrape_page(self, page: Page) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        for keyword in CONTRACT_KEYWORDS:
            self._search_keyword(page, keyword, seen, all_items)

        return all_items

    def _search_keyword(
        self,
        page: Page,
        keyword: str,
        seen: set[str],
        all_items: list[FormItem],
    ) -> None:
        try:
            page.goto(SEARCH_URL, wait_until="networkidle", timeout=30000)
        except Exception as e:
            print(f"[MOHW] 페이지 로드 실패: {e}")
            return
        time.sleep(3)

        # 검색창 입력 및 제출
        try:
            loc = page.locator("input[name='query']").first
            loc.wait_for(state="visible", timeout=8000)
            loc.fill(keyword)
            time.sleep(0.3)
            loc.press("Enter")
            page.wait_for_load_state("networkidle")
            time.sleep(3)
        except Exception as e:
            print(f"[MOHW] 검색 실패 (keyword={keyword}): {e}")
            return

        # "자료" 카테고리 더보기 클릭 → 자료 전용 결과 페이지로 전환
        try:
            more_btn = page.locator("button[value='DATA']").first
            more_btn.wait_for(state="visible", timeout=5000)
            more_btn.click()
            page.wait_for_load_state("networkidle")
            time.sleep(2)
        except Exception:
            pass  # 더보기 버튼이 없어도 현재 결과에서 파싱 진행

        # 페이지네이션 루프
        while True:
            soup = BeautifulSoup(page.content(), "html.parser")
            count_before = len(all_items)
            self._parse_data_items(soup, seen, all_items)

            # 더 이상 새 항목이 없으면 중단
            if len(all_items) == count_before:
                break

            # 다음 페이지 버튼 탐색
            next_btn = self._find_next_btn(page, soup)
            if not next_btn:
                break

            try:
                next_btn.click()
                page.wait_for_load_state("networkidle")
                time.sleep(2)
            except Exception:
                break

    def _find_next_btn(self, page: Page, soup: BeautifulSoup):
        """페이지네이션에서 '다음' 버튼 반환. 없으면 None."""
        # board_pager 또는 일반 pager 내 다음 링크
        for a_tag in soup.select(".board_pager a, .pager a, .pagination a, ul.paging a"):
            txt = a_tag.get_text(strip=True)
            if txt not in ("다음", ">", "▶", "next"):
                continue
            onclick = a_tag.get("onclick", "")
            href = a_tag.get("href", "")
            # onclick="goPage(N)" 또는 href="?pageNum=N" 패턴
            m = re.search(r"goPage\((\d+)\)|[?&]pageNum=(\d+)", onclick + href)
            if m:
                np = m.group(1) or m.group(2)
                candidates = [
                    f"a[onclick*='goPage({np})']",
                    f"a[href*='pageNum={np}']",
                ]
                for sel in candidates:
                    btn = page.locator(sel).first
                    try:
                        if btn.is_visible():
                            return btn
                    except Exception:
                        continue
            # onclick/href 패턴 없으면 직접 클릭
            try:
                direct = page.locator(f"a:text-is('{txt}')").first
                if direct.is_visible():
                    return direct
            except Exception:
                pass
        return None

    def _parse_data_items(
        self,
        soup: BeautifulSoup,
        seen: set[str],
        items: list[FormItem],
    ) -> None:
        """ul.tsr_mohw_lst에서 '자료' 카테고리 항목 파싱 → items에 추가."""
        for li in soup.select("ul.tsr_mohw_lst > li"):
            badge = li.select_one(".krds-badge")
            # 뱃지가 없거나 "자료"가 아닌 항목은 건너뜀
            if badge and badge.get_text(strip=True) != "자료":
                continue

            # 제목 / 소스 URL
            title_a = li.select_one("dl dt a")
            if not title_a:
                continue
            raw_title = re.sub(r"\s+", " ", title_a.get_text()).strip()
            source_href = title_a.get("href", "")
            source_url = (
                source_href if source_href.startswith("http")
                else BASE_URL + source_href if source_href.startswith("/")
                else ""
            )

            # 날짜
            date_tag = li.select_one(".i-date")
            registered_date = date_tag.get_text(strip=True).rstrip(".") if date_tag else ""

            # 다운로드 버튼: onclick="location.href='/boardDownload.es?...'"
            dl_buttons = li.select("button[onclick*='boardDownload.es']")
            if not dl_buttons:
                # 다운로드 버튼이 없으면 소스 URL만 등록 (키워드 매칭 시)
                if source_url and any(kw in raw_title for kw in CONTRACT_KEYWORDS):
                    dedup_key = source_url + raw_title
                    if dedup_key not in seen:
                        seen.add(dedup_key)
                        items.append(FormItem(
                            source=MINISTRY_NAME,
                            title=raw_title,
                            file_name="",
                            file_url=source_url,
                            source_url=source_url,
                            registered_date=registered_date,
                            file_format="",
                        ))
                continue

            for btn in dl_buttons:
                onclick = btn.get("onclick", "")
                m = re.search(r"location\.href=['\"]([^'\"]+)['\"]", onclick)
                if not m:
                    continue
                dl_path = m.group(1)
                file_url = BASE_URL + dl_path if dl_path.startswith("/") else dl_path

                # 파일명: title_a 텍스트가 "파일명.hwp" 형태인 경우 그대로 사용
                # 아니면 버튼 텍스트(예: "HWP 다운로드")에서 확장자 추출 후 조합
                if "." in raw_title and raw_title.rsplit(".", 1)[-1].lower() in _FILE_EXTS:
                    file_name = raw_title
                    file_ext = raw_title.rsplit(".", 1)[-1].lower()
                    title = raw_title.rsplit(".", 1)[0]
                else:
                    title = raw_title
                    btn_text = btn.get_text(strip=True)
                    ext_m = re.match(r"^([A-Za-z]+)\s*다운로드", btn_text)
                    file_ext = ext_m.group(1).lower() if ext_m else ""
                    file_name = f"{title}.{file_ext}" if file_ext else title

                dedup_key = file_url
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                items.append(FormItem(
                    source=MINISTRY_NAME,
                    title=title,
                    file_name=file_name,
                    file_url=file_url,
                    source_url=source_url,
                    registered_date=registered_date,
                    file_format=file_ext,
                ))
