# 법률서식 수집 플랫폼

한국 법률 포털 및 정부 각 부처 공식 홈페이지에서 법률서식·표준계약서·약정서를 자동 수집해 Supabase에 저장하고, Next.js 웹사이트에서 검색·다운로드할 수 있는 플랫폼입니다.

---

## 아키텍처

```
로컬 배치 실행 (수동)
  ├─ python main.py --target gov    # 24개 정부부처 수집
  └─ python main.py --target legal  # 법률서식 3곳 수집
         ↓
  Supabase PostgreSQL
  ├─ legal_forms     (법률서식)
  ├─ gov_contracts   (정부부처 계약서)
  ├─ scrape_logs     (수집 이력)
  └─ unified_forms   (통합 뷰)
         ↓
  Next.js 15 (web/) → Vercel 배포
  ├─ /       홈 — 총 건수 + 출처별 차트 + 최근 수집 현황
  └─ /legal  서식 목록 — 출처·형식 필터, 키워드 검색, 다운로드
```

---

## 설치

Python 3.12+ 및 [uv](https://github.com/astral-sh/uv) 필요

```bash
uv sync
playwright install chromium
```

---

## 수집 실행

```bash
# 정부부처 전체 수집 (3라운드 자동 retry)
uv run python -m legal_scraper.scrapers.gov_contracts.run_all

# 특정 부처만 수집
uv run python -m legal_scraper.scrapers.gov_contracts.run_all --ministry 법무부

# 키워드 지정 수집 (기본값 덮어쓰기)
uv run python -m legal_scraper.scrapers.gov_contracts.run_all --ministry 법무부 --keyword 서약서

# 파일 다운로드 없이 메타데이터만 수집
uv run python -m legal_scraper.scrapers.gov_contracts.run_all --no-download

# 법률서식 수집
uv run python main.py --target legal
```

---

## 수집 대상

### 법률서식 (3곳)

| 수집처 | 방식 |
|--------|------|
| 대한법률구조공단 (KLAC) | requests |
| 전자소송포털 (ECFS) | REST API |
| 전자공탁 (EKT) | REST API |

### 정부부처 계약서 (24개)

| 부처 | 수집 방식 |
|------|-----------|
| 감사원 | requests |
| 경찰청 | curl_cffi (safari) |
| 고용노동부 | playwright |
| 공정거래위원회 | requests |
| 관세청 | requests |
| 과학기술정보통신부 | playwright |
| 국가보훈부 | curl_cffi (chrome) |
| 국가유산청 | playwright |
| 국세청 | requests |
| 국토교통부 | requests |
| 농림축산식품부 | playwright |
| 농촌진흥청 | playwright |
| 문화체육관광부 | curl_cffi (chrome) |
| 법무부 | requests |
| 보건복지부 | playwright |
| 산림청 | curl_cffi (chrome) |
| 산업통상자원부 | playwright |
| 성평등가족부 | requests |
| 식품의약품안전처 | requests |
| 외교부 | requests |
| 중소벤처기업부 | requests |
| 지식재산처 | playwright |
| 행정안전부 | playwright |
| 행정중심복합도시건설청 | requests |

**수집 키워드**: `계약서`, `약정서`, `서약서` (외교부는 `촉탁서` 추가)

---

## 프로젝트 구조

```
legal_scraper/
├── scrapers/
│   ├── klac_scraper.py             # 대한법률구조공단
│   ├── ecfs_scraper.py             # 전자소송포털
│   ├── ekt_scraper.py              # 전자공탁
│   └── gov_contracts/
│       ├── base_scraper.py         # BaseGovScraper
│       ├── base_playwright_scraper.py
│       ├── run_all.py              # CLI 실행기 (3라운드 retry)
│       ├── config.py               # MINISTRIES 목록
│       ├── scrapers/               # 부처별 스크래퍼 24개
│       └── utils/
│           ├── file_filter.py      # CONTRACT_KEYWORDS 필터
│           ├── downloader.py       # 파일 다운로드
│           └── excel_writer.py
└── utils/
    └── supabase_client.py          # Supabase 저장 (PostgREST 직접 호출)

web/                                # Next.js 15 프론트엔드
├── app/
│   ├── page.tsx                    # 홈
│   ├── legal/                      # 서식 목록
│   └── api/ekt-download/           # EKT 프록시 API
└── components/
    └── DataTable.tsx
```

---

## 웹 개발 서버

```bash
cd web
npm install
npm run dev
```

`http://localhost:3000` 접속

---

## 환경변수

`.env` 파일에 아래 값 설정:

```
SUPABASE_URL=https://...supabase.co
SUPABASE_KEY=...
```

`web/.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=https://...supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

---

## 의존성

| 패키지 | 용도 |
|--------|------|
| `requests` | HTTP 요청 |
| `playwright` | JS 렌더링 필요 사이트 |
| `curl_cffi` | TLS 지문 차단 우회 |
| `beautifulsoup4` / `lxml` | HTML 파싱 |
| `openpyxl` | Excel 저장 |
