# ── 대한법률구조공단 ─────────────────────────────────────────────
KLAC_URL  = "https://www.klac.or.kr/legalinfo/legalFrm.do"
KLAC_NAME = "대한법률구조공단"

# ── 전자소송포털 양식모음 ────────────────────────────────────────
ECFS_API_URL       = "https://ecfs.scourt.go.kr/psp/psp720/selectNboardList.on"
ECFS_DOWNLOAD_BASE = "https://file.scourt.go.kr/AttachDownload?path=004&file={filename}"
ECFS_NAME          = "전자소송포털"
ECFS_PAGE_SIZE     = 100

# ── 전자공탁 공탁양식 ────────────────────────────────────────────
EKT_API_URL        = "https://ekt.scourt.go.kr/pjg/pjg172/selectEdpsFrmlLst.on"
EKT_DOWNLOAD_BASE  = "https://ekt.scourt.go.kr/pjg/pjgedm/blobDown.on"
EKT_NAME           = "전자소송포털"
EKT_PAGE_SIZE      = 100

# ── 공통 ─────────────────────────────────────────────────────────
REQUEST_DELAY = (1.0, 2.0)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
