"""
계약서 관련 파일/게시글 필터링
"""

CONTRACT_KEYWORDS = ["계약서"]


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
