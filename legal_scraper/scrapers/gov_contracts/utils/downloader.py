"""
파일 다운로드 유틸리티
"""
from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import Optional

import requests


def _extract_filename_from_cd(content_disposition: str) -> str:
    """Content-Disposition 헤더에서 파일명 추출 (EUC-KR 처리 포함)"""
    # RFC 5987 형식: filename*=UTF-8''encoded
    match = re.search(r"filename\*=([^;]+)", content_disposition)
    if match:
        raw = match.group(1).strip()
        try:
            charset, _, encoded = raw.split("'", 2)
            return urllib.parse.unquote(encoded, encoding=charset or "utf-8")
        except ValueError:
            pass

    # 일반 filename= 형식
    match = re.search(r'filename=["\']?([^"\';\r\n]+)["\']?', content_disposition)
    if match:
        raw = match.group(1).strip().strip('"\'')
        # 비ASCII 바이트가 있으면 EUC-KR 직접 인코딩 가능성 (오래된 서버)
        try:
            raw_bytes = raw.encode("latin-1")
            if any(b > 0x7F for b in raw_bytes):
                try:
                    return raw_bytes.decode("euc-kr")
                except UnicodeDecodeError:
                    pass
        except UnicodeEncodeError:
            pass
        # ASCII percent-encoding 처리 (현대적 서버)
        try:
            return urllib.parse.unquote(raw, encoding="utf-8")
        except Exception:
            pass
        return raw

    return ""


def download_file(
    url: str,
    save_dir: str | Path,
    session: Optional[requests.Session] = None,
    filename: Optional[str] = None,
) -> str:
    """
    파일을 다운로드하고 로컬 경로를 반환한다.

    - Content-Disposition 헤더에서 파일명 추출 (EUC-KR 처리 포함)
    - 없으면 URL 끝에서 추출
    - 이미 존재하면 스킵 (중복 방지)
    - 저장 경로(str) 반환
    """
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    client = session or requests.Session()
    client.headers.setdefault(
        "User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36",
    )

    resp = client.get(url, stream=True, timeout=60)
    resp.raise_for_status()

    if not filename:
        cd = resp.headers.get("Content-Disposition", "")
        if cd:
            filename = _extract_filename_from_cd(cd)

    if not filename:
        parsed = urllib.parse.urlparse(url)
        filename = urllib.parse.unquote(parsed.path.rstrip("/").rsplit("/", 1)[-1])

    if not filename:
        filename = "unknown_file"

    # 파일명에 사용 불가 문자 제거 (Windows 호환)
    filename = re.sub(r'[\\/:*?"<>|]', "_", filename)
    # 파일명 길이 제한 (Windows MAX_PATH 고려, 확장자 보존)
    if len(filename) > 200:
        if "." in filename:
            stem, ext = filename.rsplit(".", 1)
            filename = stem[: 195 - len(ext)] + "." + ext
        else:
            filename = filename[:200]

    save_path = save_dir / filename

    if save_path.exists():
        return str(save_path)

    with open(save_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return str(save_path)
