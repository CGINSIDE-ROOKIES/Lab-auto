"""
EKT 다운로드 URL 생성 모듈

파일 다운로드는 Next.js API Route(/api/ekt-download)가 처리한다.
이 모듈은 스크래퍼에서 호출하는 proxy_url() 인터페이스만 유지한다.
"""


def start() -> None:
    """이전 버전 호환용 — 더 이상 로컬 프록시 서버를 기동하지 않음."""
    pass


def proxy_url(dvs_cd: str, file_ext: str) -> str:
    return f"/api/ekt-download?dvsCd={dvs_cd}&ext={file_ext}"
