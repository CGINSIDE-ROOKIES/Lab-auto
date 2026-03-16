"""
전자소송포털 양식모음 스크래퍼
방식: requests JSON API 직접 호출
API: POST /psp/psp720/selectNboardList.on
다운로드: https://file.scourt.go.kr/AttachDownload?path=004&file={fileSysName}

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

import requests

from config import ECFS_API_URL, ECFS_DOWNLOAD_BASE, ECFS_NAME, ECFS_PAGE_SIZE, HEADERS, REQUEST_DELAY

log = logging.getLogger("legal_scraper.ecfs")
TODAY = date.today().strftime("%Y-%m-%d")
_REFERER = "https://ecfs.scourt.go.kr/psp/index.on?m=PSP720M24"

# 공탁(전자공탁 별도 사이트)을 제외한 전체 분야 목록
# minGubun2 파라미터로 카테고리별 필터링
CATEGORIES = [
    ("a", "민사"),
    ("b", "신청"),
    ("c", "강제집행"),
    ("d", "개인파산/면책"),
    ("e", "가사"),
    ("f", "행정"),
    ("h", "가족관계등록"),
    ("i", "형사"),
    ("k", "정보공개청구"),
    ("l", "개인회생"),
    ("m", "소년·가정·아동보호"),
    ("n", "특허"),
    ("o", "후견등기"),
    ("p", "일반회생"),
    ("q", "법인회생"),
    ("r", "법인파산"),
    ("s", "독촉"),
    ("t", "장애인 사법지원"),
]


def _delay():
    time.sleep(random.uniform(*REQUEST_DELAY))


def _fetch(session, page_no, total_cnt, category_code):
    payload = {"dma_search": {
        "pageNo": page_no,
        "pageSize": ECFS_PAGE_SIZE,
        "bfPageNo": page_no - 1 if page_no > 1 else "",
        "startRowNo": (page_no - 1) * ECFS_PAGE_SIZE + 1,
        "totalCnt": total_cnt,
        "totalYn": "Y" if page_no == 1 else "N",
        "minGubun": "", "minGubun2": category_code, "sName": "", "eName": "",
        "searchWord": "", "searchWord2": "",
        "firstYn": "Y" if page_no == 1 else "N",
    }}
    resp = session.post(
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


def _dl_url(fname):
    return ECFS_DOWNLOAD_BASE.format(filename=fname) if fname else ""


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
                "다운로드URL": _dl_url(sys_nm),
                "수집일시": TODAY,
            })
            added = True
        if not added:
            rows.append({"수집처": ECFS_NAME, "대분류": 대분류, "중분류": "",
                         "서식제목": 서식제목, "파일형식": "", "다운로드URL": "", "수집일시": TODAY})
    return rows


def _scrape_category(session, code, name, sample_mode, on_progress, known_keys,
                     cat_idx, total_cats):
    """단일 카테고리 스크래핑. 수집된 rows 반환."""
    results = []
    stop = False

    data = _fetch(session, 1, "", code)
    total_cnt = int(data["data"]["dma_search"].get("totalCnt", 0))
    items = data["data"].get("dlt_nboardList", [])
    log.info(f"ECFS [{name}] 총 {total_cnt}건")

    if sample_mode:
        results = _parse_items(items[:5])
        if on_progress:
            on_progress(cat_idx, total_cats, f"[{name}] 샘플 {len(results)}건")
        return results

    rows = _parse_items(items)
    if known_keys:
        rows, stop = _filter_known(rows, known_keys)
    results.extend(rows)
    total_pages = math.ceil(total_cnt / ECFS_PAGE_SIZE) if total_cnt else 1

    if on_progress:
        on_progress(cat_idx, total_cats, f"[{name}] 1/{total_pages} 페이지")

    if not stop:
        for pg in range(2, total_pages + 1):
            _delay()
            try:
                data = _fetch(session, pg, total_cnt, code)
                items = data["data"].get("dlt_nboardList", [])
                rows = _parse_items(items)
                if known_keys:
                    rows, stop = _filter_known(rows, known_keys)
                results.extend(rows)
                log.info(f"ECFS [{name}] {pg}/{total_pages}")
                if on_progress:
                    on_progress(cat_idx, total_cats, f"[{name}] {pg}/{total_pages} 페이지")
            except Exception as e:
                log.error(f"ECFS [{name}] {pg}p 오류: {e}")
            if stop:
                log.info(f"ECFS [{name}] {pg}p: 기존 항목 발견 → 수집 중단")
                break

    return results


def scrape(sample_mode=False, on_progress=None, known_keys=None):
    session = requests.Session()
    results = []
    total_cats = len(CATEGORIES)

    for idx, (code, name) in enumerate(CATEGORIES, start=1):
        try:
            _delay()
            cat_rows = _scrape_category(
                session, code, name, sample_mode,
                on_progress, known_keys, idx, total_cats,
            )
            results.extend(cat_rows)
            log.info(f"ECFS [{name}] 완료: {len(cat_rows)}행")
        except Exception as e:
            log.error(f"ECFS [{name}] 오류: {e}")

        if sample_mode:
            break

    if on_progress:
        on_progress(total_cats, total_cats, "완료")
    log.info(f"ECFS 전체 완료: {len(results)}행")
    return results
