"""
법률서식 수집·분류 Streamlit 웹앱

실행: streamlit run app.py
"""
import base64
import json
import sys
from datetime import date
from pathlib import Path

import requests as _req
import streamlit as st
import pandas as pd

# ── 경로 설정 ─────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    SNAPSHOT_FILE, TAXONOMY_FILE, OUTPUT_DIR, DATA_DIR,
    RAW_COLUMNS, CLASSIFIED_COLUMNS,
)
from scrapers import klac_scraper, ecfs_scraper, ekt_scraper
from classifier.classify import load_taxonomy, classify_all, stats
from utils.excel_writer import (
    to_bytes_raw, to_bytes_classified, write_raw, write_classified,
    merge_files, merged_df_to_bytes, write_merged, EXPECTED_COLUMNS,
)
from utils.logger import setup_logger

logger = setup_logger()
st.set_page_config(page_title="법률서식 수집·분류", page_icon="⚖️", layout="wide")

TODAY_STR = date.today().strftime("%Y%m%d")

# ── Session State 초기화 ──────────────────────────────────────────
for key, default in {
    "all_rows":          [],
    "new_rows":          [],
    "classified_rows":   [],
    "scraping_done":     False,
    "classify_done":     False,
    "incr_rows":         [],
    "incr_done":         False,
    "incr_no_new":       False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── snapshot 헬퍼 ─────────────────────────────────────────────────
def _site_key(r):
    return f"{r.get('서식제목','')}|||{r.get('파일형식','')}"

def _migrate_snapshot(old_snap):
    """구버전 flat snapshot → 사이트별 nested 구조로 자동 변환"""
    new_snap = {"klac": {}, "ecfs": {}, "ekt": {}}
    for old_key, dt in old_snap.items():
        parts = old_key.split("|||")
        if len(parts) != 3:
            continue
        title, fmt, source = parts
        new_key = f"{title}|||{fmt}"
        if source == "대한법률구조공단":
            new_snap["klac"][new_key] = dt
        else:
            new_snap["ecfs"][new_key] = dt
            new_snap["ekt"][new_key] = dt
    return new_snap

# ── GitHub snapshot 저장소 ────────────────────────────────────────
def _gh_config():
    try:
        token = st.secrets.get("GITHUB_TOKEN", "")
        repo  = st.secrets.get("GITHUB_REPO", "")
        branch = st.secrets.get("GITHUB_BRANCH", "main")
    except Exception:
        return None, None, None
    if not token or not repo:
        return None, None, None
    return token, repo, branch

_GH_SNAP_PATH = "legal_scraper/data/snapshot.json"

def _gh_load():
    token, repo, branch = _gh_config()
    if not token:
        return None, None
    url = f"https://api.github.com/repos/{repo}/contents/{_GH_SNAP_PATH}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    try:
        r = _req.get(url, headers=headers, params={"ref": branch}, timeout=10)
        if r.status_code == 404:
            return None, None
        r.raise_for_status()
        data = r.json()
        content = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
        return content, data["sha"]
    except Exception as e:
        st.warning(f"GitHub snapshot 읽기 실패: {e}")
        return None, None

def _gh_save(snap_dict, sha):
    token, repo, branch = _gh_config()
    if not token:
        return
    url = f"https://api.github.com/repos/{repo}/contents/{_GH_SNAP_PATH}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    payload = {
        "message": "auto: snapshot 업데이트",
        "content": base64.b64encode(
            json.dumps(snap_dict, ensure_ascii=False, indent=2).encode("utf-8")
        ).decode("utf-8"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    try:
        r = _req.put(url, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        st.session_state["_snap_sha"] = r.json()["content"]["sha"]
    except Exception as e:
        st.warning(f"GitHub snapshot 저장 실패: {e}")

def load_snapshot():
    # GitHub 우선, 없으면 로컬 파일
    content, sha = _gh_load()
    if content is not None:
        st.session_state["_snap_sha"] = sha
        if content and not isinstance(next(iter(content.values())), dict):
            content = _migrate_snapshot(content)
        return content
    # 로컬 fallback
    if not SNAPSHOT_FILE.exists():
        return None
    data = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    if data and not isinstance(next(iter(data.values())), dict):
        data = _migrate_snapshot(data)
    return data

def _build_snap_dict(rows):
    new_snap = {"klac": {}, "ecfs": {}, "ekt": {}}
    for r in rows:
        key = _site_key(r)
        dt  = r.get("수집일시", "")
        if r.get("수집처") == "대한법률구조공단":
            new_snap["klac"][key] = dt
        elif r.get("대분류") == "공탁":
            new_snap["ekt"][key] = dt
        else:
            new_snap["ecfs"][key] = dt
    return new_snap

def _persist_snap(snap_dict):
    """GitHub에 저장, 로컬에도 백업"""
    _gh_save(snap_dict, st.session_state.get("_snap_sha"))
    try:
        SNAPSHOT_FILE.write_text(json.dumps(snap_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def save_snapshot(rows):
    _persist_snap(_build_snap_dict(rows))


# ── 사이드바 ──────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚖️ 법률서식")
    st.divider()

    # 수집 통계
    snap = load_snapshot()
    if snap:
        total_snap = sum(len(v) for v in snap.values())
        st.metric("마지막 수집 건수", f"{total_snap:,}건")
        all_dates = [dt for v in snap.values() for dt in v.values()]
        if all_dates:
            st.caption(f"수집일: {max(all_dates)}")
    else:
        st.info("아직 수집 이력 없음")

    st.divider()

    # 샘플 모드
    sample_mode = st.checkbox("샘플 모드 (사이트당 1페이지)", value=False)

    st.divider()

    # 분류체계.xlsx 업로드
    st.subheader("분류체계 파일")
    if TAXONOMY_FILE.exists():
        st.success(f"✅ {TAXONOMY_FILE.name} 로드됨")
    else:
        st.warning("data/분류체계.xlsx 없음")

    uploaded = st.file_uploader("분류체계.xlsx 업로드", type=["xlsx"], label_visibility="collapsed")
    if uploaded:
        DATA_DIR.mkdir(exist_ok=True)
        TAXONOMY_FILE.write_bytes(uploaded.read())
        st.success("업로드 완료")
        st.rerun()


# ── 탭 ────────────────────────────────────────────────────────────
tab_scrape, tab_classify = st.tabs(["📥 스크래핑", "🗂️ 분류"])


# ═══════════════════════════════════════════════════════════════
# 탭1: 스크래핑
# ═══════════════════════════════════════════════════════════════
with tab_scrape:
    st.header("전체 스크래핑")
    run_btn = st.button("▶ 전체 스크래핑 시작", type="primary", use_container_width=True)

    if run_btn:
        st.session_state.scraping_done   = False
        st.session_state.classify_done   = False
        st.session_state.all_rows        = []
        st.session_state.new_rows        = []
        st.session_state.classified_rows = []

        # ── 진행 표시 컨테이너 ──────────────────────────────────
        st.subheader("진행 현황")

        # 사이트1
        c1 = st.container(border=True)
        with c1:
            st.caption("🏛️ 대한법률구조공단")
            k_text = st.empty()
            k_bar  = st.progress(0.0)

        # 사이트2
        c2 = st.container(border=True)
        with c2:
            st.caption("⚖️ 전자소송포털 양식모음")
            e_text = st.empty()
            e_bar  = st.progress(0.0)

        # 사이트3
        c3 = st.container(border=True)
        with c3:
            st.caption("💰 전자공탁 공탁양식")
            t_text = st.empty()
            t_bar  = st.progress(0.0)

        # ── 스크래퍼 실행 ────────────────────────────────────────
        def make_cb(text_ph, bar_ph):
            def cb(cur, total, msg):
                text_ph.markdown(f"**{msg}**")
                bar_ph.progress(min(cur / max(total, 1), 1.0))
            return cb

        k_text.markdown("*수집 중...*")
        klac_rows = klac_scraper.scrape(
            sample_mode=sample_mode,
            on_progress=make_cb(k_text, k_bar),
        )
        k_text.markdown(f"✅ **{len(klac_rows):,}건** 수집 완료")
        k_bar.progress(1.0)

        e_text.markdown("*수집 중...*")
        ecfs_rows = ecfs_scraper.scrape(
            sample_mode=sample_mode,
            on_progress=make_cb(e_text, e_bar),
        )
        e_text.markdown(f"✅ **{len(ecfs_rows):,}건** 수집 완료")
        e_bar.progress(1.0)

        t_text.markdown("*수집 중...*")
        ekt_rows = ekt_scraper.scrape(
            sample_mode=sample_mode,
            on_progress=make_cb(t_text, t_bar),
        )
        t_text.markdown(f"✅ **{len(ekt_rows):,}건** 수집 완료")
        t_bar.progress(1.0)

        all_rows = klac_rows + ecfs_rows + ekt_rows

        # ── snapshot 비교 ────────────────────────────────────────
        snap = load_snapshot()
        if snap is None:
            new_rows = all_rows
        else:
            klac_keys = snap.get("klac", {})
            ecfs_keys = snap.get("ecfs", {})
            ekt_keys  = snap.get("ekt",  {})
            new_rows = [
                r for r in all_rows
                if _site_key(r) not in (
                    klac_keys if r.get("수집처") == "대한법률구조공단"
                    else ekt_keys if r.get("대분류") == "공탁"
                    else ecfs_keys
                )
            ]

        save_snapshot(all_rows)

        st.session_state.all_rows      = all_rows
        st.session_state.new_rows      = new_rows
        st.session_state.scraping_done = True

        # 로컬 파일 저장
        out_path = OUTPUT_DIR / f"legal_forms_{TODAY_STR}.xlsx"
        write_raw(new_rows if new_rows else all_rows, out_path)
        logger.info(f"저장: {out_path}")

    # ── 결과 표시 ─────────────────────────────────────────────────
    if st.session_state.scraping_done:
        all_rows = st.session_state.all_rows
        new_rows = st.session_state.new_rows

        st.divider()
        col1, col2, col3 = st.columns(3)
        col1.metric("전체 수집", f"{len(all_rows):,}건")
        col2.metric("신규", f"{len(new_rows):,}건")
        col3.metric("KLAC / ECFS / EKT",
                    f"{sum(1 for r in all_rows if r['수집처']=='대한법률구조공단'):,} / "
                    f"{sum(1 for r in all_rows if r['수집처']=='전자소송포털' and r['대분류']!='공탁'):,} / "
                    f"{sum(1 for r in all_rows if r['대분류']=='공탁'):,}")

        if new_rows:
            st.subheader(f"신규 항목 미리보기 (상위 20건 / 총 {len(new_rows):,}건)")
            preview = pd.DataFrame(new_rows[:20])
            preview.insert(0, "일련번호", range(1, len(preview) + 1))
            st.dataframe(preview, use_container_width=True, hide_index=True)

            st.download_button(
                "⬇️ 신규 서식 엑셀 다운로드",
                data=to_bytes_raw(new_rows),
                file_name=f"legal_forms_NEW_{TODAY_STR}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        else:
            st.success("✅ 변동 없음 — 신규 서식이 없습니다.")
            logger.info("변동 없음")

    # ═══════════════════════════════════════════════════════════════
    # 추가 스크래핑 섹션
    # ═══════════════════════════════════════════════════════════════
    st.divider()
    st.header("추가 스크래핑")
    st.caption("이미 수집된 snapshot.json 기준으로 신규 항목만 추가 수집합니다.")

    snap_exists = SNAPSHOT_FILE.exists()

    if not snap_exists:
        st.info("📋 수집 이력(snapshot.json)이 없습니다. 위의 **전체 스크래핑**을 먼저 실행하세요.")
    else:
        incr_btn = st.button("▶ 추가 스크래핑 시작", type="secondary", use_container_width=True)

        if incr_btn:
            st.session_state.incr_rows   = []
            st.session_state.incr_done   = False
            st.session_state.incr_no_new = False

            # 기존 snapshot 로드
            existing_snap = load_snapshot()

            st.subheader("진행 현황")

            c1 = st.container(border=True)
            with c1:
                st.caption("🏛️ 대한법률구조공단")
                k_text2 = st.empty()
                k_bar2  = st.progress(0.0)

            c2 = st.container(border=True)
            with c2:
                st.caption("⚖️ 전자소송포털 양식모음")
                e_text2 = st.empty()
                e_bar2  = st.progress(0.0)

            c3 = st.container(border=True)
            with c3:
                st.caption("💰 전자공탁 공탁양식")
                t_text2 = st.empty()
                t_bar2  = st.progress(0.0)

            def make_cb2(text_ph, bar_ph):
                def cb(cur, total, msg):
                    text_ph.markdown(f"**{msg}**")
                    bar_ph.progress(min(cur / max(total, 1), 1.0))
                return cb

            klac_known = set(existing_snap.get("klac", {}).keys())
            ecfs_known = set(existing_snap.get("ecfs", {}).keys())
            ekt_known  = set(existing_snap.get("ekt",  {}).keys())

            k_text2.markdown("*수집 중...*")
            klac_rows2 = klac_scraper.scrape(
                known_keys=klac_known,
                on_progress=make_cb2(k_text2, k_bar2),
            )
            k_text2.markdown(f"✅ **{len(klac_rows2):,}건** 신규 수집")
            k_bar2.progress(1.0)

            e_text2.markdown("*수집 중...*")
            ecfs_rows2 = ecfs_scraper.scrape(
                known_keys=ecfs_known,
                on_progress=make_cb2(e_text2, e_bar2),
            )
            e_text2.markdown(f"✅ **{len(ecfs_rows2):,}건** 신규 수집")
            e_bar2.progress(1.0)

            t_text2.markdown("*수집 중...*")
            ekt_rows2 = ekt_scraper.scrape(
                known_keys=ekt_known,
                on_progress=make_cb2(t_text2, t_bar2),
            )
            t_text2.markdown(f"✅ **{len(ekt_rows2):,}건** 신규 수집")
            t_bar2.progress(1.0)

            incr_rows = klac_rows2 + ecfs_rows2 + ekt_rows2

            if incr_rows:
                # 사이트별 snapshot에 신규 항목 병합 후 저장
                for r in incr_rows:
                    key = _site_key(r)
                    dt  = r.get("수집일시", "")
                    if r.get("수집처") == "대한법률구조공단":
                        existing_snap["klac"][key] = dt
                    elif r.get("대분류") == "공탁":
                        existing_snap["ekt"][key] = dt
                    else:
                        existing_snap["ecfs"][key] = dt
                _persist_snap(existing_snap)
                # 로컬 파일 저장
                out_path2 = OUTPUT_DIR / f"legal_forms_INCR_{TODAY_STR}.xlsx"
                write_raw(incr_rows, out_path2)
                logger.info(f"추가 스크래핑 저장: {out_path2} ({len(incr_rows)}건)")

                st.session_state.incr_rows = incr_rows
                st.session_state.incr_done = True
            else:
                st.session_state.incr_no_new = True
                st.session_state.incr_done   = True
                logger.info("추가 스크래핑: 신규 항목 없음")

        # ── 추가 스크래핑 결과 표시 ───────────────────────────────
        if st.session_state.incr_done:
            st.divider()
            if st.session_state.incr_no_new:
                st.info("📭 추가 스크래핑할 신규 항목이 없습니다. 이미 최신 상태입니다.")
            else:
                incr_rows = st.session_state.incr_rows
                col1, col2 = st.columns(2)
                col1.metric("신규 추가 항목", f"{len(incr_rows):,}건")
                col2.metric("KLAC / ECFS / EKT",
                            f"{sum(1 for r in incr_rows if r['수집처']=='대한법률구조공단'):,} / "
                            f"{sum(1 for r in incr_rows if r['수집처']=='전자소송포털' and r['대분류']!='공탁'):,} / "
                            f"{sum(1 for r in incr_rows if r['대분류']=='공탁'):,}")

                st.subheader(f"신규 항목 미리보기 (상위 20건 / 총 {len(incr_rows):,}건)")
                preview2 = pd.DataFrame(incr_rows[:20])
                preview2.insert(0, "일련번호", range(1, len(preview2) + 1))
                st.dataframe(preview2, use_container_width=True, hide_index=True)

                st.download_button(
                    "⬇️ 추가 수집 서식 엑셀 다운로드",
                    data=to_bytes_raw(incr_rows),
                    file_name=f"legal_forms_INCR_{TODAY_STR}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )


    # ═══════════════════════════════════════════════════════════════
    # 데이터 병합 섹션
    # ═══════════════════════════════════════════════════════════════
    st.divider()
    st.header("📂 데이터 병합")

    merge_base_file = st.file_uploader("기존 파일 업로드", type=["xlsx"], key="merge_base")
    merge_incr_file = st.file_uploader("증분 파일 업로드", type=["xlsx"], key="merge_incr")

    merge_btn = st.button(
        "병합 실행",
        type="primary",
        disabled=(merge_base_file is None or merge_incr_file is None),
        use_container_width=True,
    )

    if merge_btn and merge_base_file and merge_incr_file:
        try:
            base_df = pd.read_excel(merge_base_file)
            incr_df = pd.read_excel(merge_incr_file)

            # 컬럼 검증
            base_cols = list(base_df.columns)
            incr_cols = list(incr_df.columns)
            if base_cols != EXPECTED_COLUMNS or incr_cols != EXPECTED_COLUMNS:
                missing_base = [c for c in EXPECTED_COLUMNS if c not in base_cols]
                extra_base   = [c for c in base_cols if c not in EXPECTED_COLUMNS]
                missing_incr = [c for c in EXPECTED_COLUMNS if c not in incr_cols]
                extra_incr   = [c for c in incr_cols if c not in EXPECTED_COLUMNS]
                err_lines = ["❌ 컬럼 불일치로 병합을 중단합니다."]
                if missing_base:
                    err_lines.append(f"• 기존 파일 누락 컬럼: {missing_base}")
                if extra_base:
                    err_lines.append(f"• 기존 파일 불필요 컬럼: {extra_base}")
                if missing_incr:
                    err_lines.append(f"• 증분 파일 누락 컬럼: {missing_incr}")
                if extra_incr:
                    err_lines.append(f"• 증분 파일 불필요 컬럼: {extra_incr}")
                st.error("\n".join(err_lines))
            else:
                merged_df, duplicates_df = merge_files(base_df, incr_df)

                # 중복 경고
                if not duplicates_df.empty:
                    st.warning(
                        f"⚠️ 중복 데이터 {len(duplicates_df):,}건 발견 (병합은 완료됨)"
                    )
                    with st.expander("중복 항목 펼쳐보기 ▼"):
                        st.dataframe(
                            duplicates_df[["서식제목", "파일형식", "수집처"]],
                            use_container_width=True,
                            hide_index=True,
                        )

                # 저장 경로 결정: 기존 파일의 8자리 날짜를 오늘 날짜로 교체
                import re as _re
                base_stem = Path(merge_base_file.name).stem
                base_suffix = Path(merge_base_file.name).suffix
                date_pattern = _re.compile(r"\d{8}")
                if date_pattern.search(base_stem):
                    new_stem = date_pattern.sub(TODAY_STR, base_stem)
                else:
                    new_stem = base_stem + f"_{TODAY_STR}"
                merged_filename = new_stem + base_suffix

                # 기존 파일과 동일한 폴더 (업로드된 파일이므로 OUTPUT_DIR 사용)
                merged_path = OUTPUT_DIR / merged_filename
                write_merged(merged_df, merged_path)

                n_base  = len(base_df)
                n_incr  = len(incr_df)
                n_total = len(merged_df)
                st.success(
                    f"✅ 병합 완료\n"
                    f"- 기존: {n_base:,}건 / 증분: {n_incr:,}건 / 병합 후 합계: {n_total:,}건\n"
                    f"- 저장 위치: {merged_path}"
                )
                st.download_button(
                    "⬇️ 병합 파일 다운로드",
                    data=merged_df_to_bytes(merged_df),
                    file_name=merged_filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
        except Exception as e:
            st.error(f"❌ 오류: {e}")


# ═══════════════════════════════════════════════════════════════
# 탭2: 분류
# ═══════════════════════════════════════════════════════════════
with tab_classify:
    st.header("자동 분류")

    if not st.session_state.scraping_done:
        st.info("먼저 **스크래핑** 탭에서 수집을 완료하세요.")
        st.stop()

    # 분류체계 로드
    taxonomy = load_taxonomy(TAXONOMY_FILE if TAXONOMY_FILE.exists() else None)
    if not taxonomy:
        if not TAXONOMY_FILE.exists():
            st.error("❌ 분류체계.xlsx 파일이 없습니다. 사이드바에서 파일을 업로드하세요.")
        else:
            st.error(
                "❌ 분류체계.xlsx를 읽었으나 키워드가 0건입니다.\n\n"
                "시트 이름이 **'분류체계(키워드포함)'** 인지, "
                "'키워드'로 시작하는 컬럼이 있는지 확인하세요."
            )
        st.stop()

    # 자동 분류 실행 (스크래핑 완료 직후 또는 버튼)
    if not st.session_state.classify_done:
        with st.spinner("분류 중..."):
            classified = classify_all(st.session_state.all_rows, taxonomy)
            # 일련번호 추가
            for i, r in enumerate(classified, 1):
                r["일련번호"] = i
            st.session_state.classified_rows = classified
            st.session_state.classify_done   = True

    classified_rows = st.session_state.classified_rows

    # ── 통계 ─────────────────────────────────────────────────────
    s = stats(classified_rows)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("전체",    f"{s['전체']:,}건")
    c2.metric("✅ 분류완료", f"{s['분류완료']:,}건",
              f"{s['분류완료']/max(s['전체'],1)*100:.1f}%")
    c3.metric("🟡 부분일치", f"{s['부분일치']:,}건",
              f"{s['부분일치']/max(s['전체'],1)*100:.1f}%")
    c4.metric("🔴 검토필요", f"{s['검토필요']:,}건",
              f"{s['검토필요']/max(s['전체'],1)*100:.1f}%")

    st.divider()

    # ── 색상 적용 테이블 ──────────────────────────────────────────
    df = pd.DataFrame(classified_rows)[CLASSIFIED_COLUMNS]

    def _row_color(row):
        color_map = {"분류완료": "#C6EFCE", "부분일치": "#FFEB9C", "검토필요": "#FFC7CE"}
        color = color_map.get(row["분류상태"], "")
        return [f"background-color: {color}" if color else ""] * len(row)

    st.subheader(f"분류 결과 (상위 200건 미리보기 / 총 {len(df):,}건)")
    styled = df.head(200).style.apply(_row_color, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── 다운로드 ──────────────────────────────────────────────────
    excel_bytes = to_bytes_classified(classified_rows)
    st.download_button(
        "⬇️ 분류 결과 엑셀 다운로드 (전체 + 검토필요 시트)",
        data=excel_bytes,
        file_name=f"legal_forms_classified_{TODAY_STR}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    # 로컬 저장
    write_classified(classified_rows, OUTPUT_DIR / f"legal_forms_classified_{TODAY_STR}.xlsx")
