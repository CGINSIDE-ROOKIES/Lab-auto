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
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

# legal_scraper 디렉터리를 sys.path에 추가
# (scrapers/klac_scraper.py 등이 'from config import ...' 형태로 임포트)
_LS_DIR = Path(__file__).parent / "legal_scraper"
if str(_LS_DIR) not in sys.path:
    sys.path.insert(0, str(_LS_DIR))


def _process_klac_rows(rows: list[dict]) -> list[dict]:
    """KLAC 항목의 HWP 파일을 다운로드 → QR 제거 → Storage 업로드 → URL 교체."""
    import hashlib
    import requests as _requests
    from utils.hwp_qr_remover import remove_qr
    from legal_scraper.utils.supabase_client import upload_to_storage

    processed = []
    for i, row in enumerate(rows, 1):
        original_url = row.get("다운로드URL", "")
        if not original_url:
            processed.append(row)
            continue

        # 원본 URL은 성공/실패 무관하게 항상 source_url로 기록
        row = {**row, "원본다운로드URL": original_url}

        # 원본 URL 해시로 Storage 경로 결정 (재실행 시 동일 경로 → 중복 방지)
        url_hash = hashlib.md5(original_url.encode()).hexdigest()
        storage_path = f"klac/{url_hash}.hwp"

        try:
            resp = _requests.get(original_url, timeout=30, verify=False)
            resp.raise_for_status()
            cleaned = remove_qr(resp.content)
            storage_url = upload_to_storage(cleaned, storage_path)
            row = {**row, "다운로드URL": storage_url}
            print(f"  [{i}/{len(rows)}] QR 제거 완료: {row.get('서식제목', '')[:30]}")
        except Exception as e:
            import traceback
            print(f"  [{i}/{len(rows)}] QR 제거 실패 (원본 URL 유지): {e}")
            traceback.print_exc()

        processed.append(row)
    return processed


def _run_legal(source: str | None = None) -> None:
    """법률서식 3곳(KLAC·ECFS·EKT) 수집 → Supabase 저장"""
    import datetime
    from scrapers import klac_scraper, ecfs_scraper, ekt_scraper
    from utils.ekt_proxy import start as _start_ekt_proxy
    from legal_scraper.utils.supabase_client import upsert_legal_forms, log_scrape_entry, fetch_blacklist

    _start_ekt_proxy()

    blacklist: set[str] = set()
    try:
        blacklist = fetch_blacklist()
        print(f"[INFO] 블랙리스트 {len(blacklist)}건 로드")
    except Exception as e:
        print(f"[WARN] 블랙리스트 로드 실패 (건너뜀): {e}")

    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_legal"

    def _to_supabase_rows(rows: list[dict], source_key: str) -> list[dict]:
        return [
            {
                "source": r.get("수집처", source_key),
                "category_main": r.get("대분류", ""),
                "category_mid": r.get("중분류", ""),
                "title": r.get("서식제목", ""),
                "file_format": r.get("파일형식", ""),
                "download_url": r.get("다운로드URL", ""),
                "source_url": r.get("원본다운로드URL") or None,
            }
            for r in rows
            if r.get("다운로드URL")
        ]

    all_sources = [
        ("KLAC", klac_scraper.scrape),
        ("ECFS", ecfs_scraper.scrape),
        ("EKT", ekt_scraper.scrape),
    ]
    sources = [(k, fn) for k, fn in all_sources if not source or k == source.upper()]

    total = 0
    for source_key, scrape_fn in sources:
        print(f"[START] {source_key} 수집 중...", flush=True)
        try:
            rows = scrape_fn()
            print(f"[DONE]  {source_key} — {len(rows)}건 수집", flush=True)
            if source_key == "KLAC":
                print(f"        QR 제거 + Storage 업로드 시작...", flush=True)
                rows = _process_klac_rows(rows)
            sb_rows = _to_supabase_rows(rows, source_key)
            inserted = upsert_legal_forms(sb_rows, blacklist=blacklist)
            print(f"        Supabase 저장 ({inserted}건 처리)", flush=True)
            total += inserted
            try:
                log_scrape_entry({"run_id": run_id, "ministry": source_key,
                    "status": "success", "round_num": 1,
                    "collected": len(rows), "inserted": inserted, "error_msg": None})
            except Exception:
                pass
        except EnvironmentError as e:
            print(f"[WARN] Supabase 저장 건너뜀: {e}")
        except Exception as e:
            print(f"[ERROR] {source_key}: {e}")
            try:
                log_scrape_entry({"run_id": run_id, "ministry": source_key,
                    "status": "failed", "round_num": 1,
                    "collected": 0, "inserted": 0, "error_msg": str(e)[:500]})
            except Exception:
                pass

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
    parser.add_argument(
        "--source",
        metavar="NAME",
        choices=["KLAC", "ECFS", "EKT"],
        help="법률서식 수집 시 특정 출처만 수집 (KLAC / ECFS / EKT)",
    )
    return parser.parse_args()


def main() -> None:
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    print("=== 수집 시작 ===", flush=True)
    args = parse_args()
    print(f"[CONFIG] target={args.target}", flush=True)

    if args.target in ("legal", "all"):
        print("[PHASE] 법률서식 수집 시작 (KLAC·ECFS·EKT)", flush=True)
        _run_legal(source=args.source)

    if args.target in ("gov", "all"):
        print("[PHASE] 정부부처 계약서 수집 시작", flush=True)
        _run_gov(ministry=args.ministry)


if __name__ == "__main__":
    main()
