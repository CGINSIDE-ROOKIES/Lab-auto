"""
국가보훈부 통합검색 스크래퍼 (curl_cffi — chrome TLS 흉내)

검색 URL: https://www.mpva.go.kr/search/search.jsp
- GET query=키워드&collection=minwon (민원/보상 탭)
- startCount 10 단위 증가로 페이지네이션, 결과 없으면 종료
- 검색결과: ul.list li > div.board_title a (상세 링크)
- 상세페이지: ul.p-attach a.p-attach__link → ./downloadBbsFile.do?atchmnflNo=N
  파일명: 링크 텍스트에서 아이콘 접두어("hwp 문서" 등) 제거

※ 국가보훈부 전용 키워드(MPVA_CONTRACT_KEYWORDS)를 사용하며,
   전역 CONTRACT_KEYWORDS(계약/약정서)와 완전히 독립적으로 동작합니다.
   새 키워드 추가 시 MPVA_CONTRACT_KEYWORDS 리스트에만 추가하면 됩니다.
"""
from __future__ import annotations

import re
import time

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from ..base_scraper import BaseGovScraper, FormItem

MINISTRY_NAME = "국가보훈부"
BASE_URL = "https://www.mpva.go.kr"
SEARCH_URL = f"{BASE_URL}/search/search.jsp"
DETAIL_BASE = f"{BASE_URL}/mpva"
PAGE_SIZE = 10

MPVA_CONTRACT_KEYWORDS: list[str] = [
    "계약서",
]

# "hwp 문서", "pdf 문서", "xlsx 문서" 등 아이콘 접두어 제거
_ICON_PREFIX_RE = re.compile(r"^[\w]+\s+문서\s*", re.IGNORECASE)


def _clean_filename(raw: str) -> str:
    """링크 텍스트에서 아이콘 접두어 제거 후 파일명 반환"""
    return _ICON_PREFIX_RE.sub("", raw).strip()


def _parse_total(soup: BeautifulSoup) -> int:
    """h2 내 em.em_orange 텍스트에서 총 건수 반환"""
    em = soup.select_one("section.result_group h2 em.em_orange")
    if em:
        try:
            return int(em.get_text(strip=True).replace(",", ""))
        except ValueError:
            pass
    return 0


def _parse_detail_links(soup: BeautifulSoup) -> list[str]:
    """검색결과 목록에서 상세페이지 URL 리스트 반환"""
    links = []
    for li in soup.select("ul.list li"):
        a = li.select_one("div.board_title a[href]")
        if a:
            links.append(a["href"])
    return links


def _parse_attachments(soup: BeautifulSoup, source_url: str, date: str) -> list[FormItem]:
    """상세페이지 HTML에서 첨부파일 추출"""
    items: list[FormItem] = []
    seen: set[str] = set()

    for a in soup.select("ul.p-attach a.p-attach__link[href]"):
        href = a.get("href", "").strip()
        if not href:
            continue

        # 상대 경로 → 절대 URL
        if href.startswith("./"):
            file_url = DETAIL_BASE + "/" + href[2:]
        elif href.startswith("/"):
            file_url = BASE_URL + href
        else:
            file_url = href

        if file_url in seen:
            continue

        raw_text = a.get_text(strip=True)
        file_name = _clean_filename(raw_text)
        file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

        seen.add(file_url)
        items.append(FormItem(
            ministry=MINISTRY_NAME,
            title=file_name,
            file_name=file_name,
            file_url=file_url,
            source_url=source_url,
            registered_date=date,
            file_ext=file_ext,
        ))

    return items


class MpvaScraper(BaseGovScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.5

    def __init__(self, download_dir: str = "downloads/gov_contracts/국가보훈부"):
        super().__init__()
        self.session = cffi_requests.Session(impersonate="chrome")
        self.download_dir = download_dir

    # ── 내부 헬퍼 ──────────────────────────────────────────────────

    def _get(self, url: str, **kwargs) -> str:
        """GET 요청 + 재시도 (curl_cffi)"""
        max_retries = 3
        for attempt in range(max_retries):
            if attempt > 0:
                wait = 2 ** attempt
                print(f"[MPVA] 재시도 {attempt}/{max_retries - 1}, {wait}초 대기")
                time.sleep(wait)
                self.session = cffi_requests.Session(impersonate="chrome")
            time.sleep(self.request_delay)
            try:
                r = self.session.get(url, timeout=30, **kwargs)
                r.raise_for_status()
                return r.text
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[MPVA] 요청 실패 (시도={attempt + 1}): {e}")
                    continue
                raise

    def _search(self, keyword: str, start_count: int) -> str:
        url = (
            f"{SEARCH_URL}?query={keyword}"
            f"&collection=minwon"
            f"&startCount={start_count}"
            f"&sort=DATE&range=A"
        )
        return self._get(url)

    # ── BaseGovScraper 구현 ────────────────────────────────────────

    def filter_by_keyword(self, items: list[FormItem]) -> list[FormItem]:
        from ..utils.file_filter import EXCLUDE_TITLE_KEYWORDS
        return [
            item for item in items
            if any(kw in (item.file_name or item.title) for kw in MPVA_CONTRACT_KEYWORDS)
            and item.file_ext.lower() not in self._EXCLUDED_EXTS
            and not any(kw in item.title for kw in EXCLUDE_TITLE_KEYWORDS)
        ]

    def fetch_items(self) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        for keyword in MPVA_CONTRACT_KEYWORDS:
            print(f"[MPVA] 키워드={keyword} 검색 시작")
            start_count = 0

            while True:
                try:
                    page_html = self._search(keyword, start_count)
                except Exception as e:
                    print(f"[MPVA] 검색 실패 (startCount={start_count}): {e}")
                    break

                soup = BeautifulSoup(page_html, "html.parser")

                if start_count == 0:
                    total = _parse_total(soup)
                    print(f"[MPVA] 총 {total}건")

                detail_links = _parse_detail_links(soup)
                if not detail_links:
                    break

                page_num = start_count // PAGE_SIZE + 1
                print(f"[MPVA] startCount={start_count} — 상세페이지 {len(detail_links)}건 진입")

                for detail_url in detail_links:
                    if detail_url in seen:
                        continue
                    seen.add(detail_url)

                    try:
                        detail_html = self._get(detail_url)
                    except Exception as e:
                        print(f"[MPVA] 상세페이지 실패 ({detail_url}): {e}")
                        continue

                    # 상세페이지 날짜: p-date 또는 td.p-date
                    detail_soup = BeautifulSoup(detail_html, "html.parser")
                    date_el = detail_soup.select_one(".p-date, td.date, span.date")
                    date = date_el.get_text(strip=True) if date_el else ""

                    items = _parse_attachments(detail_soup, detail_url, date)
                    for item in items:
                        if item.file_url not in seen:
                            seen.add(item.file_url)
                            all_items.append(item)

                    if self.on_progress:
                        self.on_progress(len(all_items), f"{keyword} p{page_num}")
                    print(f"[MPVA] 상세 {detail_url[-50:]} → {len(items)}개 파일, 누적 {len(all_items)}건")

                start_count += PAGE_SIZE

        return all_items
