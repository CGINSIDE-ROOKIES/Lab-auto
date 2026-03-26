"""
외교부 표준계약서 스크래퍼 (requests + JSON API)

검색 페이지: https://search.mofa.go.kr/search/search_new.do
AJAX API:   POST https://search.mofa.go.kr/search/consulSearch.do
- 파라미터: charset=UTF-8, datatype=json, query=키워드, sort=DATE, startCount=N, viewCount=10
- 응답 JSON: attach_embd_ko.Document[] — 파일 첨부 검색 결과
    - ATTACHNM   : 파일명
    - ATTACH_URL : 다운로드 full URL (재외공관 도메인 포함)
    - LINK_URL   : 상세 페이지 URL
    - DATE       : 등록일 (YYYY.MM.DD)
    - EXT        : 파일 확장자

※ 외교부 전용 키워드(MOFA_KEYWORDS) 사용 — 전역 CONTRACT_KEYWORDS 와 독립.
   동일 파일이 여러 재외공관에 각각 업로드되는 경우가 있으므로
   URL 중복 제거에 더해 파일명 기준 중복 제거도 적용.
"""
from __future__ import annotations

import time

from ..base_scraper import BaseGovScraper, FormItem

MINISTRY_NAME = "외교부"
BASE_URL = "https://search.mofa.go.kr"
SEARCH_PAGE_URL = f"{BASE_URL}/search/search_new.do"
AJAX_URL = f"{BASE_URL}/search/consulSearch.do"
VIEW_COUNT = 10

# ── 외교부 전용 키워드 ────────────────────────────────────────────────
# 전역 CONTRACT_KEYWORDS 와 독립적으로 관리됩니다.
MOFA_KEYWORDS: list[str] = [
    "촉탁서",
]


class MofaScraper(BaseGovScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.0

    def _init_session(self) -> None:
        super()._init_session()
        try:
            # 세션 쿠키 획득
            self.session.get(SEARCH_PAGE_URL, timeout=30)
        except Exception:
            pass  # GET 실패 시 AJAX 단계에서 재시도

    # ── 키워드 필터 재정의 ────────────────────────────────────────────

    def filter_by_keyword(self, items: list[FormItem]) -> list[FormItem]:
        from ..utils.file_filter import EXCLUDE_TITLE_KEYWORDS
        return [
            item for item in items
            if any(kw in (item.file_name or item.title) for kw in MOFA_KEYWORDS)
            and item.file_format.lower() not in self._EXCLUDED_EXTS
            and not any(kw in item.title or kw in item.file_name for kw in EXCLUDE_TITLE_KEYWORDS)
        ]

    # ── 수집 진입점 ───────────────────────────────────────────────────

    def fetch_items(self) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen_urls: set[str] = set()
        seen_names: set[str] = set()

        for keyword in MOFA_KEYWORDS:
            self._search_keyword(keyword, seen_urls, seen_names, all_items)

        return all_items

    # ── 키워드별 페이지 순회 ──────────────────────────────────────────

    def _search_keyword(
        self,
        keyword: str,
        seen_urls: set[str],
        seen_names: set[str],
        all_items: list[FormItem],
    ) -> None:
        start_count = 0
        total: int | None = None

        while True:
            try:
                data = self._post_search(keyword, start_count)
            except Exception as e:
                print(f"[{MINISTRY_NAME}] AJAX 요청 실패 (startCount={start_count}): {e}")
                break

            attach = data.get("attach_embd_ko", {})

            if total is None:
                total = int(attach.get("totalCount", 0))
                print(f"[{MINISTRY_NAME}] 키워드='{keyword}' 총 {total}건")
                if total == 0:
                    break

            documents = attach.get("Document", [])
            if not documents:
                break

            for doc in documents:
                item = self._doc_to_item(doc)
                if item is None:
                    continue
                # URL 또는 파일명 기준 중복 제거
                # (동일 파일이 여러 재외공관 사이트에 각각 올라오는 경우 파일명이 같음)
                if item.file_url in seen_urls or item.file_name in seen_names:
                    continue
                seen_urls.add(item.file_url)
                seen_names.add(item.file_name)
                all_items.append(item)

            if self.on_progress:
                self.on_progress(len(all_items), f"{len(all_items)}건 수집 중...")

            start_count += VIEW_COUNT
            if total is not None and start_count >= total:
                break
            if len(documents) < VIEW_COUNT:
                break

    # ── AJAX POST ────────────────────────────────────────────────────

    def _post_search(self, keyword: str, start_count: int) -> dict:
        time.sleep(self.request_delay)
        resp = self._request_with_retry(
            lambda: self.session.post(
                AJAX_URL,
                data={
                    "charset": "UTF-8",
                    "datatype": "json",
                    "query": keyword,
                    "sort": "DATE",
                    "startCount": str(start_count),
                    "viewCount": str(VIEW_COUNT),
                },
                headers={
                    "Referer": SEARCH_PAGE_URL,
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=30,
            )
        )
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.json()

    # ── JSON Document → FormItem ─────────────────────────────────────

    def _doc_to_item(self, doc: dict) -> FormItem | None:
        file_url = doc.get("ATTACH_URL", "").strip()
        file_name = doc.get("ATTACHNM", "").strip()
        if not file_url or not file_name:
            return None

        raw_date = doc.get("DATE", "")
        registered_date = raw_date.replace(".", "-")  # YYYY.MM.DD → YYYY-MM-DD

        file_ext = doc.get("EXT", "").lower().strip()
        if not file_ext and "." in file_name:
            file_ext = file_name.rsplit(".", 1)[-1].lower()

        # 확장자 제거한 순수 제목
        if file_ext and file_name.lower().endswith(f".{file_ext}"):
            title = file_name[: -(len(file_ext) + 1)]
        else:
            title = file_name

        source_url = doc.get("LINK_URL", "").strip()

        return FormItem(
            source=MINISTRY_NAME,
            title=title,
            file_name=file_name,
            file_url=file_url,
            source_url=source_url,
            registered_date=registered_date,
            file_format=file_ext,
        )
