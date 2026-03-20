"""
계약서 관련 파일/게시글 필터링
"""

CONTRACT_KEYWORDS = ["계약", "약정서"]

# 제목에 이 단어가 포함되면 수집 제외 (전체 공통)
EXCLUDE_TITLE_KEYWORDS = ["수의", "합격"]


def is_contract_file(file_name: str, post_title: str = "") -> bool:
    """
    파일명 우선 검사, 없으면 게시글 제목 검사.
    둘 다 없으면 False.
    """
    if file_name:
        return any(kw in file_name for kw in CONTRACT_KEYWORDS)
    if post_title:
        return any(kw in post_title for kw in CONTRACT_KEYWORDS)
    return False
