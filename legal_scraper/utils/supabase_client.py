"""
Supabase REST API 클라이언트 (requests 기반)
supabase-py 대신 requests로 직접 PostgREST API를 호출합니다.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

import requests

_KST = timezone(timedelta(hours=9))
from dotenv import load_dotenv

if TYPE_CHECKING:
    from legal_scraper.scrapers.gov_contracts.base_scraper import FormItem

load_dotenv()

_SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
_SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
_SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")


def _headers(conflict_ignore: bool = True) -> dict:
    prefer = "resolution=ignore-duplicates,return=minimal" if conflict_ignore else "return=minimal"
    return {
        "apikey": _SUPABASE_KEY,
        "Authorization": f"Bearer {_SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }


def _check_config() -> None:
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        raise EnvironmentError(
            "SUPABASE_URL과 SUPABASE_KEY 환경변수가 설정되지 않았습니다. "
            ".env 파일을 확인하세요."
        )


def fetch_blacklist() -> set[str]:
    """
    deleted_forms 테이블의 download_url 전체를 set으로 반환.
    스크래퍼 실행 시작 시 한 번만 호출하여 블랙리스트를 로드합니다.
    """
    _check_config()
    blacklist: set[str] = set()
    limit = 1000
    offset = 0
    url = f"{_SUPABASE_URL}/rest/v1/deleted_forms"
    while True:
        resp = requests.get(
            url,
            headers=_headers(conflict_ignore=False),
            params={"select": "download_url", "limit": limit, "offset": offset},
            timeout=30,
        )
        resp.raise_for_status()
        rows = resp.json()
        for row in rows:
            if row.get("download_url"):
                blacklist.add(row["download_url"])
        if len(rows) < limit:
            break
        offset += limit
    return blacklist


def upsert_gov_contracts(items: list[FormItem], blacklist: set[str] | None = None) -> int:
    """
    gov_contracts 테이블에 수집 항목을 저장합니다.
    download_url이 같은 항목은 무시(중복 방지).
    blacklist: fetch_blacklist()로 로드한 삭제 차단 URL 집합.
    반환값: 실제로 삽입된 건수
    """
    _check_config()
    if not items:
        return 0

    rows = [
        {
            "source": item.source,
            "title": item.title,
            "file_name": item.file_name,
            "file_format": item.file_format,
            "department": item.department,
            "registered_date": item.registered_date,
            "source_url": item.source_url,
            "download_url": item.file_url,
        }
        for item in items
        if item.file_url and (blacklist is None or item.file_url not in blacklist)
    ]

    if not rows:
        return 0

    url = f"{_SUPABASE_URL}/rest/v1/gov_contracts"
    resp = requests.post(url, headers=_headers(conflict_ignore=True), json=rows, timeout=30)
    # 409 = 전체가 중복 (이미 존재) → 정상 케이스
    if resp.status_code == 409:
        return 0
    resp.raise_for_status()
    return len(rows)


def upsert_legal_forms(items: list[dict], blacklist: set[str] | None = None) -> int:
    """
    legal_forms 테이블에 수집 항목을 저장합니다.
    download_url이 같은 항목은 무시(중복 방지).
    blacklist: fetch_blacklist()로 로드한 삭제 차단 URL 집합.

    items 딕셔너리 키:
      source, category_main, category_mid, title, file_format, download_url
    """
    _check_config()
    if not items:
        return 0

    rows = [
        {
            "source": item.get("source", ""),
            "category_main": item.get("category_main", ""),
            "category_mid": item.get("category_mid", ""),
            "title": item.get("title", ""),
            "file_format": item.get("file_format", ""),
            "download_url": item.get("download_url", ""),
            "source_url": item.get("source_url") or None,
        }
        for item in items
        if item.get("download_url") and (blacklist is None or item["download_url"] not in blacklist)
    ]

    if not rows:
        return 0

    url = f"{_SUPABASE_URL}/rest/v1/legal_forms"
    resp = requests.post(url, headers=_headers(conflict_ignore=True), json=rows, timeout=30)
    if resp.status_code == 409:
        return 0
    resp.raise_for_status()
    return len(rows)


def upload_to_storage(file_bytes: bytes, storage_path: str, bucket: str = "forms") -> str:
    """파일을 Supabase Storage에 업로드하고 공개 URL을 반환.

    storage_path: 버킷 내 경로 (예: "klac/abc123.hwp")
    bucket: 버킷 이름 (기본값: "forms")
    반환값: 공개 접근 가능한 URL
    """
    _check_config()
    service_key = _SUPABASE_SERVICE_KEY or _SUPABASE_KEY
    url = f"{_SUPABASE_URL}/storage/v1/object/{bucket}/{storage_path}"
    headers = {
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/octet-stream",
        "x-upsert": "true",
    }
    resp = requests.put(url, headers=headers, data=file_bytes, timeout=60)
    resp.raise_for_status()
    return f"{_SUPABASE_URL}/storage/v1/object/public/{bucket}/{storage_path}"


def log_scrape_entry(entry: dict) -> None:
    """
    scrape_logs 테이블에 수집 결과 1건을 즉시 기록합니다.

    entry 딕셔너리 키:
      run_id, ministry, status ('success'|'failed'|'skipped'),
      round_num, collected, inserted, error_msg
    """
    _check_config()
    row = {
        "run_id": entry["run_id"],
        "ministry": entry["ministry"],
        "status": entry["status"],
        "round_num": entry["round_num"],
        "collected": entry["collected"],
        "inserted": entry["inserted"],
        "error_msg": entry.get("error_msg"),
        "scraped_at": datetime.now(_KST).strftime("%Y-%m-%dT%H:%M:%S"),
    }
    url = f"{_SUPABASE_URL}/rest/v1/scrape_logs"
    resp = requests.post(url, headers=_headers(conflict_ignore=False), json=[row], timeout=30)
    resp.raise_for_status()
