"""
공정거래위원회 표준계약서 스크래퍼

목록 URL: https://www.ftc.go.kr/www/selectBbsNttList.do?bordCd=201&key=202&pageIndex={N}
유형 A — requests + BeautifulSoup
"""
from __future__ import annotations

import urllib.parse

from bs4 import BeautifulSoup

from ..base_scraper import BaseGovScraper, FormItem

MINISTRY_NAME = "공정거래위원회"
BASE_URL = "https://www.ftc.go.kr/www/selectBbsNttList.do"
BASE_HOST = "https://www.ftc.go.kr/www"
MAX_PAGES = 200

# 수집 대상 게시판 (bordCd, key) 쌍
BOARDS = [
    ("201", "202"),  # 표준약관
    ("202", "203"),  # 표준하도급계약서
    ("203", "204"),  # 표준가맹계약서
    ("204", "205"),  # 표준유통거래계약서
    ("205", "206"),  # 표준대리점거래계약서
    ("206", "207"),  # 표준비밀유지계약서
]


class FtcScraper(BaseGovScraper):
    ministry_name = MINISTRY_NAME
    request_delay = 1.5

    def __init__(self, download_dir: str = "downloads/gov_contracts/공정거래위원회"):
        super().__init__()
        self.download_dir = download_dir

    # ── 공개 메서드 ───────────────────────────────────────────────

    def fetch_items(self) -> list[FormItem]:
        """6개 게시판 × 전체 페이지 순회 → FormItem 리스트 반환 (파일명/확장자 미포함)"""
        items: list[FormItem] = []

        for bord_cd, key in BOARDS:
            for page in range(1, MAX_PAGES + 1):
                soup = self.parse_html(
                    BASE_URL,
                    params={
                        "bordCd": bord_cd,
                        "key": key,
                        "pageIndex": str(page),
                    },
                )
                rows = self._parse_rows(soup, page)

                if not rows:
                    break

                items.extend(rows)

        return items

    def run(self) -> list[FormItem]:
        """
        1) 전체 목록 수집
        2) 제목에 '계약서' 포함된 항목 필터
        3) 필터된 항목만 HEAD 요청 → 파일명/확장자 보강
        """
        all_items = self.fetch_items()
        filtered = self.filter_by_keyword(all_items)
        self._enrich_file_info(filtered)
        return filtered

    # ── 내부 메서드 ───────────────────────────────────────────────

    def _parse_rows(self, soup: BeautifulSoup, page: int) -> list[FormItem]:
        tbody = soup.find("tbody")
        if not tbody:
            return []

        rows = tbody.find_all("tr")
        if not rows:
            return []

        items: list[FormItem] = []
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue

            # 제목 및 상세 URL
            title_td = tds[1]
            a_tag = title_td.find("a")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            detail_href = a_tag.get("href", "")
            source_url = (
                BASE_HOST + "/" + detail_href.lstrip("./")
                if detail_href
                else ""
            )

            # 담당부서
            department = tds[2].get_text(strip=True)

            # 등록일
            registered_date = tds[3].get_text(strip=True)

            # 다운로드 URL
            file_td = tds[4]
            dl_a = file_td.find("a", href=lambda h: h and "downloadBbsFile" in h)
            if not dl_a:
                continue
            dl_href = dl_a.get("href", "")
            file_url = BASE_HOST + "/" + dl_href.lstrip("./") if dl_href else ""

            items.append(
                FormItem(
                    ministry=MINISTRY_NAME,
                    title=title,
                    file_name="",       # HEAD 요청 후 보강
                    file_url=file_url,
                    source_url=source_url,
                    registered_date=registered_date,
                    department=department,
                )
            )

        return items

    def _enrich_file_info(self, items: list[FormItem]) -> None:
        """
        필터된 항목에 대해서만 HEAD 요청 → Content-Disposition에서
        파일명과 확장자를 추출해 item을 직접 수정한다.
        """
        for item in items:
            if not item.file_url:
                continue
            try:
                resp = self.session.head(item.file_url, timeout=15, allow_redirects=True)
                cd = resp.headers.get("Content-Disposition", "")
                filename = _extract_filename(cd)
                if filename:
                    item.file_name = filename
                    parts = filename.rsplit(".", 1)
                    item.file_ext = parts[-1].lower() if len(parts) == 2 else ""
            except Exception:
                pass


def _extract_filename(content_disposition: str) -> str:
    """Content-Disposition 헤더에서 파일명을 추출한다."""
    if not content_disposition:
        return ""

    # RFC 5987: filename*=charset''encoded
    import re
    m = re.search(r"filename\*=([^;]+)", content_disposition)
    if m:
        raw = m.group(1).strip()
        try:
            charset, _, encoded = raw.split("'", 2)
            return urllib.parse.unquote(encoded, encoding=charset or "utf-8")
        except ValueError:
            pass

    # 일반: filename="..." 또는 filename=...
    m = re.search(r'filename=["\']?([^"\';\r\n]+)["\']?', content_disposition)
    if m:
        raw = m.group(1).strip().strip("\"'")
        # URL 인코딩 우선 시도
        try:
            decoded = urllib.parse.unquote(raw, encoding="utf-8")
            if decoded != raw:
                return decoded
        except Exception:
            pass
        # EUC-KR 시도
        try:
            return raw.encode("latin-1").decode("euc-kr")
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
        return raw

    return ""
