"""
전자소송포털 양식모음 스크래퍼
방식: requests JSON API 직접 호출
API: POST /psp/psp720/selectNboardList.on
다운로드: GET https://file.scourt.go.kr/AttachDownload?path=004&file={fileSysName}&downFile={euckrFilename}

아이템 필드: title("[대분류] 서식제목"), fileSysName(HWP), fileSysName3(PDF),
             fileSysName2(기타), fileSysExname(기타)
진행 콜백: on_progress(current_page, total_pages, message)
"""
import re
import time
import random
import math
import logging
from datetime import date
from urllib.parse import quote

import requests

from config import ECFS_API_URL, ECFS_DOWNLOAD_BASE, ECFS_NAME, ECFS_PAGE_SIZE, HEADERS, REQUEST_DELAY

log = logging.getLogger("legal_scraper.ecfs")
TODAY = date.today().strftime("%Y-%m-%d")
_REFERER = "https://ecfs.scourt.go.kr/psp/index.on?m=PSP720M24"


def _delay():
    time.sleep(random.uniform(*REQUEST_DELAY))


def _fetch(session, page_no, total_cnt):
    payload = {"dma_search": {
        "pageNo": page_no,
        "pageSize": ECFS_PAGE_SIZE,
        "bfPageNo": page_no - 1 if page_no > 1 else "",
        "startRowNo": (page_no - 1) * ECFS_PAGE_SIZE + 1,
        "totalCnt": total_cnt,
        "totalYn": "Y" if page_no == 1 else "N",
        "minGubun": "", "minGubun2": "", "sName": "", "eName": "",
        "searchWord": "", "searchWord2": "",
        "firstYn": "Y" if page_no == 1 else "N",
    }}
    resp = requests.post(
        ECFS_API_URL,
        json=payload,
        headers={**HEADERS, "Content-Type": "application/json", "Referer": _REFERER},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_title(raw):
    m = re.match(r"^\[([^\]]+)\]\s*(.+)$", raw.strip())
    return (m.group(1).strip(), m.group(2).strip()) if m else ("", raw.strip())


def _dl_url(sys_nm, org_nm=""):
    if not sys_nm:
        return ""
    url = ECFS_DOWNLOAD_BASE.format(filename=sys_nm)
    if org_nm:
        url += "&downFile=" + quote(org_nm.encode("euc-kr", errors="replace"))
    return url


def _ext(org_name, sys_name=""):
    for n in (org_name, sys_name):
        if n and "." in n:
            return n.rsplit(".", 1)[-1].upper()
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


def _parse_items(items):
    rows = []
    for item in items:
        대분류, 서식제목 = _parse_title(item.get("title", ""))
        pairs = [
            (item.get("fileSysName"),   item.get("fileOrgName")),
            (item.get("fileSysName2"),  item.get("fileOrgName2")),
            (item.get("fileSysName3"),  item.get("fileOrgName3")),
            (item.get("fileSysExname"), item.get("fileOrgExname")),
        ]
        added = False
        for sys_nm, org_nm in pairs:
            if not sys_nm:
                continue
            rows.append({
                "수집처": ECFS_NAME,
                "대분류": 대분류,
                "중분류": "",
                "서식제목": 서식제목,
                "파일형식": _ext(org_nm, sys_nm),
                "다운로드URL": _dl_url(sys_nm, org_nm or ""),
                "수집일시": TODAY,
            })
            added = True
        if not added:
            rows.append({"수집처": ECFS_NAME, "대분류": 대분류, "중분류": "",
                         "서식제목": 서식제목, "파일형식": "", "다운로드URL": "", "수집일시": TODAY})
    return rows


def download_file(download_url: str, save_path: str) -> bool:
    session = requests.Session()
    session.headers.update({**HEADERS, "Referer": _REFERER})
    response = session.get(download_url, timeout=30)
    if response.status_code == 200 and len(response.content) > 100:
        with open(save_path, "wb") as f:
            f.write(response.content)
        return True
    return False


def scrape(sample_mode=False, on_progress=None, known_keys=None):
    session = requests.Session()
    results = []
    stop = False
    try:
        data = _fetch(session, 1, "")
        total_cnt = int(data["data"]["dma_search"].get("totalCnt", 0))
        items = data["data"].get("dlt_nboardList", [])
        log.info(f"ECFS 총 {total_cnt}건")

        if sample_mode:
            items = items[:10]
            results = _parse_items(items)
            if on_progress:
                on_progress(1, 1, f"샘플 {len(items)}건 수집 완료")
            return results

        rows = _parse_items(items)
        if known_keys:
            rows, stop = _filter_known(rows, known_keys)
        results.extend(rows)
        total_pages = math.ceil(total_cnt / ECFS_PAGE_SIZE)
        if on_progress:
            on_progress(1, total_pages, f"1/{total_pages} 페이지")

        if not stop:
            for pg in range(2, total_pages + 1):
                _delay()
                try:
                    data = _fetch(session, pg, total_cnt)
                    items = data["data"].get("dlt_nboardList", [])
                    rows = _parse_items(items)
                    if known_keys:
                        rows, stop = _filter_known(rows, known_keys)
                    results.extend(rows)
                    log.info(f"ECFS {pg}/{total_pages}")
                    if on_progress:
                        on_progress(pg, total_pages, f"{pg}/{total_pages} 페이지")
                except Exception as e:
                    log.error(f"ECFS {pg}p 오류: {e}")
                if stop:
                    log.info(f"ECFS {pg}p: 기존 항목 발견 → 수집 중단")
                    break

    except Exception as e:
        log.error(f"ECFS 오류: {e}")

    if on_progress:
        on_progress(1, 1, "완료")
    log.info(f"ECFS 완료: {len(results)}행")
    return results
