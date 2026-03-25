"""
부처 설정 모음
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ScrapeType = Literal["board_get", "board_post", "search_get", "playwright"]


@dataclass
class MinistryConfig:
    name: str
    scrape_type: ScrapeType
    base_url: str
    search_keyword: str = "계약서"
    notes: str = ""


MINISTRIES: list[MinistryConfig] = [
    # ── 유형 A: 정형 게시판 (requests + BS4) ──────────────────────
    MinistryConfig(
        name="공정거래위원회",
        scrape_type="board_get",
        base_url="https://www.ftc.go.kr/www/selectBbsNttList.do?bordCd=201&key=202",
        notes="정형 게시판 GET",
    ),
    MinistryConfig(
        name="중소벤처기업부",
        scrape_type="board_post",
        base_url="https://www.mss.go.kr/site/smba/ex/bbs/List.do?cbIdx=605",
        notes="전체 수집 후 필터",
    ),
    MinistryConfig(
        name="법무부",
        scrape_type="board_post",
        base_url="https://moj.go.kr/moj/3521/subview.do",
        notes="POST qt=계약서",
    ),
    # ── 유형 B: 검색 GET ──────────────────────────────────────────
    MinistryConfig(
        name="식품의약품안전처",
        scrape_type="search_get",
        base_url="https://www.mfds.go.kr/brd/m_212/list.do",
        search_keyword="계약",
        notes="srchWord=계약",
    ),
    MinistryConfig(
        name="국토교통부",
        scrape_type="search_get",
        base_url="https://www.molit.go.kr/search/search2023.jsp",
        search_keyword="표준계약서",
        notes="query=표준계약서",
    ),
    MinistryConfig(
        name="국세청",
        scrape_type="search_get",
        base_url="https://www.nts.go.kr/nts/ad/nf/nltFormatTotalApiList.do?mi=40178",
        notes="검색 GET",
    ),
    # ── 유형 C: JS 렌더링 (Playwright) ────────────────────────────
    MinistryConfig(
        name="과학기술정보통신부",
        scrape_type="playwright",
        base_url="https://www.msit.go.kr/search/ko/searchKo.do",
        notes="첨부파일 탭 XHR",
    ),
    MinistryConfig(
        name="행정안전부",
        scrape_type="playwright",
        base_url="https://www.mois.go.kr/srch.jsp",
        notes="fragment 방식",
    ),
    MinistryConfig(
        name="고용노동부",
        scrape_type="playwright",
        base_url="https://www.moel.go.kr/policy/policydata/list.do",
        notes="POST+JS렌더링",
    ),
    MinistryConfig(
        name="문화체육관광부",
        scrape_type="playwright",
        base_url="https://www.mcst.go.kr/site/search/search.jsp",
        notes="JS 렌더링",
    ),
    MinistryConfig(
        name="보건복지부",
        scrape_type="playwright",
        base_url="https://www.mohw.go.kr/react/search/search.jsp",
        notes="React 기반",
    ),
    MinistryConfig(
        name="농림축산식품부",
        scrape_type="playwright",
        base_url="https://www.mafra.go.kr/search/front/Search.jsp",
        notes="JS 렌더링",
    ),
    MinistryConfig(
        name="산업통상자원부",
        scrape_type="playwright",
        base_url="https://www.motie.go.kr/kor/search",
        notes="JS 렌더링",
    ),
    MinistryConfig(
        name="경찰청",
        scrape_type="playwright",
        base_url="https://www.police.go.kr/user/search/ND_searchResult.do",
        notes="JS 렌더링",
    ),
    MinistryConfig(
        name="국가유산청",
        scrape_type="playwright",
        base_url="https://search.khs.go.kr/srch_org/search/search_sub.jsp",
        notes="서브도메인",
    ),
    MinistryConfig(
        name="농촌진흥청",
        scrape_type="playwright",
        base_url="https://www.rda.go.kr/search/engineSearch.do",
        notes="JS 렌더링",
    ),
    MinistryConfig(
        name="지식재산처",
        scrape_type="playwright",
        base_url="https://www.moip.go.kr/ko/searchView.do",
        notes="JS 렌더링",
    ),
    # ── 유형 B: 검색 POST ─────────────────────────────────────────
    MinistryConfig(
        name="관세청",
        scrape_type="search_get",
        base_url="https://www.customs.go.kr/search/search.jsp",
        search_keyword="계약서",
        notes="POST searchField=SJ collection=attach, 관세청 전용 키워드",
    ),
    MinistryConfig(
        name="행정중심복합도시건설청",
        scrape_type="board_get",
        base_url="https://naacc.go.kr/WEB/contents/N4040200000.do",
        search_keyword="계약",
        notes="GET schStr=키워드, 상세 페이지에서 첨부파일 수집",
    ),
    MinistryConfig(
        name="산림청",
        scrape_type="search_get",
        base_url="https://www.forest.go.kr/kfsweb/kfs/search.do",
        search_keyword="계약서",
        notes="GET category=CMS, 상세페이지에서 FileDown.do 수집, curl_cffi chrome",
    ),
    MinistryConfig(
        name="외교부",
        scrape_type="search_get",
        base_url="https://search.mofa.go.kr/search/consulSearch.do",
        search_keyword="촉탁서",
        notes="POST JSON API, attach_embd_ko 컬렉션, 파일명 기준 중복 제거",
    ),
    MinistryConfig(
        name="국가보훈부",
        scrape_type="search_get",
        base_url="https://www.mpva.go.kr/search/search.jsp",
        search_keyword="계약서",
        notes="GET collection=minwon (민원/보상 탭), 상세페이지 p-attach 첨부파일, curl_cffi chrome",
    ),
    MinistryConfig(
        name="성평등가족부",
        scrape_type="board_post",
        base_url="https://www.mogef.go.kr/as/asl/as_asl_s001.do",
        search_keyword="계약",
        notes="POST searchTerm=키워드, 카테고리(NEWS/SUB/INFO/ETC/EDU) 순회, fn_fileDownload 파싱",
    ),
]
