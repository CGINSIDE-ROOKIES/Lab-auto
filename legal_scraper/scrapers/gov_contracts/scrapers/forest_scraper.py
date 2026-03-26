"""
산림청 통합검색 스크래퍼 (curl_cffi — chrome TLS 흉내)

검색 URL: https://www.forest.go.kr/kfsweb/kfs/search.do
- GET kwd=키워드&category=CMS&pageNum=N&sort=d (콘텐츠 필터)
- 페이지네이션: span.paging_count "N/M" → M페이지
- 검색결과: div.srch_board > div.srchB_title a (상세 링크), span.date (날짜)
- 상세페이지: a[href*='FileDown.do'] 파싱 → 파일명은 주변 텍스트에서 추출

"""
from __future__ import annotations

import re
import time

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from ..base_scraper import BaseGovScraper, FormItem
from ..utils.file_filter import CONTRACT_KEYWORDS

MINISTRY_NAME = "산림청"
BASE_URL = "https://www.forest.go.kr"
SEARCH_URL = f"{BASE_URL}/kfsweb/kfs/search.do"

_SKIP_LINK_TEXTS = {"자료받기", "다운로드", "download", "내려받기", "첨부파일"}


def _normalize_url(href: str, fallback_base: str = BASE_URL) -> str:
    """상대 URL → 절대 URL, HTTP → HTTPS 정규화, 호스트 소문자 변환"""
    if not href:
        return ""
    import urllib.parse
    # 대문자 스킴 포함 처리
    href_lower = href[:8].lower() + href[8:]
    if href_lower.startswith("http://"):
        href = "https://" + href[7:]
    elif href_lower.startswith("https://"):
        href = "https://" + href[8:]
    if href.startswith("/"):
        href = fallback_base + href
    # 호스트 부분 소문자화
    try:
        p = urllib.parse.urlparse(href)
        href = urllib.parse.urlunparse(p._replace(netloc=p.netloc.lower()))
    except Exception:
        pass
    return href


def _extract_filename(a_tag) -> str:
    """
    FileDown.do 링크에서 파일명 추출.
    링크 텍스트가 '자료받기' 등 무의미한 경우 주변 컨텍스트에서 추출.
    """
    # 1. title / aria-label 속성
    for attr in ("title", "aria-label"):
        val = (a_tag.get(attr) or "").strip()
        if val and val not in _SKIP_LINK_TEXTS:
            return val

    # 2. 링크 텍스트 자체가 파일명이면 사용
    text = a_tag.get_text(strip=True)
    if text and text not in _SKIP_LINK_TEXTS and "." in text:
        return text

    # 3. 부모 요소 텍스트에서 링크 텍스트를 제거한 나머지
    parent = a_tag.parent
    if parent:
        parent_text = parent.get_text(" ", strip=True)
        for skip in _SKIP_LINK_TEXTS:
            parent_text = parent_text.replace(skip, "").strip()
        if parent_text and len(parent_text) > 1:
            return parent_text

    # 4. 인접 형제 또는 부모의 부모 텍스트
    grandparent = parent.parent if parent else None
    if grandparent:
        gp_text = grandparent.get_text(" ", strip=True)
        for skip in _SKIP_LINK_TEXTS:
            gp_text = gp_text.replace(skip, "").strip()
        if gp_text and len(gp_text) > 1:
            # 너무 길면 앞 80자만
            return gp_text[:80].strip()

    return text  # fallback


def _parse_total_pages(soup: BeautifulSoup) -> int:
    """span.paging_count 'N/M' 에서 총 페이지 수 반환 (없으면 1)"""
    span = soup.select_one("span.paging_count")
    if span:
        m = re.search(r"\d+/(\d+)", span.get_text(strip=True))
        if m:
            return int(m.group(1))
    return 1


def _parse_search_results(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """
    검색결과 목록에서 (상세페이지 URL, 날짜) 리스트 반환.
    div.srch_board > div.srchB_title a 가 상세 링크.
    """
    results = []
    for div in soup.select("div.srch_board"):
        a = div.select_one("div.srchB_title a[href]")
        if not a:
            continue
        detail_url = _normalize_url(a["href"])
        date_span = div.select_one("span.date")
        date = date_span.get_text(strip=True) if date_span else ""
        results.append((detail_url, date))
    return results


def _parse_attachments(soup: BeautifulSoup, source_url: str, date: str) -> list[FormItem]:
    """상세페이지 HTML에서 FileDown.do 링크를 찾아 FormItem 리스트 반환"""
    items: list[FormItem] = []
    seen: set[str] = set()

    # 상세페이지의 base URL (nfsv 서브도메인일 수 있음)
    import urllib.parse
    parsed = urllib.parse.urlparse(source_url)
    page_base = f"{parsed.scheme}://{parsed.netloc}"

    for a in soup.select("a[href*='FileDown.do']"):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        file_url = _normalize_url(href, page_base)
        if file_url in seen:
            continue

        file_name = _extract_filename(a)
        file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

        seen.add(file_url)
        items.append(FormItem(
            source=MINISTRY_NAME,
            title=file_name,
            file_name=file_name,
            file_url=file_url,
            source_url=source_url,
            registered_date=date,
            file_format=file_ext,
        ))

    return items


class ForestScraper(BaseGovScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 2.0  # WAF 대응: 넉넉한 딜레이

    def __init__(self, download_dir: str = "downloads/gov_contracts/산림청"):
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
                print(f"[FOREST] 재시도 {attempt}/{max_retries - 1}, {wait}초 대기")
                time.sleep(wait)
                self.session = cffi_requests.Session(impersonate="chrome")
            time.sleep(self.request_delay)
            try:
                r = self.session.get(url, timeout=30, **kwargs)
                r.raise_for_status()
                return r.text
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[FOREST] 요청 실패 (시도={attempt + 1}): {e}")
                    continue
                raise

    def _search(self, keyword: str, page_num: int) -> str:
        params = {
            "kwd": keyword,
            "category": "CMS",
            "pageNum": str(page_num),
            "sort": "d",
        }
        url = SEARCH_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        return self._get(url)

    # ── BaseGovScraper 구현 ────────────────────────────────────────

    def fetch_items(self) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        for keyword in CONTRACT_KEYWORDS:
            print(f"[FOREST] 키워드={keyword} 검색 시작")
            try:
                first_html = self._search(keyword, 1)
            except Exception as e:
                print(f"[FOREST] 1페이지 요청 실패 ({keyword}): {e}")
                continue

            soup = BeautifulSoup(first_html, "html.parser")
            total_pages = _parse_total_pages(soup)
            print(f"[FOREST] 총 {total_pages}페이지")

            for page_num in range(1, total_pages + 1):
                try:
                    page_html = first_html if page_num == 1 else self._search(keyword, page_num)
                except Exception as e:
                    print(f"[FOREST] 검색 {page_num}페이지 실패: {e}")
                    break

                page_soup = BeautifulSoup(page_html, "html.parser") if page_num > 1 else soup
                results = _parse_search_results(page_soup)

                if not results:
                    print(f"[FOREST] {page_num}페이지 결과 없음, 중단")
                    break

                print(f"[FOREST] {page_num}/{total_pages} — 상세페이지 {len(results)}건 진입")

                for detail_url, date in results:
                    if detail_url in seen:
                        continue
                    seen.add(detail_url)

                    try:
                        detail_html = self._get(detail_url)
                    except Exception as e:
                        print(f"[FOREST] 상세페이지 실패 ({detail_url}): {e}")
                        continue

                    detail_soup = BeautifulSoup(detail_html, "html.parser")
                    items = _parse_attachments(detail_soup, detail_url, date)
                    for item in items:
                        if item.file_url not in seen:
                            seen.add(item.file_url)
                            all_items.append(item)

                    if self.on_progress:
                        self.on_progress(len(all_items), f"{keyword} p{page_num}/{total_pages}")
                    print(f"[FOREST] 상세 {detail_url[:60]} → {len(items)}개 파일, 누적 {len(all_items)}건")

        return all_items
