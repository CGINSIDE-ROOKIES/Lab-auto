"""
정부부처 표준계약서·약정서 수집 페이지
"""
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path

import streamlit as st
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.gov_contracts.run_all import scraper_map
from scrapers.gov_contracts.base_scraper import FormItem
from scrapers.gov_contracts.utils.excel_writer import to_bytes, COLUMNS

st.set_page_config(page_title="정부부처 계약서 수집", page_icon="🏛️", layout="wide")

TODAY_STR = date.today().strftime("%Y%m%d")

_SNAP_FILE  = Path(__file__).parent.parent / "data" / "gov_contracts_snapshot.json"
_OUTPUT_DIR = Path(__file__).parent.parent / "output"

# ── 부처 목록 ─────────────────────────────────────────────────────
_REQUESTS_MINISTRIES = [
    "공정거래위원회", "법무부", "성평등가족부", "과학기술정보통신부",
    "농림축산식품부", "국세청", "경찰청", "국토교통부",
    "식품의약품안전처", "감사원", "고용노동부", "문화체육관광부",
]
_PLAYWRIGHT_MINISTRIES = [
    "산업통상자원부", "보건복지부", "중소벤처기업부",
    "국가유산청", "지식재산처", "농촌진흥청", "행정안전부",
]
ALL_MINISTRIES = _REQUESTS_MINISTRIES + _PLAYWRIGHT_MINISTRIES
_PLAYWRIGHT_SET = set(_PLAYWRIGHT_MINISTRIES)

_INTER_DELAY  = 10   # 스크래퍼 간 기본 딜레이 (초)
_GROUP_DELAY  = 120  # requests→Playwright 전환 전 IP 안정화 딜레이 (초)

_GC_EXCEL_COLS = ["부처명", "서식제목", "첨부파일명", "파일확장자", "등록일", "다운로드URL"]

# ── Session State 초기화 ──────────────────────────────────────────
for _key, _val in {
    "gc_items":      [],
    "gc_new_items":  [],
    "gc_done":       False,
    "gc_incr_items": [],
    "gc_incr_done":  False,
    "gc_incr_no_new": False,
}.items():
    if _key not in st.session_state:
        st.session_state[_key] = _val

# 체크박스 기본값 초기화 (최초 1회만)
for _m in ALL_MINISTRIES:
    if f"cb_{_m}" not in st.session_state:
        st.session_state[f"cb_{_m}"] = True


# ── snapshot 헬퍼 ─────────────────────────────────────────────────
def _load_snap() -> dict:
    if _SNAP_FILE.exists():
        return json.loads(_SNAP_FILE.read_text(encoding="utf-8"))
    return {}

def _save_snap(snap: dict) -> None:
    _SNAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SNAP_FILE.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")

def _snap_key(item: FormItem) -> str:
    return item.file_url

def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── 스크래퍼 실행 헬퍼 ───────────────────────────────────────────
def _run_one(name: str, text_ph, bar_ph) -> list[FormItem]:
    cls = scraper_map.get(name)
    if cls is None:
        text_ph.markdown("⚠️ 스크래퍼 미구현")
        return []
    try:
        bar_ph.progress(0.1)
        text_ph.markdown("*초기화 중...*")
        scraper = cls()
        bar_ph.progress(0.3)
        text_ph.markdown("*수집 중...*")

        def _cb(count: int, _msg: str) -> None:
            text_ph.markdown(f"🔄 **{count:,}건** 수집 중...")

        scraper.on_progress = _cb
        items = scraper.run()
        bar_ph.progress(1.0)
        text_ph.markdown(f"✅ **{len(items):,}건** 수집 완료")
        return items
    except Exception as e:
        bar_ph.progress(0.0)
        text_ph.markdown(f"❌ 오류: {e}")
        return []


# ── 결과 표시 헬퍼 ────────────────────────────────────────────────
def _show_results(items: list[FormItem], label: str, file_prefix: str) -> None:
    if not items:
        st.success("✅ 신규 항목이 없습니다. 이미 최신 상태입니다.")
        return

    st.divider()

    # 부처별 집계
    ministry_counts: dict[str, int] = {}
    for item in items:
        ministry_counts[item.ministry] = ministry_counts.get(item.ministry, 0) + 1

    total_col, *_ = st.columns([1, 3])
    total_col.metric(label, f"{len(items):,}건")

    # 부처별 메트릭 (가로 배열)
    cols = st.columns(min(len(ministry_counts), 6))
    for idx, (ministry, cnt) in enumerate(sorted(ministry_counts.items(), key=lambda x: -x[1])):
        cols[idx % len(cols)].metric(ministry, f"{cnt:,}건")

    st.subheader(f"미리보기 (상위 20건 / 총 {len(items):,}건)")
    rows = [
        {
            "부처명": i.ministry,
            "서식제목": i.title,
            "첨부파일명": i.file_name,
            "파일확장자": i.file_ext,
            "등록일": i.registered_date,
            "다운로드URL": i.file_url,
        }
        for i in items[:20]
    ]
    preview_df = pd.DataFrame(rows)
    preview_df.insert(0, "일련번호", range(1, len(preview_df) + 1))
    st.dataframe(preview_df, use_container_width=True, hide_index=True)

    st.download_button(
        f"⬇️ {label} 엑셀 다운로드",
        data=to_bytes(items),
        file_name=f"{file_prefix}_{TODAY_STR}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


# ── 사이드바: 부처 선택 ───────────────────────────────────────────
with st.sidebar:
    st.title("🏛️ 정부부처 계약서")
    st.divider()

    # 수집 이력 통계
    snap = _load_snap()
    if snap:
        total_snap = sum(len(v) for v in snap.values())
        st.metric("마지막 수집 건수", f"{total_snap:,}건")
        all_dates = [dt for v in snap.values() for dt in v.values() if dt]
        if all_dates:
            st.caption(f"수집일: {max(all_dates)[:10]}")
    else:
        st.info("아직 수집 이력 없음")

    st.divider()
    st.subheader("수집 부처 선택")

    col_sel, col_clr = st.columns(2)
    if col_sel.button("전체 선택", use_container_width=True):
        for m in ALL_MINISTRIES:
            st.session_state[f"cb_{m}"] = True
        st.rerun()
    if col_clr.button("전체 해제", use_container_width=True):
        for m in ALL_MINISTRIES:
            st.session_state[f"cb_{m}"] = False
        st.rerun()

    st.caption("**requests 기반**")
    for m in _REQUESTS_MINISTRIES:
        st.checkbox(m, key=f"cb_{m}")

    st.caption("**Playwright 기반** _(브라우저 사용, 느림)_")
    for m in _PLAYWRIGHT_MINISTRIES:
        st.checkbox(m, key=f"cb_{m}")

    # 선택된 부처 수 표시
    selected_ministries = [m for m in ALL_MINISTRIES if st.session_state.get(f"cb_{m}")]
    st.divider()
    st.caption(f"선택: {len(selected_ministries)} / {len(ALL_MINISTRIES)}개 부처")


# ── 탭 ────────────────────────────────────────────────────────────
tab_full, tab_incr, tab_merge = st.tabs(["📥 전체 수집", "➕ 추가 수집", "📂 데이터 병합"])


# ═══════════════════════════════════════════════════════════════
# 탭1: 전체 수집
# ═══════════════════════════════════════════════════════════════
with tab_full:
    st.header("전체 수집")
    st.caption("선택한 부처를 전체 수집합니다. snapshot 대비 신규 항목을 표시합니다.")

    if not selected_ministries:
        st.warning("사이드바에서 수집할 부처를 선택하세요.")
    else:
        run_btn = st.button(
            f"▶ 전체 수집 시작 ({len(selected_ministries)}개 부처)",
            type="primary",
            use_container_width=True,
            key="btn_full",
        )

        if run_btn:
            st.session_state.gc_done      = False
            st.session_state.gc_items     = []
            st.session_state.gc_new_items = []

            st.subheader("진행 현황")
            ministry_uis: dict[str, tuple] = {}
            for m in selected_ministries:
                c = st.container(border=True)
                with c:
                    st.caption(f"🏛️ {m}")
                    t = st.empty()
                    b = st.progress(0.0)
                    t.markdown("*대기 중...*")
                ministry_uis[m] = (t, b)

            all_items: list[FormItem] = []
            pw_pause_done = False
            for idx, m in enumerate(selected_ministries):
                t, b = ministry_uis[m]
                t.markdown("*수집 중...*")
                items = _run_one(m, t, b)
                all_items.extend(items)
                if idx < len(selected_ministries) - 1:
                    next_m = selected_ministries[idx + 1]
                    next_t, _ = ministry_uis[next_m]
                    if next_m in _PLAYWRIGHT_SET and not pw_pause_done:
                        pw_pause_done = True
                        next_t.markdown(f"⏳ *IP 안정화 대기 중... ({_GROUP_DELAY}초)*")
                        time.sleep(_GROUP_DELAY)
                    else:
                        next_t.markdown("⏳ *잠시 후 시작...*")
                        time.sleep(_INTER_DELAY)

            # snapshot 비교 → 신규 항목 추출
            snap = _load_snap()
            if not snap:
                new_items = all_items
            else:
                new_items = [
                    item for item in all_items
                    if _snap_key(item) not in snap.get(item.ministry, {})
                ]

            # snapshot 갱신 (수집된 전체 항목 반영)
            now = _now_str()
            for item in all_items:
                snap.setdefault(item.ministry, {})[_snap_key(item)] = now
            _save_snap(snap)

            # 로컬 Excel 저장
            _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            from scrapers.gov_contracts.utils.excel_writer import save_to_excel
            save_to_excel(new_items or all_items, _OUTPUT_DIR / f"gov_contracts_{TODAY_STR}.xlsx")

            st.session_state.gc_items     = all_items
            st.session_state.gc_new_items = new_items
            st.session_state.gc_done      = True

        if st.session_state.gc_done:
            all_items_res  = st.session_state.gc_items
            new_items_res  = st.session_state.gc_new_items

            st.divider()

            # ── 전체 수집 요약 ──────────────────────────────────
            col_total, col_new = st.columns(2)
            col_total.metric("전체 수집", f"{len(all_items_res):,}건")
            col_new.metric("신규 항목", f"{len(new_items_res):,}건")

            # 부처별 전체 수집건수
            if all_items_res:
                m_counts: dict[str, int] = {}
                for item in all_items_res:
                    m_counts[item.ministry] = m_counts.get(item.ministry, 0) + 1
                st.caption("부처별 수집 결과")
                cols = st.columns(min(len(m_counts), 6))
                for idx, (ministry, cnt) in enumerate(
                    sorted(m_counts.items(), key=lambda x: -x[1])
                ):
                    cols[idx % len(cols)].metric(ministry, f"{cnt:,}건")

            # ── 신규 항목 ───────────────────────────────────────
            st.divider()
            _show_results(new_items_res, label="신규 항목", file_prefix="gov_contracts_NEW")


# ═══════════════════════════════════════════════════════════════
# 탭2: 추가 수집
# ═══════════════════════════════════════════════════════════════
with tab_incr:
    st.header("추가 수집")
    st.caption("기존 snapshot 기준으로 신규 항목만 수집합니다. snapshot이 있어야 합니다.")

    snap_exists = _SNAP_FILE.exists()

    if not snap_exists:
        st.info("📋 수집 이력이 없습니다. **전체 수집** 탭에서 먼저 수집하세요.")
    elif not selected_ministries:
        st.warning("사이드바에서 수집할 부처를 선택하세요.")
    else:
        incr_btn = st.button(
            f"▶ 추가 수집 시작 ({len(selected_ministries)}개 부처)",
            type="secondary",
            use_container_width=True,
            key="btn_incr",
        )

        if incr_btn:
            st.session_state.gc_incr_done   = False
            st.session_state.gc_incr_no_new = False
            st.session_state.gc_incr_items  = []

            existing_snap = _load_snap()

            st.subheader("진행 현황")
            ministry_uis2: dict[str, tuple] = {}
            for m in selected_ministries:
                c = st.container(border=True)
                with c:
                    st.caption(f"🏛️ {m}")
                    t = st.empty()
                    b = st.progress(0.0)
                    t.markdown("*대기 중...*")
                ministry_uis2[m] = (t, b)

            all_items2: list[FormItem] = []
            pw_pause_done2 = False
            for idx, m in enumerate(selected_ministries):
                t, b = ministry_uis2[m]
                t.markdown("*수집 중...*")
                items = _run_one(m, t, b)
                all_items2.extend(items)
                if idx < len(selected_ministries) - 1:
                    next_m = selected_ministries[idx + 1]
                    next_t, _ = ministry_uis2[next_m]
                    if next_m in _PLAYWRIGHT_SET and not pw_pause_done2:
                        pw_pause_done2 = True
                        next_t.markdown(f"⏳ *IP 안정화 대기 중... ({_GROUP_DELAY}초)*")
                        time.sleep(_GROUP_DELAY)
                    else:
                        next_t.markdown("⏳ *잠시 후 시작...*")
                        time.sleep(_INTER_DELAY)

            # 신규 항목만 필터
            known = existing_snap
            incr_items = [
                item for item in all_items2
                if _snap_key(item) not in known.get(item.ministry, {})
            ]

            if incr_items:
                # snapshot 업데이트
                now = _now_str()
                for item in incr_items:
                    existing_snap.setdefault(item.ministry, {})[_snap_key(item)] = now
                _save_snap(existing_snap)

                # 로컬 Excel 저장
                _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                from scrapers.gov_contracts.utils.excel_writer import save_to_excel
                save_to_excel(incr_items, _OUTPUT_DIR / f"gov_contracts_INCR_{TODAY_STR}.xlsx")

                st.session_state.gc_incr_items = incr_items
                st.session_state.gc_incr_done  = True
            else:
                st.session_state.gc_incr_no_new = True
                st.session_state.gc_incr_done   = True

        if st.session_state.gc_incr_done:
            if st.session_state.gc_incr_no_new:
                st.divider()
                st.info("📭 신규 항목이 없습니다. 이미 최신 상태입니다.")
            else:
                _show_results(
                    st.session_state.gc_incr_items,
                    label="신규 추가 항목",
                    file_prefix="gov_contracts_INCR",
                )


# ═══════════════════════════════════════════════════════════════
# 탭3: 데이터 병합
# ═══════════════════════════════════════════════════════════════
with tab_merge:
    st.header("📂 데이터 병합")
    st.caption("두 Excel 파일을 병합합니다. 다운로드URL 기준으로 중복을 제거합니다.")

    merge_base_file = st.file_uploader("기존 파일 업로드", type=["xlsx"], key="gc_merge_base")
    merge_incr_file = st.file_uploader("증분 파일 업로드", type=["xlsx"], key="gc_merge_incr")

    merge_btn = st.button(
        "병합 실행",
        type="primary",
        disabled=(merge_base_file is None or merge_incr_file is None),
        use_container_width=True,
        key="btn_merge",
    )

    if merge_btn and merge_base_file and merge_incr_file:
        try:
            base_df = pd.read_excel(merge_base_file)
            incr_df = pd.read_excel(merge_incr_file)

            # 컬럼 검증 (일련번호 제외한 실질 컬럼)
            expected = [c for c in COLUMNS if c != "일련번호"]
            base_data_cols = [c for c in base_df.columns if c != "일련번호"]
            incr_data_cols = [c for c in incr_df.columns if c != "일련번호"]

            missing_base = [c for c in expected if c not in base_data_cols]
            missing_incr = [c for c in expected if c not in incr_data_cols]

            if missing_base or missing_incr:
                err_lines = ["❌ 컬럼 불일치로 병합을 중단합니다."]
                if missing_base:
                    err_lines.append(f"• 기존 파일 누락 컬럼: {missing_base}")
                if missing_incr:
                    err_lines.append(f"• 증분 파일 누락 컬럼: {missing_incr}")
                st.error("\n".join(err_lines))
            else:
                # 병합 (다운로드URL 기준 dedup, 기존 파일 우선)
                combined = pd.concat([base_df, incr_df], ignore_index=True)
                before = len(combined)
                merged_df = combined.drop_duplicates(subset=["다운로드URL"], keep="first")
                merged_df = merged_df.reset_index(drop=True)
                merged_df["일련번호"] = range(1, len(merged_df) + 1)

                n_dup = before - len(merged_df)
                if n_dup > 0:
                    st.warning(f"⚠️ 중복 {n_dup:,}건 제거됨")

                # 파일명 결정
                import re as _re
                base_stem   = Path(merge_base_file.name).stem
                base_suffix = Path(merge_base_file.name).suffix
                date_pat    = _re.compile(r"\d{8}")
                new_stem    = date_pat.sub(TODAY_STR, base_stem) if date_pat.search(base_stem) else base_stem + f"_{TODAY_STR}"
                merged_filename = new_stem + base_suffix

                # 로컬 저장
                _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                merged_path = _OUTPUT_DIR / merged_filename
                merged_df.to_excel(merged_path, index=False)

                st.success(
                    f"✅ 병합 완료 — "
                    f"기존 {len(base_df):,}건 / 증분 {len(incr_df):,}건 → 합계 {len(merged_df):,}건"
                )

                # 다운로드용 bytes
                import io, openpyxl as _xl
                buf = io.BytesIO()
                merged_df.to_excel(buf, index=False)
                buf.seek(0)

                st.download_button(
                    "⬇️ 병합 파일 다운로드",
                    data=buf.getvalue(),
                    file_name=merged_filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
        except Exception as e:
            st.error(f"❌ 오류: {e}")
