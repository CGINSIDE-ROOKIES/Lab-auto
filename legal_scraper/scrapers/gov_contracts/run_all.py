"""
정부부처 표준계약서 전체 수집 실행기

사용법:
    python -m scrapers.gov_contracts.run_all
    python -m scrapers.gov_contracts.run_all --ministry 공정거래위원회
    python -m scrapers.gov_contracts.run_all --type playwright --no-download

재시도 전략:
    Round 1: 전체 실행
    Round 2: 실패분 재시도 - 라운드 내 마지막 실패로부터 3분 미만 경과 시 나머지만 대기
    Round 3: 잔여 실패분 재시도 - 동일하게 5분 기준 적용
    이후에도 실패 시 exit code 1 (GitHub Actions 이메일 트리거)
"""
from __future__ import annotations

import argparse
import datetime
import sys
import time
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (단독 실행 시)
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from legal_scraper.scrapers.gov_contracts.config import MINISTRIES, MinistryConfig
from legal_scraper.scrapers.gov_contracts.utils.excel_writer import save_to_excel
from legal_scraper.utils.supabase_client import upsert_gov_contracts, log_scrape_entry

DOWNLOAD_BASE = "downloads/gov_contracts"
OUTPUT_EXCEL = "outputs/gov_contracts_metadata.xlsx"

# 라운드별 대기 시간 (초). 인덱스 0 = Round 2 전, 1 = Round 3 전
RETRY_WAITS = [3 * 60, 5 * 60]
MAX_ROUNDS = 3

# ── 부처별 스크래퍼 매핑 ──────────────────────────────────────────────
from legal_scraper.scrapers.gov_contracts.scrapers.ftc_scraper import FtcScraper
from legal_scraper.scrapers.gov_contracts.scrapers.moj_scraper import MojScraper
from legal_scraper.scrapers.gov_contracts.scrapers.mogef_scraper import MogefScraper
from legal_scraper.scrapers.gov_contracts.scrapers.msit_scraper import MsitScraper
from legal_scraper.scrapers.gov_contracts.scrapers.mcst_scraper import McstScraper
from legal_scraper.scrapers.gov_contracts.scrapers.motie_scraper import MotieScraper
from legal_scraper.scrapers.gov_contracts.scrapers.police_scraper import PoliceScraper
from legal_scraper.scrapers.gov_contracts.scrapers.mohw_scraper import MohwScraper
from legal_scraper.scrapers.gov_contracts.scrapers.mafra_scraper import MafraScraper
from legal_scraper.scrapers.gov_contracts.scrapers.nts_scraper import NtsScraper
from legal_scraper.scrapers.gov_contracts.scrapers.mss_scraper import MssScraper
from legal_scraper.scrapers.gov_contracts.scrapers.khs_scraper import KhsScraper
from legal_scraper.scrapers.gov_contracts.scrapers.moip_scraper import MoipScraper
from legal_scraper.scrapers.gov_contracts.scrapers.rda_scraper import RdaScraper
from legal_scraper.scrapers.gov_contracts.scrapers.molit_scraper import MolitScraper
from legal_scraper.scrapers.gov_contracts.scrapers.mfds_scraper import MfdsScraper
from legal_scraper.scrapers.gov_contracts.scrapers.mois_scraper import MoisScraper
from legal_scraper.scrapers.gov_contracts.scrapers.bai_scraper import BaiScraper
from legal_scraper.scrapers.gov_contracts.scrapers.moel_scraper import MoelScraper
from legal_scraper.scrapers.gov_contracts.scrapers.customs_scraper import CustomsScraper
from legal_scraper.scrapers.gov_contracts.scrapers.naacc_scraper import NaaccScraper
from legal_scraper.scrapers.gov_contracts.scrapers.forest_scraper import ForestScraper
from legal_scraper.scrapers.gov_contracts.scrapers.mofa_scraper import MofaScraper
from legal_scraper.scrapers.gov_contracts.scrapers.mpva_scraper import MpvaScraper

scraper_map: dict[str, type] = {
    "공정거래위원회": FtcScraper,
    "법무부": MojScraper,
    "성평등가족부": MogefScraper,
    "과학기술정보통신부": MsitScraper,
    "문화체육관광부": McstScraper,
    "산업통상자원부": MotieScraper,
    "경찰청": PoliceScraper,
    "보건복지부": MohwScraper,
    "농림축산식품부": MafraScraper,
    "국세청": NtsScraper,
    "중소벤처기업부": MssScraper,
    "국가유산청": KhsScraper,
    "지식재산처": MoipScraper,
    "농촌진흥청": RdaScraper,
    "국토교통부": MolitScraper,
    "식품의약품안전처": MfdsScraper,
    "행정안전부": MoisScraper,
    "감사원": BaiScraper,
    "고용노동부": MoelScraper,
    "관세청": CustomsScraper,
    "행정중심복합도시건설청": NaaccScraper,
    "산림청": ForestScraper,
    "외교부": MofaScraper,
    "국가보훈부": MpvaScraper,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="정부부처 표준계약서 수집기")
    parser.add_argument("--ministry", metavar="NAME", help="특정 부처만 수집")
    parser.add_argument(
        "--type",
        dest="scrape_type",
        metavar="TYPE",
        choices=["board_get", "board_post", "search_get", "playwright", "direct_url"],
        help="특정 유형만 수집",
    )
    parser.add_argument("--no-download", action="store_true", help="파일 다운로드 생략")
    return parser.parse_args()


def _get_targets(args: argparse.Namespace) -> list[MinistryConfig]:
    targets = MINISTRIES[:]
    if args.ministry:
        targets = [m for m in targets if m.name == args.ministry]
    if args.scrape_type:
        targets = [m for m in targets if m.scrape_type == args.scrape_type]
    return targets


def _run_one(name: str, args: argparse.Namespace) -> tuple[list, str | None]:
    """단일 부처 수집 + 로컬 다운로드. (items, error_msg) 반환."""
    scraper_cls = scraper_map.get(name)
    if scraper_cls is None:
        return [], None  # 미구현 → 에러 아님

    scraper = scraper_cls()
    items = scraper.run()

    if not args.no_download:
        from legal_scraper.scrapers.gov_contracts.utils.downloader import download_file
        dl_dir = Path(DOWNLOAD_BASE) / name
        for item in items:
            if item.file_url:
                try:
                    item.local_path = download_file(
                        item.file_url, dl_dir, session=scraper.session,
                        post_data=item.download_post_data,
                    )
                except Exception as e:
                    print(f"  [WARN] 다운로드 실패 {item.file_url}: {e}")

    # 0건 수집 + 연결 오류 발생 → 상위로 예외를 던져 retry 대상에 포함
    if len(items) == 0 and getattr(scraper, 'had_connection_error', False):
        raise ConnectionError(f"{name}: 연결 오류로 0건 수집, 재시도 필요")

    return items, None


def main() -> None:
    args = parse_args()
    targets = _get_targets(args)

    if not targets:
        print("수집 대상 부처가 없습니다.")
        sys.exit(1)

    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    all_items: list = []
    pending = list(targets)

    last_failure_time: float | None = None

    for round_num in range(1, MAX_ROUNDS + 1):
        if round_num > 1:
            wait_sec = RETRY_WAITS[round_num - 2]
            elapsed = time.time() - (last_failure_time or time.time())
            remaining = max(0.0, wait_sec - elapsed)
            if remaining > 0:
                print(f"\n[RETRY] 실패 {len(pending)}건 - {remaining:.0f}초 추가 대기 후 Round {round_num} 시작"
                      f" (경과 {elapsed:.0f}초 / 기준 {wait_sec}초)")
                time.sleep(remaining)
            else:
                print(f"\n[RETRY] 실패 {len(pending)}건 - 이미 {elapsed:.0f}초 경과, 즉시 Round {round_num} 시작")

        still_failed: list[MinistryConfig] = []
        last_failure_time = None  # 라운드마다 초기화

        for ministry_cfg in pending:
            name = ministry_cfg.name

            if scraper_map.get(name) is None:
                print(f"[SKIP] {name} - 스크래퍼 미구현")
                try:
                    log_scrape_entry({"run_id": run_id, "ministry": name,
                        "status": "skipped", "round_num": round_num,
                        "collected": 0, "inserted": 0, "error_msg": None})
                except Exception:
                    pass
                continue

            label = f"(Round {round_num})" if round_num > 1 else ""
            print(f"[START] {name} {label}".rstrip())
            try:
                items, _ = _run_one(name, args)
                print(f"[DONE]  {name} - {len(items)}건 수집")

                # 부처별로 바로 Supabase 저장 (실패해도 다음 부처 계속)
                inserted = 0
                try:
                    inserted = upsert_gov_contracts(items)
                except EnvironmentError:
                    pass  # .env 없는 환경 (로컬 테스트 등)
                except Exception as e:
                    print(f"  [WARN] Supabase 저장 실패: {e}")

                all_items.extend(items)
                try:
                    log_scrape_entry({"run_id": run_id, "ministry": name,
                        "status": "success", "round_num": round_num,
                        "collected": len(items), "inserted": inserted, "error_msg": None})
                except Exception:
                    pass

            except Exception as e:
                err = str(e)[:500]  # 너무 긴 에러 메시지 자르기
                print(f"[ERROR] {name}: {err}")
                last_failure_time = time.time()
                still_failed.append(ministry_cfg)
                try:
                    log_scrape_entry({"run_id": run_id, "ministry": name,
                        "status": "failed", "round_num": round_num,
                        "collected": 0, "inserted": 0, "error_msg": err})
                except Exception:
                    pass

        pending = still_failed
        if not pending:
            break

    # Excel 저장 (전체 합산)
    if all_items:
        save_to_excel(all_items, OUTPUT_EXCEL)
        print(f"\n총 {len(all_items)}건 수집 -> {OUTPUT_EXCEL}")


    # 최종 실패 보고
    if pending:
        failed_names = [m.name for m in pending]
        print(f"\n[FAIL] 최대 재시도({MAX_ROUNDS}회) 후에도 실패: {', '.join(failed_names)}")
        sys.exit(1)  # GitHub Actions 실패 처리 → 이메일 발송
    else:
        print("\n[완료] 모든 부처 수집 성공")


if __name__ == "__main__":
    main()
