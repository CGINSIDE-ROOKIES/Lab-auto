"""
전자공탁 공탁양식 스크래퍼
방식: requests JSON API 직접 호출
API: POST /pjg/pjg172/selectEdpsFrmlLst.on
다운로드: POST /pjg/pjgedm/blobDown.on (JSON body: dma_downloadFile)

아이템 필드: dpsFrmlDvsCd(코드), dpsFrmlFileNm(서식명),
             dpsHwpFrmlFile/dpsDocxFrmlFile/dpsPdfFrmlFile/dpsWrtExmFile ("Y")
진행 콜백: on_progress(current_page, total_pages, message)
"""
import time
import random
import math
import logging
from datetime import date
from urllib.parse import urlparse, parse_qs

import requests

from config import EKT_API_URL, EKT_DOWNLOAD_BASE, EKT_NAME, EKT_PAGE_SIZE, HEADERS, REQUEST_DELAY

log = logging.getLogger("legal_scraper.ekt")
TODAY = date.today().strftime("%Y-%m-%d")
_REFERER = "https://ekt.scourt.go.kr/pjg/index.on?m=PJG172M03"

# (API 필드, 표기 확장자, blobDown fileExtsPnlim)
_FILE_TYPES = [
    ("dpsHwpFrmlFile",  "HWP",  "hwp"),
    ("dpsDocxFrmlFile", "DOCX", "doc"),
    ("dpsPdfFrmlFile",  "PDF",  "pdf"),
    ("dpsWrtExmFile",   "GIF",  "gif"),
]

# fileExtsPnlim → fileColumn 매핑
_FILE_COL = {
    "hwp": "dpsHwpFrmlFile",
    "doc": "dpsDocxFrmlFile",
    "pdf": "dpsPdfFrmlFile",
    "gif": "dpsWrtExmFile",
}


def _delay():
    time.sleep(random.uniform(*REQUEST_DELAY))


def _fetch(session, page_no):
    resp = session.post(
        EKT_API_URL,
        json={"dma_srchDpsForm": {"srchdpsForm": "", "pageNo": str(page_no),
                                   "pageSize": str(EKT_PAGE_SIZE), "rnum": ""}},
        headers={**HEADERS, "Content-Type": "application/json", "Referer": _REFERER},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def _dl_url(dvs_cd, file_ext):
    return f"{EKT_DOWNLOAD_BASE}?kindCode=03&dpsFrmlDvsCd={dvs_cd}&fileExtsPnlim={file_ext}"


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
        dvs_cd   = str(item.get("dpsFrmlDvsCd", ""))
        서식제목 = item.get("dpsFrmlFileNm", "").strip()
        added = False
        for field, ext_label, file_ext in _FILE_TYPES:
            if item.get(field) == "Y":
                rows.append({
                    "수집처": EKT_NAME,
                    "대분류": "공탁",
                    "중분류": "",
                    "서식제목": 서식제목,
                    "파일형식": ext_label,
                    "다운로드URL": _dl_url(dvs_cd, file_ext),
                    "수집일시": TODAY,
                })
                added = True
        if not added:
            rows.append({"수집처": EKT_NAME, "대분류": "공탁", "중분류": "",
                         "서식제목": 서식제목, "파일형식": "", "다운로드URL": "", "수집일시": TODAY})
    return rows


def download_file(download_url: str, save_path: str) -> bool:
    qs = parse_qs(urlparse(download_url).query)
    dvs_cd   = qs.get("dpsFrmlDvsCd", [""])[0]
    file_ext = qs.get("fileExtsPnlim", [""])[0]
    file_col = _FILE_COL.get(file_ext, "")

    session = requests.Session()
    session.headers.update({**HEADERS, "Referer": _REFERER})
    session.get(_REFERER, timeout=15)
    response = session.post(
        EKT_DOWNLOAD_BASE,
        json={"dma_downloadFile": {
            "kindCode": "03",
            "dpsFrmlDvsCd": dvs_cd,
            "fileExtsPnlim": file_ext,
            "fileColumn": file_col,
            "fileNm": "dpsFrmlFileNm",
        }},
        headers={"Content-Type": "application/json; charset=UTF-8"},
        timeout=30,
    )
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
        data = _fetch(session, 1)
        info = data["data"]["dma_srchDpsForm"]
        total_cnt = int(info.get("grsCnt", 0))
        items = data["data"].get("dlt_edpsFrmlLst", [])
        log.info(f"EKT 총 {total_cnt}건")

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
        total_pages = math.ceil(total_cnt / EKT_PAGE_SIZE)
        if on_progress:
            on_progress(1, total_pages, f"1/{total_pages} 페이지")

        if not stop:
            for pg in range(2, total_pages + 1):
                _delay()
                try:
                    data = _fetch(session, pg)
                    items = data["data"].get("dlt_edpsFrmlLst", [])
                    rows = _parse_items(items)
                    if known_keys:
                        rows, stop = _filter_known(rows, known_keys)
                    results.extend(rows)
                    log.info(f"EKT {pg}/{total_pages}")
                    if on_progress:
                        on_progress(pg, total_pages, f"{pg}/{total_pages} 페이지")
                except Exception as e:
                    log.error(f"EKT {pg}p 오류: {e}")
                if stop:
                    log.info(f"EKT {pg}p: 기존 항목 발견 → 수집 중단")
                    break

    except Exception as e:
        log.error(f"EKT 오류: {e}")

    if on_progress:
        on_progress(1, 1, "완료")
    log.info(f"EKT 완료: {len(results)}행")
    return results
