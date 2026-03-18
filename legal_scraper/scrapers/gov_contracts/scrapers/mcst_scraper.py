"""
문화체육관광부 표준계약서 스크래퍼 (Playwright)

목록 URL: https://www.mcst.go.kr/site/s_data/generalData/dataList.jsp?pMenuCD=0405050000
- 목록 페이지에서 pSeq 수집 → 상세 페이지 방문 → 첨부파일 URL 조립
- 페이지네이션: movePage(N, form) onclick 클릭

다운로드 URL 패턴 (onclick 파싱):
  file_download('인코딩된원본명', '저장된실제명', 'menuCD')
  → /servlets/eduport/front/upload/UplDownloadFile
    ?pFileName={인코딩된원본명}&pRealName={저장된실제명}&pPath={menuCD}&pFlag=
"""
from __future__ import annotations

import re
import time
import urllib.parse

from bs4 import BeautifulSoup
from playwright.sync_api import Page

from ..base_playwright_scraper import BasePlaywrightScraper
from ..base_scraper import FormItem

MINISTRY_NAME = "문화체육관광부"
BASE_URL = "https://www.mcst.go.kr"
MENU_CD = "0405050000"
LIST_URL = f"{BASE_URL}/site/s_data/generalData/dataList.jsp?pMenuCD={MENU_CD}"
VIEW_URL = f"{BASE_URL}/site/s_data/generalData/dataView.jsp"
DOWNLOAD_URL = f"{BASE_URL}/servlets/eduport/front/upload/UplDownloadFile"


class McstScraper(BasePlaywrightScraper):
    MINISTRY_NAME = MINISTRY_NAME
    ministry_name = MINISTRY_NAME
    request_delay = 1.5

    def __init__(self, download_dir: str = "downloads/gov_contracts/문화체육관광부"):
        super().__init__()
        self.download_dir = download_dir

    def _scrape_page(self, page: Page) -> list[FormItem]:
        all_items: list[FormItem] = []
        seen: set[str] = set()

        # ── 1단계: 목록 페이지에서 전체 pSeq 수집 ──────────────────────
        page.goto(LIST_URL, wait_until="networkidle", timeout=30000)
        time.sleep(1)

        row_data: list[tuple[str, str, str, str]] = []  # (pSeq, title, date, dept)

        while True:
            soup = BeautifulSoup(page.content(), "html.parser")
            tbody = soup.find("tbody")
            if tbody:
                for tr in tbody.find_all("tr"):
                    a_tag = tr.find("a", href=lambda h: h and "dataView.jsp" in (h or ""))
                    if not a_tag:
                        # onclick fnView 방식 fallback
                        a_tag = tr.find("a", onclick=lambda o: o and "fnView" in (o or ""))
                    if not a_tag:
                        continue

                    # pSeq 추출
                    p_seq = ""
                    href = a_tag.get("href", "")
                    m = re.search(r"pSeq=(\d+)", href)
                    if m:
                        p_seq = m.group(1)
                    else:
                        onclick = a_tag.get("onclick", "")
                        m = re.search(r"fnView\(['\"][\w]+['\"],\s*['\"](\d+)['\"]", onclick)
                        if m:
                            p_seq = m.group(1)
                    if not p_seq:
                        continue

                    # 제목
                    title_p = a_tag.find("p", class_="tit")
                    title = title_p.get_text(strip=True) if title_p else a_tag.get_text(strip=True)

                    # td 위치 기반: [0]번호 [1]제목 [2]담당부서 [3]등재일 [4]조회
                    tds = tr.find_all("td")
                    registered_date = tds[3].get_text(strip=True).rstrip(".") if len(tds) > 3 else ""
                    department = tds[2].get_text(strip=True) if len(tds) > 2 else ""

                    row_data.append((p_seq, title, registered_date, department))

            # 다음 페이지 클릭 (movePage(N, form) 방식)
            next_btn = page.query_selector("a[onclick*='movePage']:last-of-type")
            # "다음" 텍스트 버튼 탐색
            next_btn = None
            for a in soup.find_all("a", onclick=lambda o: o and "movePage" in (o or "")):
                txt = a.get_text(strip=True)
                if txt in ("다음", "next", ">", "▶"):
                    next_btn_sel = a.get("onclick", "")
                    m_next = re.search(r"movePage\((\d+)", next_btn_sel)
                    if m_next:
                        next_page_num = m_next.group(1)
                        next_btn = page.query_selector(
                            f"a[onclick*='movePage({next_page_num},'],"
                            f"a[onclick*=\"movePage({next_page_num},\"],"
                            f"a[onclick*=\"movePage('{next_page_num}'\"]"
                        )
                    break

            if not next_btn:
                break

            try:
                next_btn.click()
                page.wait_for_load_state("networkidle")
                time.sleep(1)
            except Exception:
                break

        # ── 2단계: 각 pSeq 상세 페이지 방문 → 파일 URL 수집 ────────────
        for p_seq, title, registered_date, department in row_data:
            detail_url = f"{VIEW_URL}?pMenuCD={MENU_CD}&pSeq={p_seq}"

            try:
                page.goto(detail_url, wait_until="networkidle", timeout=30000)
                time.sleep(1)
            except Exception as e:
                print(f"[MCST] 상세 페이지 로드 실패 pSeq={p_seq}: {e}")
                continue

            detail_soup = BeautifulSoup(page.content(), "html.parser")

            # file_download('인코딩명', '저장명', 'menuCD') 패턴
            found_file = False
            for fa in detail_soup.find_all("a", onclick=lambda o: o and "file_download" in (o or "")):
                onclick = fa.get("onclick", "")
                m = re.search(
                    r"file_download\('([^']+)',\s*'([^']+)',\s*'([^']+)'\)",
                    onclick,
                )
                if not m:
                    continue

                p_file_name = m.group(1)   # URL 인코딩된 원본 파일명
                p_real_name = m.group(2)   # 서버 저장 파일명
                p_path = m.group(3)        # menuCD

                file_url = (
                    f"{DOWNLOAD_URL}"
                    f"?pFileName={p_file_name}"
                    f"&pRealName={p_real_name}"
                    f"&pPath={p_path}"
                    f"&pFlag="
                )

                # 파일명 디코딩
                file_name = urllib.parse.unquote_plus(p_file_name)
                file_ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

                dedup_key = file_url
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                found_file = True

                all_items.append(FormItem(
                    ministry=MINISTRY_NAME,
                    title=title,
                    file_name=file_name,
                    file_url=file_url,
                    source_url=detail_url,
                    registered_date=registered_date,
                    department=department,
                    file_ext=file_ext,
                ))

            if not found_file:
                print(f"[MCST] 첨부파일 없음: pSeq={p_seq}, title={title[:30]}")

        return all_items
