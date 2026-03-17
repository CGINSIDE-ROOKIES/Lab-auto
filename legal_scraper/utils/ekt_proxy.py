"""
EKT 파일 다운로드 프록시 서버

배경: ekt.scourt.go.kr/pjg/pjgedm/blobDown.on 은 JSON POST 전용이라
브라우저(Excel) URL 클릭(GET)으로는 파일을 받을 수 없음.
이 모듈은 GET 요청을 받아 내부적으로 POST 변환 후 파일 스트림을 반환하는
경량 HTTP 서버를 백그라운드 스레드로 실행한다.

실행 후 URL 형태:  http://localhost:8601/ekt?dvsCd=22&ext=hwp
"""
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import requests

from config import EKT_DOWNLOAD_BASE, HEADERS

log = logging.getLogger("legal_scraper.ekt_proxy")

PROXY_PORT = 8601
_REFERER = "https://ekt.scourt.go.kr/pjg/index.on?m=PJG172M03"

_FILE_COL = {
    "hwp":  "dpsHwpFrmlFile",
    "doc":  "dpsDocxFrmlFile",
    "pdf":  "dpsPdfFrmlFile",
    "gif":  "dpsWrtExmFile",
}

_server: HTTPServer | None = None
_lock = threading.Lock()


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        dvs_cd   = qs.get("dvsCd", [""])[0]
        file_ext = qs.get("ext",   [""])[0]
        file_col = _FILE_COL.get(file_ext, "")

        if not dvs_cd or not file_ext:
            self.send_error(400, "dvsCd, ext 파라미터 필요")
            return

        try:
            session = requests.Session()
            session.headers.update({**HEADERS, "Referer": _REFERER})
            session.get(_REFERER, timeout=15)
            resp = session.post(
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
        except Exception as e:
            log.error(f"EKT proxy 오류: {e}")
            self.send_error(502, str(e))
            return

        if resp.status_code != 200 or len(resp.content) < 100:
            self.send_error(502, f"EKT 서버 응답 오류: {resp.status_code}")
            return

        cd = resp.headers.get("Content-Disposition",
                               f'attachment; filename="file.{file_ext}"')
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", cd)
        self.send_header("Content-Length", str(len(resp.content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(resp.content)

    def log_message(self, fmt, *args):  # 로그 억제
        pass


def start():
    """프록시 서버를 백그라운드 데몬 스레드로 기동. 이미 실행 중이면 무시."""
    global _server
    with _lock:
        if _server is not None:
            return PROXY_PORT
        try:
            _server = HTTPServer(("localhost", PROXY_PORT), _Handler)
            t = threading.Thread(target=_server.serve_forever, daemon=True)
            t.start()
            log.info(f"EKT 다운로드 프록시 시작: http://localhost:{PROXY_PORT}")
        except OSError:
            # 이미 포트가 사용 중 → 다른 프로세스(기존 앱)가 실행 중
            log.info(f"EKT 프록시 포트 {PROXY_PORT} 이미 사용 중 — 기존 서버 활용")
    return PROXY_PORT


def proxy_url(dvs_cd: str, file_ext: str) -> str:
    return f"http://localhost:{PROXY_PORT}/ekt?dvsCd={dvs_cd}&ext={file_ext}"
