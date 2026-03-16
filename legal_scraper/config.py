from pathlib import Path

BASE_DIR = Path(__file__).parent

# ── 디렉터리 ─────────────────────────────────────────────────────
DATA_DIR   = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR   = BASE_DIR / "logs"

for _d in [DATA_DIR, OUTPUT_DIR, LOGS_DIR]:
    _d.mkdir(exist_ok=True)

SNAPSHOT_FILE  = DATA_DIR / "snapshot.json"
TAXONOMY_FILE  = DATA_DIR / "분류체계.xlsx"
TAXONOMY_SHEET = "분류체계(키워드포함)"

# ── 사이트 1: 대한법률구조공단 ──────────────────────────────────
KLAC_URL  = "https://www.klac.or.kr/legalinfo/legalFrm.do"
KLAC_NAME = "대한법률구조공단"

# ── 사이트 2: 전자소송포털 양식모음 ─────────────────────────────
ECFS_API_URL      = "https://ecfs.scourt.go.kr/psp/psp720/selectNboardList.on"
ECFS_DOWNLOAD_BASE = "https://file.scourt.go.kr/AttachDownload?path=004&file={filename}"
ECFS_NAME         = "전자소송포털"
ECFS_PAGE_SIZE    = 100

# ── 사이트 3: 전자공탁 공탁양식 ─────────────────────────────────
EKT_API_URL      = "https://ekt.scourt.go.kr/pjg/pjg172/selectEdpsFrmlLst.on"
EKT_DOWNLOAD_BASE = "https://ekt.scourt.go.kr/pjg/pjgedm/blobDown.on"
EKT_NAME         = "전자소송포털"
EKT_PAGE_SIZE    = 100

# ── 공통 ─────────────────────────────────────────────────────────
REQUEST_DELAY = (1.0, 2.0)   # (min, max) seconds

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# 수집 결과 컬럼
RAW_COLUMNS = [
    "일련번호", "수집처", "대분류", "중분류",
    "서식제목", "파일형식", "다운로드URL", "수집일시",
]

# 분류 결과 컬럼
CLASSIFIED_COLUMNS = [
    "일련번호", "수집처", "원본대분류", "원본중분류",
    "서식제목", "파일형식",
    "최종대분류", "최종중분류", "소분류", "세분류",
    "다운로드URL", "수집일시", "분류방법", "분류상태",
]
