"""
정부부처 표준계약서 전체 수집 실행기

사용법:
    python -m scrapers.gov_contracts.run_all
    python -m scrapers.gov_contracts.run_all --ministry 공정거래위원회
    python -m scrapers.gov_contracts.run_all --type playwright --no-download
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (단독 실행 시)
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from legal_scraper.scrapers.gov_contracts.config import MINISTRIES, MinistryConfig
from legal_scraper.scrapers.gov_contracts.utils.excel_writer import save_to_excel

DOWNLOAD_BASE = "downloads/gov_contracts"
OUTPUT_EXCEL = "outputs/gov_contracts_metadata.xlsx"

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
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="정부부처 표준계약서 수집기")
    parser.add_argument(
        "--ministry",
        metavar="NAME",
        help="특정 부처만 수집 (예: 공정거래위원회)",
    )
    parser.add_argument(
        "--type",
        dest="scrape_type",
        metavar="TYPE",
        choices=["board_get", "board_post", "search_get", "playwright", "direct_url"],
        help="특정 유형만 수집",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="파일 다운로드 생략 (메타데이터만 수집)",
    )
    return parser.parse_args()


def _get_targets(args: argparse.Namespace) -> list[MinistryConfig]:
    targets = MINISTRIES[:]
    if args.ministry:
        targets = [m for m in targets if m.name == args.ministry]
    if args.scrape_type:
        targets = [m for m in targets if m.scrape_type == args.scrape_type]
    return targets


def main() -> None:
    args = parse_args()
    targets = _get_targets(args)

    if not targets:
        print("수집 대상 부처가 없습니다.")
        sys.exit(1)

    all_items = []

    for ministry_cfg in targets:
        name = ministry_cfg.name
        scraper_cls = scraper_map.get(name)

        if scraper_cls is None:
            print(f"[SKIP] {name} — 스크래퍼 미구현")
            continue

        print(f"[START] {name}")
        try:
            scraper = scraper_cls()
            items = scraper.run()
            print(f"[DONE]  {name} — {len(items)}건 수집")

            if not args.no_download:
                from legal_scraper.scrapers.gov_contracts.utils.downloader import download_file

                dl_dir = Path(DOWNLOAD_BASE) / name
                for item in items:
                    if item.file_url:
                        try:
                            local = download_file(
                                item.file_url,
                                dl_dir,
                                session=scraper.session,
                            )
                            item.local_path = local
                        except Exception as e:
                            print(f"  [WARN] 다운로드 실패 {item.file_url}: {e}")

            all_items.extend(items)

        except Exception as e:
            print(f"[ERROR] {name}: {e}")

    if all_items:
        save_to_excel(all_items, OUTPUT_EXCEL)
        print(f"\n총 {len(all_items)}건 저장 → {OUTPUT_EXCEL}")
    else:
        print("\n수집 결과 없음")


if __name__ == "__main__":
    main()
