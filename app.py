import streamlit as st
import json
import io
import os
import re
import random
import datetime
import pandas as pd
import google.generativeai as genai
import plotly.graph_objects as go
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR

# ==========================================
# 0. 보안 및 기본 설정
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 AI 컨설팅 시스템")
        correct_pw = st.secrets.get("LOGIN_PASSWORD", "1234")
        pw = st.text_input("접속 비밀번호를 입력하세요", type="password")
        if st.button("접속"):
            if pw == correct_pw:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
        return False
    return True

if check_password():
    # --- 데이터 관리 함수 ---
    DB_FILE = "company_db.json"
    def load_db(): return json.load(open(DB_FILE, "r", encoding="utf-8")) if os.path.exists(DB_FILE) else {}
    def save_db(db_data): json.dump(db_data, open(DB_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)

    # 신용등급 판정 로직
    def get_credit_grade(score, type="NICE"):
        if type == "NICE":
            if score >= 900: return 1
            elif score >= 870: return 2
            elif score >= 840: return 3
            elif score >= 805: return 4
            elif score >= 750: return 5
            elif score >= 665: return 6
            elif score >= 600: return 7
            elif score >= 515: return 8
            elif score >= 445: return 9
            else: return 10
        else: # KCB
            if score >= 942: return 1
            elif score >= 891: return 2
            elif score >= 832: return 3
            elif score >= 768: return 4
            elif score >= 698: return 5
            elif score >= 630: return 6
            elif score >= 530: return 7
            elif score >= 454: return 8
            elif score >= 335: return 9
            else: return 10

    # ==========================================
    # 1. 사이드바 (기존 기능 100% 유지)
    # ==========================================
    st.sidebar.header("📁 업체 관리")
    db = load_db()
    if st.sidebar.button("💾 현재 정보 저장", use_container_width=True):
        c_name = st.session_state.get("in_company_name", "").strip()
        if c_name:
            db[c_name] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            save_db(db); st.sidebar.success("저장 완료!")
    
    selected_company = st.sidebar.selectbox("📂 업체 목록", ["새 업체 입력"] + list(db.keys()))
    if st.sidebar.button("불러오기", use_container_width=True):
        if selected_company != "새 업체 입력":
            for k, v in db[selected_company].items(): st.session_state[k] = v
            st.rerun()

    # ==========================================
    # 2. 메인 대시보드 (전면 수정 레이아웃)
    # ==========================================
    st.title("📊 AI 컨설팅 대시보드")
    
    # 상단 탭 (유지)
    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1: st.button("📊 1. 기업분석리포트 생성", use_container_width=True, type="primary")
    with col_t2: st.button("💡 2. 정책자금 매칭 리포트", use_container_width=True)
    with col_t3: st.button("📝 3. 사업계획서 생성", use_container_width=True)

    # --- 1. 기업현황 ---
    st.header("1. 기업현황")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.text_input("기업명", key="in_company_name")
        st.text_input("사업자등록번호", key="in_raw_biz_no")
        biz_type = st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
        if biz_type == "법인":
            st.text_input("법인등록번호", key="in_raw_corp_no")
    with c2:
        st.text_input("사업개시일", placeholder="2020.01.01", key="in_start_date")
        st.selectbox("업종", ["제조업", "도소매업", "서비스업", "IT업", "건설업", "음식점업", "기타"], key="in_industry")
        st.radio("사업장 임대여부", ["임대", "자가"], horizontal=True, key="in_lease_status")
    with c3:
        st.text_input("사업장 전화번호", key="in_biz_tel")
        st.text_input("사업장 팩스번호", key="in_biz_fax")
        st.text_input("사업장 주소", key="in_biz_addr")

    # --- 2. 대표자 정보 ---
    st.header("2. 대표자 정보")
    r1, r2, r3 = st.columns(3)
    with r1:
        st.text_input("대표자명", key="in_rep_name")
        st.text_input("대표자 연락처", key="in_rep_phone")
        st.selectbox("통신사", ["SKT", "KT", "LG U+", "알뜰폰"], key="in_rep_telecom")
        st.text_input("이메일 주소", key="in_rep_email")
    with r2:
        st.text_input("거주지 주소", key="in_home_addr")
        st.radio("거주지 주거상태", ["자가", "임대"], horizontal=True, key="in_home_status")
        st.text_input("부동산 소유현황", key="in_real_estate")
    with r3:
        st.text_input("최종학교", key="in_edu_school")
        st.text_input("학과", key="in_edu_major")
        st.text_area("경력(최근기준)", key="in_career")

    st.subheader("📌 신용 및 연체 정보")
    cr1, cr2 = st.columns(2)
    with cr1:
        # 세금체납/금융연체 한줄 배치
        cc1, cc2 = st.columns(2)
        with cc1: st.checkbox("세금체납 유/무", key="in_tax_overdue")
        with cc2: st.checkbox("금융연체 유/무", key="in_fin_overdue")
        
        # 신용점수 한줄 배치
        sc1, sc2 = st.columns(2)
        with sc1: kcb_score = st.number_input("KCB 신용점수", 0, 1000, 800, key="in_kcb_score")
        with sc2: nice_score = st.number_input("NICE 신용점수", 0, 1000, 800, key="in_nice_score")
    
    with cr2:
        # 우측 그래프 삭제 후 판정 결과 텍스트 출력
        kcb_g = get_credit_grade(kcb_score, "KCB")
        nice_g = get_credit_grade(nice_score, "NICE")
        st.markdown(f"""
        <div style="background-color:#f0f2f6; padding:20px; border-radius:10px; border-left:5px solid #174EA6;">
            <h4 style="margin:0;">🏆 신용등급 판정 결과</h4>
            <p style="font-size:18px; margin:10px 0;">KCB(올크레딧): <b>{kcb_g}등급</b> | NICE(나이스): <b>{nice_g}등급</b></p>
        </div>
        """, unsafe_allow_html=True)

    # --- 3. 재무현황 ---
    st.header("3. 재무현황")
    st.subheader("매출정보 (단위: 만 원)")
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.number_input("금년 매출액", key="in_sales_current")
    with m2: st.number_input("25년도 매출합계", key="in_sales_2025")
    with m3: st.number_input("24년도 매출합계", key="in_sales_2024")
    with m4: st.number_input("23년도 매출합계", key="in_sales_2023")

    # --- 4. 기대출현황 ---
    st.header("4. 기대출현황")
    d1, d2, d3 = st.columns(3)
    with d1: st.number_input("중진공", key="in_debt_kosme")
    with d2: st.number_input("소진공", key="in_debt_semas")
    with d3: st.number_input("신용보증재단", key="in_debt_koreg")
    d4, d5, d6, d7, d8 = st.columns(5)
    with d4: st.number_input("신용보증기금", key="in_debt_kodit")
    with d5: st.number_input("기술보증기금", key="in_debt_kibo")
    with d6: st.number_input("기타", key="in_debt_etc")
    with d7: st.number_input("신용대출", key="in_debt_credit")
    with d8: st.number_input("담보대출", key="in_debt_coll")

    # --- 5. 필요자금 ---
    st.header("5. 필요자금")
    p1, p2, p3 = st.columns([1, 1, 2])
    with p1: st.selectbox("자금구분", ["운전자금", "시설자금"], key="in_fund_type")
    with p2: st.number_input("필요자금(만원)", key="in_req_amount")
    with p3: st.text_input("자금사용용도", key="in_fund_purpose")

    # --- 6. 인증현황 ---
    st.header("6. 인증현황")
    ac1, ac2, ac3, ac4 = st.columns(4)
    with ac1: st.checkbox("소상공인확인서", key="in_chk_1"); st.checkbox("창업확인서", key="in_chk_2")
    with ac2: st.checkbox("여성기업확인서", key="in_chk_3"); st.checkbox("이노비즈", key="in_chk_4")
    with ac3: st.checkbox("벤처인증", key="in_chk_6"); st.checkbox("뿌리기업확인서", key="in_chk_7")
    with ac4: st.checkbox("ISO인증", key="in_chk_10")

    # --- 7. 비즈니스 정보 ---
    st.header("7. 비즈니스 정보")
    st.text_area("[아이템]", key="in_item_desc")
    
    st.markdown("**[주거래처 정보(매출위주)]**")
    client_col1, client_col2, client_col3 = st.columns(3)
    with client_col1: st.text_input("거래처 1", key="in_client_1")
    with client_col2: st.text_input("거래처 2", key="in_client_2")
    with client_col3: st.text_input("거래처 3", key="in_client_3")
    
    st.text_area("[판매루트]", key="in_sales_route")
    st.text_area("[시장현황]", key="in_market_status")
    st.text_area("[차별화]", key="in_diff_point")
    st.text_area("[앞으로의 계획]", key="in_future_plan")
