# Legal Scraper — 법률서식 수집·분류 웹앱

법률 서식 3개 사이트에서 전체 수집 후 분류체계에 따라 자동 분류하는 Streamlit 앱.

---

## 1. 프로젝트 개요

| 수집처 | URL | 서식 수 |
|--------|-----|---------|
| 대한법률구조공단 | https://www.klac.or.kr/legalinfo/legalFrm.do | ~2,147개 |
| 전자소송포털 | https://ecfs.scourt.go.kr/psp/index.on?m=PSP720M24 | ~983개 |
| 전자공탁 | https://ekt.scourt.go.kr/pjg/index.on?m=PJG172M03 | ~59개 |

---

## 2. 설치 방법

```bash
pip install -r requirements.txt
```

---

## 3. data/분류체계.xlsx 준비

- `data/` 폴더에 `분류체계.xlsx` 파일을 직접 넣거나 앱 사이드바에서 업로드
- 파일 내 **2번 시트** 이름: `분류체계(키워드포함)`
- 필수 컬럼: `대분류`, `중분류`, `소분류`, `세분류`, `키워드`
- `키워드` 형식: 실제 서식 제목을 파이프(`|`)로 구분

```
이행명령신청서 | 감치명령신청서 | 과태료부과신청
```

---

## 4. 로컬 실행

```bash
streamlit run app.py
```

브라우저가 자동으로 열리며 `http://localhost:8501` 접속

### 사용 흐름

1. **사이드바**: 분류체계.xlsx 업로드 (또는 data/ 폴더에 직접 배치)
2. **스크래핑 탭**: "전체 스크래핑 시작" 버튼 클릭
   - 사이트별 진행 바로 실시간 진행 확인
   - 완료 후 신규 항목 미리보기 + 엑셀 다운로드
3. **분류 탭**: 스크래핑 완료 후 자동 분류 실행
   - 색상 구분 테이블 (초록=분류완료 / 노랑=부분일치 / 빨강=검토필요)
   - 분류 결과 엑셀 다운로드 (전체 + 검토필요 시트)

> **샘플 모드**: 사이드바의 "샘플 모드" 체크박스로 사이트당 1페이지(~10건)만 빠르게 테스트

---

## 5. 결과 파일 위치

| 파일 | 설명 |
|------|------|
| `output/legal_forms_YYYYMMDD.xlsx` | 수집 결과 (신규 항목) |
| `output/legal_forms_classified_YYYYMMDD.xlsx` | 분류 결과 |
| `data/snapshot.json` | 수집 이력 (증분 수집용) |
| `logs/scraper.log` | 상세 로그 |

---

## 6. Streamlit Cloud 배포

```bash
# 1. GitHub 저장소에 push
git init && git add . && git commit -m "initial"
git remote add origin https://github.com/yourname/legal-scraper.git
git push -u origin main

# 2. https://share.streamlit.io 에서
#    - Main file: app.py
#    - Python version: 3.11+
```

> **주의**: Streamlit Cloud는 파일이 재시작마다 초기화됩니다.
> 분류체계.xlsx는 사이드바 업로드 위젯을 사용하세요.
> snapshot.json이 없으면 매 실행마다 전체 수집됩니다.

---

## 7. 문제 발생 시 로그 확인

```bash
# 로컬
cat logs/scraper.log

# 또는 Streamlit UI에서 직접 확인
# (터미널에도 INFO 레벨 로그 출력)
```

---

## 폴더 구조

```
legal_scraper/
├── app.py               # Streamlit UI (버튼·화면만 담당)
├── config.py            # URL, 경로, 딜레이 등 설정값
├── requirements.txt
├── scrapers/
│   ├── klac_scraper.py  # 대한법률구조공단 (requests+BS4)
│   ├── ecfs_scraper.py  # 전자소송포털 (REST API)
│   └── ekt_scraper.py   # 전자공탁 (REST API)
├── classifier/
│   └── classify.py      # 분류체계 로드 + 자동 분류
├── utils/
│   ├── excel_writer.py  # 수집/분류 결과 엑셀 생성
│   └── logger.py        # 로그 설정
├── data/
│   └── 분류체계.xlsx    # 사용자 직접 배치
├── output/              # 결과 엑셀 (gitignore)
└── logs/                # 로그 (gitignore)
```
