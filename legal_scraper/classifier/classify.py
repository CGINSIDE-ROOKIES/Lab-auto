"""
분류체계.xlsx 기반 서식 자동 분류 모듈

classify_all(rows, taxonomy_path) → list[dict]  (CLASSIFIED_COLUMNS 형식)

분류체계.xlsx 구조 (시트: '분류체계(키워드포함)')
  컬럼: 대분류, 중분류, 소분류, 세분류, 분류출처, 키워드, 건수
  키워드: 파이프(|)로 구분된 서식 제목 목록

분류 순서:
  1. 정확일치: 정규화된 서식제목 == 정규화된 키워드
  2. 부분일치A: 키워드가 서식제목에 포함 (keyword in title)
  3. 부분일치B: 서식제목이 키워드에 포함 (title in keyword)
  4. 토큰일치: 형태소 토큰 교집합 비율 ≥ 임계값
  5. 검토필요: 매핑 없음

대분류 정규화 (수집 원본 → 분류체계 대분류):
  가사, 민사, 강제집행, 특허, 개인회생 계열, 형사, 독촉/신청 등
"""
import re
import unicodedata
from pathlib import Path

import pandas as pd

from config import TAXONOMY_FILE, TAXONOMY_SHEET

# ── 대분류 정규화 테이블 ──────────────────────────────────────────
_NORMALIZE = {
    "개인회생, 파산 및 면책": "개인회생·파산 및 면책",
    "개인파산/면책":           "개인회생·파산 및 면책",
    "개인회생":               "개인회생·파산 및 면책",
    "법인파산":               "개인회생·파산 및 면책",
    "법인회생":               "개인회생·파산 및 면책",
    "일반회생":               "개인회생·파산 및 면책",
    "가사":                   "가사소송",
    "민사":                   "민사소송",
    "강제집행":               "민사집행",
    "특허":                   "특허·지식재산",
    "독촉":                   "민사소송",
    "신청":                   "민사소송",
    "소년·가정·아동보호":     "형사소송",
    "형사":                   "형사소송",
}

# 토큰 일치 임계값 (교집합 / 더 짧은 쪽 길이 ≥ 이 값이면 부분일치)
_TOKEN_THRESHOLD = 0.6

# 최소 토큰 길이 (이보다 짧은 토큰은 무시)
_MIN_TOKEN_LEN = 2


def normalize_category(cat: str) -> str:
    return _NORMALIZE.get(cat.strip(), cat.strip())


# ── 텍스트 정규화 ─────────────────────────────────────────────────
def _normalize_text(text: str) -> str:
    """
    비교 전 텍스트 정규화:
    - NFC 유니코드 정규화
    - 전각→반각 변환
    - 괄호류 통일: 〔〕→[], 【】→[], ⌜⌝→[]
    - 특수 대시·점·가운뎃점 통일
    - 연속 공백 단일화, 앞뒤 공백 제거
    """
    if not text:
        return ""
    # 유니코드 NFC
    text = unicodedata.normalize("NFC", text)
    # 전각 숫자·알파벳→반각
    text = text.translate(_FULLWIDTH_TABLE)
    # 괄호 통일
    text = re.sub(r"[〔【⌜「『]", "[", text)
    text = re.sub(r"[〕】⌝」』]", "]", text)
    # 가운뎃점·대시 통일
    text = re.sub(r"[·•․‧⋅]", "·", text)
    text = re.sub(r"[－―—]", "-", text)
    # 공백 정규화
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _make_fullwidth_table():
    table = {}
    # 전각 알파벳 A-Z, a-z, 0-9
    for i in range(0xFF01, 0xFF5F):
        table[i] = i - 0xFEE0
    return str.maketrans(table)

_FULLWIDTH_TABLE = _make_fullwidth_table()


# ── 토큰화 ────────────────────────────────────────────────────────
def _tokenize(text: str) -> set[str]:
    """공백·괄호·특수문자로 분리한 뒤 최소 길이 이상 토큰만 반환."""
    tokens = re.split(r"[\s\[\]()\-·/,·~]+", text)
    return {t for t in tokens if len(t) >= _MIN_TOKEN_LEN}


# ── 분류체계 로드 ────────────────────────────────────────────────
def load_taxonomy(path: Path | None = None) -> dict:
    """
    Returns:
      {normalized_keyword: {"대분류": ..., "중분류": ..., "소분류": ..., "세분류": ..., "_raw": original_kw}}
    """
    path = path or TAXONOMY_FILE
    if not Path(path).exists():
        return {}

    try:
        df = pd.read_excel(path, sheet_name=TAXONOMY_SHEET, dtype=str)
    except Exception as e:
        import warnings
        warnings.warn(f"분류체계.xlsx 로드 실패 ({path}): {e}")
        return {}

    # 컬럼명이 "키워드"로 시작하는 컬럼을 동적으로 탐색
    kw_col = next((c for c in df.columns if str(c).startswith("키워드")), None)
    if kw_col is None:
        import warnings
        warnings.warn(f"분류체계.xlsx에 '키워드' 컬럼이 없습니다. 실제 컬럼: {list(df.columns)}")
        return {}

    taxonomy = {}

    for _, row in df.iterrows():
        keywords_raw = str(row.get(kw_col) or "").strip()
        if not keywords_raw or keywords_raw.lower() == "nan":
            continue
        info = {
            "대분류": str(row.get("대분류") or "").strip(),
            "중분류": str(row.get("중분류") or "").strip(),
            "소분류": str(row.get("소분류") or "").strip(),
            "세분류": str(row.get("세분류") or "").strip(),
        }
        for kw in keywords_raw.split("|"):
            kw = kw.strip()
            if kw:
                norm_kw = _normalize_text(kw)
                if norm_kw:
                    taxonomy[norm_kw] = {**info, "_raw": kw, "_tokens": _tokenize(norm_kw)}

    if not taxonomy:
        import warnings
        warnings.warn("분류체계.xlsx 로드는 됐으나 키워드가 0건입니다.")

    return taxonomy


# ── 단일 행 분류 ─────────────────────────────────────────────────
def _classify_one(title: str, taxonomy: dict) -> tuple[dict, str, str]:
    """
    Returns: (info_dict, 분류방법, 분류상태)

    매칭 우선순위:
      1. 정확일치 (정규화 후 동일)
      2. 부분일치A: 키워드 ⊆ 서식제목
      3. 부분일치B: 서식제목 ⊆ 키워드
      4. 토큰일치: 토큰 교집합 비율 ≥ _TOKEN_THRESHOLD
      5. 검토필요
    """
    if not title:
        return {"대분류": "", "중분류": "", "소분류": "", "세분류": ""}, "미분류", "검토필요"

    norm_title = _normalize_text(title)
    title_tokens = _tokenize(norm_title)

    # 1. 정확일치
    if norm_title in taxonomy:
        info = {k: v for k, v in taxonomy[norm_title].items() if not k.startswith("_")}
        return info, "정확일치", "분류완료"

    # 2. 부분일치A: 키워드가 서식제목에 포함 (keyword in title)
    best_partial_a = None
    best_partial_a_len = 0
    for norm_kw, info in taxonomy.items():
        if norm_kw and norm_kw in norm_title:
            if len(norm_kw) > best_partial_a_len:
                best_partial_a = info
                best_partial_a_len = len(norm_kw)

    if best_partial_a:
        result = {k: v for k, v in best_partial_a.items() if not k.startswith("_")}
        return result, "부분일치(키워드⊆제목)", "부분일치"

    # 3. 부분일치B: 서식제목이 키워드에 포함 (title in keyword) — 단, 제목이 2글자 이상
    if len(norm_title) >= 2:
        best_partial_b = None
        best_partial_b_len = 0
        for norm_kw, info in taxonomy.items():
            if norm_title in norm_kw:
                if len(norm_kw) > best_partial_b_len:
                    best_partial_b = info
                    best_partial_b_len = len(norm_kw)
        if best_partial_b:
            result = {k: v for k, v in best_partial_b.items() if not k.startswith("_")}
            return result, "부분일치(제목⊆키워드)", "부분일치"

    # 4. 토큰 일치
    if title_tokens:
        best_score = 0.0
        best_token_match = None
        for norm_kw, info in taxonomy.items():
            kw_tokens = info.get("_tokens", set())
            if not kw_tokens:
                continue
            intersection = title_tokens & kw_tokens
            if not intersection:
                continue
            # 교집합 / min(len(title_tokens), len(kw_tokens))
            score = len(intersection) / min(len(title_tokens), len(kw_tokens))
            if score >= _TOKEN_THRESHOLD and score > best_score:
                best_score = score
                best_token_match = info

        if best_token_match:
            result = {k: v for k, v in best_token_match.items() if not k.startswith("_")}
            return result, f"토큰일치({best_score:.0%})", "부분일치"

    # 5. 검토필요
    return {"대분류": "", "중분류": "", "소분류": "", "세분류": ""}, "미분류", "검토필요"


# ── 전체 분류 ────────────────────────────────────────────────────
def classify_all(rows: list[dict], taxonomy: dict) -> list[dict]:
    """
    수집 결과(rows)에 분류 컬럼을 추가하여 반환.
    taxonomy가 비어 있으면 모두 "검토필요".
    """
    results = []
    for r in rows:
        title = r.get("서식제목", "")
        info, method, status = _classify_one(title, taxonomy)
        results.append({
            "수집처":     r.get("수집처", ""),
            "원본대분류": r.get("대분류", ""),
            "원본중분류": r.get("중분류", ""),
            "서식제목":   title,
            "파일형식":   r.get("파일형식", ""),
            "최종대분류": info.get("대분류", ""),
            "최종중분류": info.get("중분류", ""),
            "소분류":     info.get("소분류", ""),
            "세분류":     info.get("세분류", ""),
            "다운로드URL": r.get("다운로드URL", ""),
            "수집일시":   r.get("수집일시", ""),
            "분류방법":   method,
            "분류상태":   status,
        })
    return results


# ── 통계 ─────────────────────────────────────────────────────────
def stats(classified_rows: list[dict]) -> dict:
    from collections import Counter
    cnt = Counter(r.get("분류상태", "") for r in classified_rows)
    return {
        "분류완료": cnt.get("분류완료", 0),
        "부분일치": cnt.get("부분일치", 0),
        "검토필요": cnt.get("검토필요", 0),
        "전체":    len(classified_rows),
    }
