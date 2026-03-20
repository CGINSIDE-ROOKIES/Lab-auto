"""
경찰청 통합검색 스크래퍼 (curl_cffi — safari TLS 흉내)

검색 URL: https://www.police.go.kr/user/search/ND_searchResult.do
- POST colTarget=doc 로 첨부파일 전용 검색
- 응답 HTML 주석 내 fileResultList 파싱
  {ORGINL_FILE_NM=..., FILE_COURS_WEB=..., REGIST_DT=...}
- .pagination li a[onclick*='page('] 으로 전체 페이지 수 파악

※ 경찰청 전용 키워드(POLICE_CONTRACT_KEYWORDS)를 사용하며,
   전역 CONTRACT_KEYWORDS(계약/약정서)와 완전히 독립적으로 동작합니다.
   새 키워드 추가 시 POLICE_CONTRACT_KEYWORDS 리스트에만 추가하면 됩니다.
"""
from __future__ import annotations

import html
import re
import time

from curl_cffi import requests as cffi_requests

from ..base_scraper import BaseGovScraper, FormItem

MINISTRY_NAME = "경찰청"
BASE_URL = "https://www.police.go.kr"
SEARCH_URL = f"{BASE_URL}/user/search/ND_searchResult.do"

POLICE_CONTRACT_KEYWORDS: list[str] = [
    "무기계약",
]

# HTML 주석 안의 fileResultList 블록
_RESULT_LIST_RE = re.compile(
    r"fileResultList\s*:\s*\[(.+?)\]",
    re.DOTALL,
)
# 개별 항목 {KEY=value, ...}
_ITEM_RE = re.compile(r"\{([^}]+)\}")
# 키=값 파싱 (값에 ,가 없으므로 단순 분리)
_KV_RE = re.compile(r"(\w+)=([^,}]*)")
# 날짜 포맷 YYYYMMDD → YYYY-MM-DD
_DATE_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
# 마지막 페이지 번호 추출: page('44') 또는 page(44)
_LAST_PAGE_RE = re.compile(r"page\(['\"]?(\d+)['\"]?\)")


def _clean_filename(raw: str) -> str:
    """HTML 엔티티 디코딩 + 하이라이트 span 제거"""
    decoded = html.unescape(raw)
    return re.sub(r"<[^>]+>", "", decoded).strip()


def _fmt_date(raw: str) -> str:
    m = _DATE_RE.match(raw.strip())
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else raw.strip()


class PoliceScraper(BaseGovScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.5

    def __init__(self, download_dir: str = "downloads/gov_contracts/경찰청"):
        super().__init__()
        # requests.Session → curl_cffi Session 으로 교체 (safari TLS 흉내)
        self.session = cffi_requests.Session(impersonate="safari")
        self.download_dir = download_dir

    # ── 내부 헬퍼 ──────────────────────────────────────────────────

    def _post(self, keyword: str, page_num: int) -> str:
        time.sleep(self.request_delay)
        r = self.session.post(
            SEARCH_URL,
            data={
                "searchTerm": keyword,
                "colTarget": "doc",
                "pageListSize": "10",
                "q_currPage": str(page_num),
                "currentPage": str(page_num),
                "orderBy": "date",
                "gubun": "1",
                "researchTerm": "",
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.text

    def _get_last_page(self, html_text: str) -> int:
        """pagination 의 마지막 페이지 번호 반환 (없으면 1)"""
        last_page = 1
        for m in _LAST_PAGE_RE.finditer(html_text):
            n = int(m.group(1))
            if n > last_page:
                last_page = n
        return last_page

    def _parse_items(self, html_text: str, keyword: str) -> list[FormItem]:
        items: list[FormItem] = []
        m = _RESULT_LIST_RE.search(html_text)
        if not m:
            return items

        for item_m in _ITEM_RE.finditer(m.group(1)):
            kv = dict(_KV_RE.findall(item_m.group(1)))
            raw_name = kv.get("ORGINL_FILE_NM", "").strip()
            file_path = kv.get("FILE_COURS_WEB", "").strip()
            reg_dt = _fmt_date(kv.get("REGIST_DT", ""))

            if not file_path:
                continue

            file_name = _clean_filename(raw_name)
            file_url = BASE_URL + file_path if file_path.startswith("/") else file_path
            file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
            source_url = f"{SEARCH_URL}?searchTerm={keyword}&colTarget=doc"

            items.append(FormItem(
                ministry=MINISTRY_NAME,
                title=file_name,
                file_name=file_name,
                file_url=file_url,
                source_url=source_url,
                registered_date=reg_dt,
                file_ext=file_ext,
            ))
        return items

    # ── BaseGovScraper 구현 ────────────────────────────────────────

    def filter_by_keyword(self, items: list[FormItem]) -> list[FormItem]:
        return [
            item for item in items
            if any(kw in (item.file_name or item.title) for kw in POLICE_CONTRACT_KEYWORDS)
            and item.file_ext.lower() not in self._EXCLUDED_EXTS
        ]

    def fetch_items(self) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        for keyword in POLICE_CONTRACT_KEYWORDS:
            print(f"[POLICE] 키워드={keyword} 검색 시작")
            try:
                first_html = self._post(keyword, 1)
            except Exception as e:
                print(f"[POLICE] 1페이지 요청 실패 ({keyword}): {e}")
                continue

            last_page = self._get_last_page(first_html)
            print(f"[POLICE] 전체 {last_page}페이지")

            for page_num in range(1, last_page + 1):
                try:
                    page_html = first_html if page_num == 1 else self._post(keyword, page_num)
                except Exception as e:
                    print(f"[POLICE] 페이지 {page_num} 요청 실패: {e}")
                    break

                items = self._parse_items(page_html, keyword)
                for item in items:
                    if item.file_url not in seen:
                        seen.add(item.file_url)
                        all_items.append(item)

                print(f"[POLICE] {keyword} {page_num}/{last_page} - 누적 {len(all_items)}건")

        return all_items
