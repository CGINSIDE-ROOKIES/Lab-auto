# 법률서식 수집 플랫폼 — 개발자 소개

한국 정부 각 부처 공식 홈페이지와 법률서식 포털 3곳에서 계약서·약정서를 자동 수집해
Supabase에 저장하고, Next.js 웹에서 검색·다운로드할 수 있게 만드는 파이프라인입니다.

---

## 왜 만들었나

계약서·서약서 등 법률서식은 각 부처 홈페이지에 흩어져 있어 한 곳에서 검색하기 어렵습니다.
이 플랫폼은 27개 출처(부처 24 + 법률포털 3)를 단일 DB로 통합하고
웹 인터페이스에서 키워드·출처·형식으로 필터링해 다운로드할 수 있게 합니다.

---

## 전체 구조

```
로컬 배치 실행 (수동)
  ├─ python main.py --target gov    # 24개 정부부처 수집
  └─ python main.py --target legal  # 법률서식 3곳 수집
         ↓
  Supabase PostgreSQL
  ├─ legal_forms     — 법률서식 (KLAC·ECFS·EKT)
  ├─ gov_contracts   — 정부부처 계약서
  ├─ scrape_logs     — 수집 이력 (KST 타임스탬프)
  └─ unified_forms   — 통합 뷰 (프론트 전용)
         ↓
  Next.js 15 (web/) → Vercel 배포 예정
  ├─ /       홈 — 총 건수 + 출처별 차트 + 최근 수집 현황
  └─ /legal  서식 목록 — 출처·형식 필터, 키워드 검색, 다운로드
```

---

## 수집 대상 (27곳)

### 법률서식 포털 3곳

| 출처 | 수집 방식 | 특이사항 |
|------|-----------|----------|
| 대한법률구조공단 (KLAC) | requests | HWP 파일 QR 코드 제거 후 Storage 업로드 |
| 전자소송포털 (ECFS) | REST API | — |
| 전자공탁 (EKT) | REST API | 로컬 프록시 경유 다운로드 |

### 정부부처 24개

| 부처 | 스크래퍼 | 수집 방식 |
|------|----------|-----------|
| 감사원 | bai_scraper.py | requests |
| 경찰청 | police_scraper.py | curl_cffi (safari) |
| 고용노동부 | moel_scraper.py | playwright |
| 공정거래위원회 | ftc_scraper.py | requests |
| 관세청 | customs_scraper.py | requests |
| 과학기술정보통신부 | msit_scraper.py | playwright + POST JSON |
| 국가보훈부 | mpva_scraper.py | curl_cffi (chrome) |
| 국가유산청 | khs_scraper.py | playwright |
| 국세청 | nts_scraper.py | requests |
| 국토교통부 | molit_scraper.py | requests |
| 농림축산식품부 | mafra_scraper.py | playwright |
| 농촌진흥청 | rda_scraper.py | playwright |
| 문화체육관광부 | mcst_scraper.py | curl_cffi (chrome) |
| 법무부 | moj_scraper.py | requests |
| 보건복지부 | mohw_scraper.py | playwright |
| 산림청 | forest_scraper.py | curl_cffi (chrome) |
| 산업통상자원부 | motie_scraper.py | playwright |
| 성평등가족부 | mogef_scraper.py | requests + POST 다운로드 |
| 식품의약품안전처 | mfds_scraper.py | requests |
| 외교부 | mofa_scraper.py | requests + JSON API |
| 중소벤처기업부 | mss_scraper.py | requests |
| 지식재산처 | moip_scraper.py | playwright |
| 행정안전부 | mois_scraper.py | playwright |
| 행정중심복합도시건설청 | naacc_scraper.py | requests |

수집 키워드: `계약서` `약정서` `서약서` (외교부는 `촉탁서` 추가)
자동 제외: 이미지(jpg/png/gif), 엑셀(xlsx/xls), 제목에 `수의`·`합격`·`포스터` 포함

---

## 코드 구조

```
legal_scraper/
├── scrapers/
│   ├── klac_scraper.py             # 대한법률구조공단
│   ├── ecfs_scraper.py             # 전자소송포털
│   ├── ekt_scraper.py              # 전자공탁
│   └── gov_contracts/
│       ├── base_scraper.py         # BaseGovScraper (requests 기반)
│       ├── base_playwright_scraper.py
│       ├── run_all.py              # CLI 실행기 (3라운드 retry)
│       ├── config.py               # MINISTRIES 목록 (MinistryConfig)
│       ├── scrapers/               # 부처별 스크래퍼 24개
│       └── utils/
│           ├── file_filter.py      # CONTRACT_KEYWORDS, EXCLUDE_TITLE_KEYWORDS
│           ├── downloader.py       # 파일 다운로드 (GET/POST 분기)
│           └── excel_writer.py
└── utils/
    ├── supabase_client.py          # Supabase 저장 (PostgREST 직접 호출)
    └── hwp_qr_remover.py           # HWP QR 코드 제거

web/                                # Next.js 15 프론트엔드
├── app/
│   ├── page.tsx                    # 홈
│   ├── legal/                      # 서식 목록
│   └── api/ekt-download/           # EKT 프록시 API
└── components/
    └── DataTable.tsx

main.py                             # 최상위 CLI 진입점
```

---

## 스크래퍼 설계 패턴

모든 부처 스크래퍼는 두 기반 클래스 중 하나를 상속합니다.

```python
# requests 기반 (대부분)
class XxxScraper(BaseGovScraper):
    ministry_name = "부처명"

    def _init_session(self):
        super()._init_session()
        self.session.verify = False   # SSL 검증 비활성화 필요 시 여기에

    def scrape(self) -> list[FormItem]:
        items = []
        for page in range(1, ...):
            resp = self._request_with_retry(lambda: self.session.get(url, params=...))
            # 파싱 → items.append(FormItem(...))
            if self.on_progress:
                self.on_progress(len(items), f"{page}페이지 완료")
        return items

# JS 렌더링 필요 시
class XxxScraper(BasePlaywrightScraper):
    ...
```

핵심 규칙:
- `self.session.get()` 직접 호출 금지 → `_request_with_retry(lambda: ...)` 사용
- 세션 설정은 반드시 `_init_session()` 오버라이드 안에 (재시도 시 재초기화됨)
- `on_progress` 콜백으로 진행도 실시간 노출

---

## 기술 결정 사항 (Why)

### supabase-py 미사용
`requests`로 PostgREST API 직접 호출합니다.
의존성 최소화 + 동작을 완전히 제어하기 위해서입니다.

### 중복 제거 전략
`download_url UNIQUE + INSERT ON CONFLICT DO NOTHING`.
재실행해도 안전하게 멱등성이 보장됩니다.

### curl_cffi 사용 기준
일부 정부 사이트가 Python/헤드리스 크롬 TLS 지문을 차단합니다.
- `requests`에서 `ConnectionReset(10054)` → `curl_cffi` 전환
- `impersonate="chrome"` 우선, chrome도 차단 시 `"safari"` (경찰청 사례)

### Connection: close 전역 적용
NIA G-Cloud 공유 WAF가 같은 IP의 Keep-Alive 연속 요청을 TCP 강제 종료합니다.
`Connection: close` 헤더를 기본 헤더에 전역 설정해 매 요청마다 새 TCP 연결을 씁니다.

### 3라운드 retry
전체 일괄 수집 시 IP 누적 요청량으로 간헐적 차단이 발생합니다.
`run_all.py`는 0건 수집 + 연결 오류(`had_connection_error=True`) 부처만 골라 최대 3번 재시도합니다.

### Playwright + Windows 실행
`asyncio.ProactorEventLoop()`를 반드시 `threading.Thread` 안에서 생성·실행합니다.
(메인 스레드 asyncio 루프 점유 충돌 방지)

---

## 실행 방법

```bash
# 의존성 설치
uv sync
playwright install chromium

# 환경변수 (.env)
SUPABASE_URL=https://...supabase.co
SUPABASE_KEY=...

# 전체 수집
python main.py --target all

# 정부부처만 (3라운드 retry)
python main.py --target gov

# 특정 부처만
python main.py --target gov --ministry 보건복지부

# 특정 키워드 지정 (기본값 덮어쓰기)
uv run python -m legal_scraper.scrapers.gov_contracts.run_all --ministry 법무부 --keyword 서약서

# 파일 다운로드 없이 메타데이터만
uv run python -m legal_scraper.scrapers.gov_contracts.run_all --no-download

# 법률서식만
python main.py --target legal
```

---

## 새 스크래퍼 추가 체크리스트

1. `legal_scraper/scrapers/gov_contracts/scrapers/xxx_scraper.py` 작성
   - `BaseGovScraper` 또는 `BasePlaywrightScraper` 상속
   - `ministry_name` 클래스 변수 설정
   - `scrape() -> list[FormItem]` 구현
2. `legal_scraper/scrapers/gov_contracts/config.py` — `MINISTRIES` 리스트에 `MinistryConfig` 추가
3. `legal_scraper/scrapers/gov_contracts/run_all.py` — import 추가 + `scraper_map` 딕셔너리에 추가

---

## DB 스키마 (Supabase)

### `gov_contracts` 테이블

| 컬럼 | 의미 |
|------|------|
| `source` | 부처명 (출처) |
| `title` | 서식 제목 |
| `file_name` | 파일명 |
| `file_format` | 파일 확장자 |
| `download_url` | 다운로드 URL (UNIQUE) |

### `unified_forms` 뷰

프론트엔드가 직접 조회하는 통합 뷰입니다.
`legal_forms`와 `gov_contracts`를 UNION하며 alias를 고정해 프론트 인터페이스 안정성을 유지합니다.

| alias | 실제 컬럼 |
|-------|-----------|
| `source_name` | `source` |
| `form_title` | `title` |
| `doc_format` | `file_format` |

---

## 의존성

| 패키지 | 용도 |
|--------|------|
| `requests` | HTTP 요청 (대부분 부처) |
| `playwright` | JS 렌더링 필요 부처 |
| `curl_cffi` | TLS 지문 차단 우회 |
| `beautifulsoup4` / `lxml` | HTML 파싱 |
| `python-dotenv` | 환경변수 로드 |
| `openpyxl` | Excel 저장 |
| Next.js 15 + `@supabase/ssr` | 프론트엔드 |

---

## 현재 상태 및 남은 작업

| 항목 | 상태 |
|------|------|
| 스크래퍼 24개 | 완료 |
| 법률서식 3곳 | 완료 |
| Supabase 저장 + 로그 | 완료 |
| Next.js 웹 `/legal` 목록·필터 | 완료 |
| Vercel 배포 | 미완료 (web/ + env 등록 필요) |
| 수집 자동화 | 로컬 배치 수동 실행 (GitHub Actions 제거) |
