# 법률서식 수집 시스템

한국 법률 포털 및 정부 각 부처 공식 홈페이지에서 법률서식·표준계약서·약정서를 자동 수집하는 스크래퍼 시스템입니다.

## 기능

- **법률서식 수집**: 대한법률구조공단·전자소송포털·전자공탁에서 법률서식 수집 및 자동 분류
- **정부부처 계약서 수집**: 19개 부처 공식 홈페이지에서 표준계약서·약정서 수집
- **Streamlit 웹 UI**: 실시간 수집 진행 → 결과 미리보기 → Excel 다운로드
- **CLI 실행**: 전체 또는 특정 부처만 선택 수집
- **증분 수집**: snapshot 기반 신규 항목 감지
- **Excel 저장**: 수집 결과를 `outputs/gov_contracts_metadata.xlsx`에 누적 저장

---

## 설치

Python 3.14+ 및 [uv](https://github.com/astral-sh/uv) 필요

```bash
uv sync
playwright install chromium
```

---

## 실행

### 웹 UI (Streamlit)

```bash
uv run streamlit run legal_scraper/app.py
```

브라우저에서 `http://localhost:8501` 접속 후 사이드바에서 수집 페이지 선택

### CLI (정부부처 계약서)

```bash
# 전체 부처 수집
uv run python -m legal_scraper.scrapers.gov_contracts.run_all

# 특정 부처만 수집
uv run python -m legal_scraper.scrapers.gov_contracts.run_all --ministry 공정거래위원회

# 파일 다운로드 없이 메타데이터만 수집
uv run python -m legal_scraper.scrapers.gov_contracts.run_all --no-download

# 특정 수집 방식만 실행
uv run python -m legal_scraper.scrapers.gov_contracts.run_all --type playwright
```

---

## 법률서식 수집

| 수집처 | 서식 수 |
|--------|---------|
| 대한법률구조공단 | ~2,147개 |
| 전자소송포털 | ~983개 |
| 전자공탁 | ~59개 |

### 사용 흐름

1. **사이드바**: `분류체계.xlsx` 업로드 (또는 `data/` 폴더에 직접 배치)
2. **스크래핑 탭**: "전체 스크래핑 시작" 클릭 → 사이트별 진행 바로 실시간 확인 → 완료 후 신규 항목 미리보기 + 엑셀 다운로드
3. **분류 탭**: 자동 분류 실행 → 색상 구분 테이블 (초록=분류완료 / 노랑=부분일치 / 빨강=검토필요) → 분류 결과 엑셀 다운로드

> **샘플 모드**: 사이드바 "샘플 모드" 체크박스로 사이트당 1페이지(~10건)만 빠르게 테스트

### 분류체계.xlsx 준비

- `data/` 폴더에 배치하거나 사이드바에서 업로드
- 파일 내 **2번 시트** 이름: `분류체계(키워드포함)`
- 필수 컬럼: `대분류`, `중분류`, `소분류`, `세분류`, `키워드`
- `키워드` 형식: 실제 서식 제목을 파이프(`|`)로 구분

### 결과 파일

| 파일 | 설명 |
|------|------|
| `output/legal_forms_YYYYMMDD.xlsx` | 수집 결과 (신규 항목) |
| `output/legal_forms_classified_YYYYMMDD.xlsx` | 분류 결과 |
| `data/snapshot.json` | 수집 이력 (증분 수집용) |
| `logs/scraper.log` | 상세 로그 |

---

## 정부부처 계약서 수집

### 지원 부처 (19개)

| 부처 | 수집 방식 | 수집 건수 |
|------|-----------|-----------|
| 공정거래위원회 | requests | 217 |
| 법무부 | requests | 98 |
| 성평등가족부 | requests | 87 |
| 과학기술정보통신부 | requests | 86 |
| 문화체육관광부 | curl_cffi | 81 |
| 산업통상자원부 | Playwright | 29 |
| 보건복지부 | Playwright | 11 |
| 국가유산청 | Playwright | 18 |
| 농림축산식품부 | requests | 8 |
| 국세청 | requests | 5 |
| 중소벤처기업부 | Playwright | 5 |
| 지식재산처 | Playwright | 4 |
| 농촌진흥청 | Playwright | 4 |
| 식품의약품안전처 | requests | 3 |
| 국토교통부 | requests | 3 |
| 행정안전부 | Playwright | 2 |
| 감사원 | requests | 1 |
| 경찰청 | curl_cffi | - |
| 고용노동부 | requests | 0 |

### 수집 규칙

- **키워드 필터**: 파일명에 `계약` 또는 `약정서` 포함된 항목만 수집
- **판단 순서**: `file_name` 우선, 없으면 `title` 검사
- **이미지 제외**: jpg, jpeg, png, gif 등 이미지 파일 자동 제외
- **부처별 전용 키워드**: `filter_by_keyword()` 오버라이드로 독립 운용 가능
  - 법무부: `["계약서"]`
  - 경찰청: `["무기계약"]`

### 수집 데이터 필드

| 필드 | 설명 |
|------|------|
| ministry | 부처명 |
| title | 게시물 제목 |
| file_name | 첨부파일명 |
| file_url | 다운로드 URL |
| source_url | 수집 출처 URL |
| registered_date | 등록일 |
| department | 담당부서 |
| file_ext | 파일 확장자 |
| local_path | 로컬 저장 경로 |

---

## 프로젝트 구조

```
legal_scraper/
├── app.py                          # Streamlit 앱 진입점
├── config.py                       # 설정값
├── pages/
│   ├── 1_법률서식.py               # 법률서식 수집·분류 UI
│   └── 2_정부부처_계약서.py        # 정부부처 계약서 수집 UI
├── scrapers/
│   ├── klac_scraper.py             # 대한법률구조공단 (requests+BS4)
│   ├── ecfs_scraper.py             # 전자소송포털 (REST API)
│   ├── ekt_scraper.py              # 전자공탁 (REST API)
│   └── gov_contracts/
│       ├── base_scraper.py         # BaseGovScraper (requests 기반)
│       ├── base_playwright_scraper.py
│       ├── run_all.py              # CLI 실행기
│       ├── config.py
│       ├── scrapers/               # 부처별 스크래퍼 19개
│       └── utils/
│           ├── file_filter.py      # 키워드 필터 (CONTRACT_KEYWORDS)
│           ├── excel_writer.py
│           └── downloader.py
├── classifier/
│   └── classify.py                 # 분류체계 로드 + 자동 분류
├── utils/
│   ├── excel_writer.py
│   └── logger.py
├── data/
│   └── 분류체계.xlsx               # 사용자 직접 배치
├── output/                         # 법률서식 결과 (gitignore)
└── outputs/
    └── gov_contracts_metadata.xlsx # 정부부처 계약서 결과 (gitignore)
```

---

## 의존성

| 패키지 | 용도 |
|--------|------|
| `requests` | HTTP 요청 (requests 기반 스크래퍼) |
| `playwright` | JS 렌더링 필요 사이트 |
| `curl_cffi` | TLS 지문 차단 우회 (문화체육관광부, 경찰청) |
| `beautifulsoup4` / `lxml` | HTML 파싱 |
| `openpyxl` | Excel 저장 |
| `streamlit` | 웹 UI |

---

## Streamlit Cloud 배포

```bash
git push origin main
```

[https://share.streamlit.io](https://share.streamlit.io) 에서 Main file: `legal_scraper/app.py` 설정

> **주의**: Streamlit Cloud는 파일이 재시작마다 초기화됩니다.
> `분류체계.xlsx`는 사이드바 업로드 위젯을 사용하고,
> `snapshot.json`이 없으면 매 실행마다 전체 수집됩니다.
