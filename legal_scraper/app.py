"""
법률서식 수집 시스템 — 홈
왼쪽 사이드바에서 수집 페이지를 선택하세요.
"""
import streamlit as st

st.set_page_config(page_title="법률서식 수집 시스템", page_icon="⚖️", layout="wide")

st.title("⚖️ 법률서식 수집 시스템")
st.divider()

col1, col2 = st.columns(2, gap="large")

with col1:
    st.subheader("⚖️ 법률서식")
    st.markdown(
        """
        대한법률구조공단·전자소송포털·전자공탁에서
        법률 서식을 수집하고 분류합니다.

        - 전체 스크래핑 / 추가 스크래핑
        - snapshot 기반 신규 항목 감지
        - 자동 분류 (분류체계.xlsx 필요)
        - Excel 다운로드 및 파일 병합
        """
    )

with col2:
    st.subheader("🏛️ 정부부처 계약서")
    st.markdown(
        """
        19개 정부부처 공식 홈페이지에서
        표준계약서·약정서 파일을 수집합니다.

        - 부처 선택 후 수집 (requests / Playwright)
        - 전체 수집 / 추가 수집
        - snapshot 기반 신규 항목 감지
        - Excel 다운로드 및 파일 병합
        """
    )

st.divider()
st.caption("왼쪽 사이드바에서 수집할 항목을 선택하세요.")
