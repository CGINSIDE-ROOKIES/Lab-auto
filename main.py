"""
법률서식 수집 플랫폼 — CLI 진입점

사용법:
    python main.py --target all
    python main.py --target legal
    python main.py --target gov
    python main.py --target gov --ministry 보건복지부
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Windows cp949 콘솔에서 한글/특수문자 인코딩 오류 방지
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# legal_scraper 디렉터리를 sys.path에 추가
# (scrapers/klac_scraper.py 등이 'from config import ...' 형태로 임포트)
_LS_DIR = Path(__file__).parent / "legal_scraper"
if str(_LS_DIR) not in sys.path:
    sys.path.insert(0, str(_LS_DIR))


def _run_legal() -> None:
    """법률서식 3곳(KLAC·ECFS·EKT) 수집 → Supabase 저장"""
    from scrapers import klac_scraper, ecfs_scraper, ekt_scraper
    from utils.ekt_proxy import start as _start_ekt_proxy
    from legal_scraper.utils.supabase_client import upsert_legal_forms

    _start_ekt_proxy()

    def _to_supabase_rows(rows: list[dict], source_key: str) -> list[dict]:
        return [
            {
                "source": r.get("수집처", source_key),
                "category_main": r.get("대분류", ""),
                "category_mid": r.get("중분류", ""),
                "title": r.get("서식제목", ""),
                "file_format": r.get("파일형식", ""),
                "download_url": r.get("다운로드URL", ""),
            }
            for r in rows
            if r.get("다운로드URL")
        ]

    sources = [
        ("KLAC", klac_scraper.scrape),
        ("ECFS", ecfs_scraper.scrape),
        ("EKT", ekt_scraper.scrape),
    ]

    total = 0
    for source_key, scrape_fn in sources:
        print(f"[START] {source_key} 수집 중...")
        try:
            rows = scrape_fn()
            print(f"[DONE]  {source_key} — {len(rows)}건 수집")
            sb_rows = _to_supabase_rows(rows, source_key)
            inserted = upsert_legal_forms(sb_rows)
            print(f"        Supabase 저장 ({inserted}건 처리)")
            total += inserted
        except EnvironmentError as e:
            print(f"[WARN] Supabase 저장 건너뜀: {e}")
        except Exception as e:
            print(f"[ERROR] {source_key}: {e}")

    print(f"\n법률서식 완료 — 총 {total}건 처리")


def _run_gov(ministry: str | None = None) -> None:
    """정부부처 계약서 수집 → Supabase 저장"""
    # run_all.py의 main()이 이미 Supabase 저장을 포함하므로 인자를 맞춰 호출
    import importlib
    import sys as _sys

    # run_all.parse_args()가 sys.argv를 직접 읽으므로 잠시 교체
    orig_argv = _sys.argv[:]
    _sys.argv = [orig_argv[0], "--no-download"]
    if ministry:
        _sys.argv += ["--ministry", ministry]

    try:
        from legal_scraper.scrapers.gov_contracts.run_all import main as gov_main
        gov_main()
    finally:
        _sys.argv = orig_argv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="법률서식 수집 플랫폼 CLI")
    parser.add_argument(
        "--target",
        choices=["all", "legal", "gov"],
        default="all",
        help="수집 대상 (기본값: all)",
    )
    parser.add_argument(
        "--ministry",
        metavar="NAME",
        help="정부부처 수집 시 특정 부처만 수집 (예: 보건복지부)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.target in ("legal", "all"):
        _run_legal()

    if args.target in ("gov", "all"):
        _run_gov(ministry=args.ministry)


if __name__ == "__main__":
    main()
