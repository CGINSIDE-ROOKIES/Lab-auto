"""
대한법률구조공단 법률서식 스크래퍼
방식: requests + BeautifulSoup (POST 기반 HTML)
진행 콜백: on_progress(current, total, message)
  - current/total: 탭 번호 기준 (1~N)
  - message: 현재 상태 문자열
"""
import math
import re
import time
import random
import logging
from urllib.parse import parse_qs, urlparse, unquote
from datetime import date

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import requests
from bs4 import BeautifulSoup

from config import KLAC_URL, KLAC_NAME, HEADERS, REQUEST_DELAY

log = logging.getLogger("legal_scraper.klac")
TODAY = date.today().strftime("%Y-%m-%d")


def _delay():
    time.sleep(random.uniform(*REQUEST_DELAY))


def _get_tabs(session):
    resp = session.get(KLAC_URL, timeout=15, verify=False)
    soup = BeautifulSoup(resp.content, "lxml")
    tabs = []
    for li in soup.select("ul.col-6 li"):
        a = li.find("a")
        if not a:
            continue
        m = re.search(r"fn_clickTab\('(\w+)','([^']+)'\)", a.get("href", ""))
        if m and m.group(1) != "000":
            tabs.append({"code": m.group(1), "name": m.group(2)})
    return tabs


def _fetch_page(session, folder_id, page_index):
    resp = session.post(KLAC_URL, data={
        "pageIndex": str(page_index),
        "folderId": folder_id,
        "listNm": "",
        "searchCnd": "0",
        "scdFolderId": "",
    }, timeout=15, verify=False)
    return BeautifulSoup(resp.content, "lxml")


def _total_pages(soup):
    # 총 게시물 수: <span class="data_num">총 <strong>N</strong> 개의 게시물...</span>
    span = soup.find("span", class_="data_num")
    if span:
        strong = span.find("strong")
        if strong:
            try:
                total = int(strong.get_text(strip=True).replace(',', ''))
                return math.ceil(total / 10)
            except ValueError:
                pass
    # fallback: 페이지 버튼 최댓값
    paging = soup.find("div", class_="paging_wrap")
    if not paging:
        return 1
    return max((int(a.get_text(strip=True)) for a in paging.find_all("a")
                if a.get_text(strip=True).isdigit()), default=1)


def _ext(url):
    try:
        params = parse_qs(urlparse(url).query)
        if "filename" in params:
            fname = unquote(params["filename"][0])
            return fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
    except Exception:
        pass
    return ""


def _snap_key(r):
    return f"{r['서식제목']}|||{r['파일형식']}"


def _filter_known(rows, known_keys):
    """기존 항목 발견 직전까지만 반환. (new_rows, found_known) 반환"""
    new_rows = []
    for r in rows:
        if _snap_key(r) in known_keys:
            return new_rows, True
        new_rows.append(r)
    return new_rows, False


def _parse_rows(soup, tab_name):
    table = soup.find("table", class_="table_TP03")
    if not table:
        return []
    rows = []
    for tr in table.find_all("tr")[1:]:
        tds = tr.find_all("td")
        if len(tds) < 3:
            continue
        중분류 = tds[0].get_text(strip=True)
        서식제목 = tds[1].get_text(strip=True)
        for a in tds[2].find_all("a", href=True):
            href = a["href"]
            if "FileDown" in href and href.startswith("http"):
                rows.append({
                    "수집처": KLAC_NAME,
                    "대분류": tab_name,
                    "중분류": 중분류,
                    "서식제목": 서식제목,
                    "파일형식": _ext(href),
                    "다운로드URL": href,
                    "수집일시": TODAY,
                })
    return rows


def scrape(sample_mode=False, on_progress=None, known_keys=None, limit=None):
    session = requests.Session()
    session.headers.update(HEADERS)
    results = []

    try:
        tabs = _get_tabs(session)
        log.info(f"KLAC 탭 수: {len(tabs)}")
    except Exception as e:
        log.error(f"KLAC 탭 로드 실패: {e}")
        return results

    total_tabs = len(tabs)
    for idx, tab in enumerate(tabs):
        folder_id, tab_name = tab["code"], tab["name"]
        try:
            _delay()
            soup = _fetch_page(session, folder_id, 1)
            total_pages = _total_pages(soup)
            msg = f"'{tab_name}' 1/{total_pages} 페이지"
            if on_progress:
                on_progress(idx + 1, total_tabs, msg)

            rows = _parse_rows(soup, tab_name)
            if known_keys:
                rows, tab_stop = _filter_known(rows, known_keys)
            else:
                tab_stop = False
            results.extend(rows)
            log.info(f"KLAC {tab_name} 1/{total_pages}")

            if not tab_stop and not sample_mode:
                for pg in range(2, total_pages + 1):
                    _delay()
                    try:
                        soup = _fetch_page(session, folder_id, pg)
                        rows = _parse_rows(soup, tab_name)
                        if known_keys:
                            rows, tab_stop = _filter_known(rows, known_keys)
                        results.extend(rows)
                        msg = f"'{tab_name}' {pg}/{total_pages} 페이지"
                        if on_progress:
                            on_progress(idx + 1, total_tabs, msg)
                        log.info(f"KLAC {tab_name} {pg}/{total_pages}")
                    except Exception as e:
                        log.error(f"KLAC {tab_name} {pg}p 오류: {e}")
                    if tab_stop:
                        log.info(f"KLAC {tab_name}: 기존 항목 발견 → 탭 중단")
                        break
        except Exception as e:
            log.error(f"KLAC 탭={tab_name} 오류: {e}")

        if sample_mode or (limit and len(results) >= limit):
            break

    if limit:
        results = results[:limit]
    if on_progress:
        on_progress(total_tabs, total_tabs, "완료")
    log.info(f"KLAC 완료: {len(results)}건")
    return results
