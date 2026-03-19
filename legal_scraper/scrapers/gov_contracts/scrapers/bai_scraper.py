"""
감사원 스크래퍼 (requests 기반)

목록 API: GET /api/boards/list?brdId=BAK_0028&searchType=0&searchText=&...&size=100&page=N
상세 API: GET /api/boards/detail?brdId=BAK_0028&postNo={postNo}
  → commonFileDetailDtoList[].{fileId, fileSn, fileName, fileExt}
다운로드: https://www.bai.go.kr/api/files/download?fileId={fileId}&fileSn={fileSn}

전략: 전체 목록 순회 → 상세 API로 파일 목록 확인 → filter_by_keyword
"""
from __future__ import annotations

import time

from ..base_scraper import BaseGovScraper, FormItem

MINISTRY_NAME = "감사원"
BASE_URL = "https://www.bai.go.kr"
BRD_ID = "BAK_0028"
LIST_URL = f"{BASE_URL}/api/boards/list"
DETAIL_URL = f"{BASE_URL}/api/boards/detail"
DOWNLOAD_URL = f"{BASE_URL}/api/files/download"
SOURCE_URL = f"{BASE_URL}/bai/down/etc/auditBoardRegulation"
PAGE_SIZE = 100


class BaiScraper(BaseGovScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 0.5

    def __init__(self, download_dir: str = "downloads/gov_contracts/감사원"):
        super().__init__()
        self.download_dir = download_dir
        self.session.verify = False
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Referer": SOURCE_URL,
        })

    def fetch_items(self) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        page = 0
        while True:
            posts, total_pages = self._fetch_list_page(page)
            if not posts:
                break

            for post in posts:
                self._process_post(post, seen, all_items)

            page += 1
            if page >= total_pages:
                break
            time.sleep(self.request_delay)

        return all_items

    def _fetch_list_page(self, page: int) -> tuple[list[dict], int]:
        """목록 API 호출 → (게시글 목록, 전체 페이지 수)"""
        try:
            resp = self.session.get(
                LIST_URL,
                params={
                    "brdId": BRD_ID,
                    "searchType": "0",
                    "searchText": "",
                    "fromRegiDt": "",
                    "toRegiDt": "",
                    "searchYear": "",
                    "searchDvsnCd": "",
                    "size": str(PAGE_SIZE),
                    "index": "0",
                    "page": str(page),
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[BAI] 목록 조회 실패 (page={page}): {e}")
            return [], 0

        posts = data.get("_embedded", {}).get("boardDtoList", [])
        total_pages = data.get("page", {}).get("totalPages", 1)
        return posts, total_pages

    def _process_post(
        self,
        post: dict,
        seen: set[str],
        items: list[FormItem],
    ) -> None:
        post_no = post.get("postNo")
        title = post.get("titNm", "").strip()
        registered_date = (post.get("regiDt") or "")[:10]  # "2024-11-26T00:00:00" → "2024-11-26"
        department = post.get("chgrNm", "")

        try:
            resp = self.session.get(
                DETAIL_URL,
                params={"brdId": BRD_ID, "postNo": str(post_no)},
                timeout=30,
            )
            resp.raise_for_status()
            detail = resp.json()
        except Exception as e:
            print(f"[BAI] 상세 조회 실패 (postNo={post_no}): {e}")
            return

        files = detail.get("commonFileDetailDtoList") or []
        for f in files:
            file_id = f.get("fileId", "")
            file_sn = f.get("fileSn", 1)
            file_name = f.get("fileName", "").strip()
            file_ext = f.get("fileExt", "").lower().strip()

            if not file_id:
                continue

            file_url = f"{DOWNLOAD_URL}?fileId={file_id}&fileSn={file_sn}"
            dedup_key = file_url
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            items.append(FormItem(
                ministry=MINISTRY_NAME,
                title=title,
                file_name=file_name,
                file_url=file_url,
                source_url=SOURCE_URL,
                registered_date=registered_date,
                department=department,
                file_ext=file_ext,
            ))

        time.sleep(self.request_delay)
