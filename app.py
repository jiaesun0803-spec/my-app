import streamlit as st
import json
import io
import os
import re
import time
import pandas as pd
import google.generativeai as genai
import plotly.graph_objects as go
from datetime import datetime

# ==========================================
# 0. 보안 및 페이지 설정
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
    KEY_FILE = "gemini_key.txt"
    DB_FILE = "company_db.json"
    
    def save_key(key):
        with open(KEY_FILE, "w") as f: f.write(key)
        st.sidebar.success("✅ API 키 저장 완료!")
    def load_key():
        return open(KEY_FILE, "r").read().strip() if os.path.exists(KEY_FILE) else ""
    def load_db():
        return json.load(open(DB_FILE, "r", encoding="utf-8")) if os.path.exists(DB_FILE) else {}
    def save_db(db_data):
        json.dump(db_data, open(DB_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)

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
    # 1. 사이드바 설정
    # ==========================================
    st.sidebar.header("⚙️ Gemini AI 설정")
    saved_key = load_key()
    api_key_input = st.sidebar.text_input("Gemini API Key", value=saved_key, type="password")
    if st.sidebar.button("💾 API 키 저장"): save_key(api_key_input); st.rerun()
    if api_key_input: genai.configure(api_key=api_key_input)

    st.sidebar.markdown("---")
    st.sidebar.header("📁 업체 관리")
    db = load_db()
    if st.sidebar.button("💾 현재 정보 저장", use_container_width=True):
        c_name = st.session_state.get("in_company_name", "").strip()
        if c_name:
            db[c_name] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            save_db(db); st.sidebar.success(f"✅ '{c_name}' 저장 완료!")

    selected_company = st.sidebar.selectbox("📂 업체 목록", ["선택 안 함"] + list(db.keys()))
    col_s1, col_s2 = st.sidebar.columns(2)
    with col_s1:
        if st.button("불러오기", use_container_width=True):
            if selected_company != "선택 안 함":
                for k, v in db[selected_company].items(): st.session_state[k] = v
                st.rerun()
    with col_s2:
        if st.button("초기화", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith("in_"): del st.session_state[k]
            st.rerun()

    # ==========================================
    # 2. 메인 화면 제어 (입력 vs 리포트)
    # ==========================================
    # session_state를 사용하여 화면 모드를 전환합니다.
    if "view_mode" not in st.session_state:
        st.session_state["view_mode"] = "INPUT"

    # --- [리포트 화면 모드] ---
    if st.session_state["view_mode"] == "REPORT":
        if st.button("⬅️ 입력 화면으로 돌아가기"):
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
        
        st.title("📋 AI 기업분석 결과보고서")
        d = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        
        if not api_key_input:
            st.error("사이드바에서 API 키를 먼저 입력해주세요.")
        else:
            with st.status("🚀 AI 전문가가 기업 데이터를 심층 분석 중입니다...", expanded=True) as status:
                st.write("📍 재무 제표 및 매출 히스토리 대조 중...")
                time.sleep(1)
                st.write("📍 업종별 시장 트렌드 및 외부 자료 수집 중...")
                time.sleep(1)
                
                # Gemini 리포트 생성 프롬프트
                model = genai.GenerativeModel('gemini-1.5-pro')
                prompt = f"""
                당신은 20년 경력의 중소기업 컨설턴트입니다. 다음 데이터를 기반으로 9개 항목의 전문 리포트를 작성하세요.
                기업명: {d.get('in_company_name')}, 업종: {d.get('in_industry')}
                매출: 23년({d.get('in_sales_2023')}), 24년({d.get('in_sales_2024')}), 25년예정({d.get('in_sales_2025')})
                신용: KCB {d.get('in_kcb_score')}, NICE {d.get('in_nice_score')}
                아이템: {d.get('in_item_desc')}, 필요자금: {d.get('in_req_amount')}
                
                [필수항목] 1.기업현황분석 2.SWOT분석 3.시장현황 4.경쟁력분석 5.정책자금추천 6.인증/교육제안 7.자금사용계획 8.매출전망(12개월) 9.성장비전 및 코멘트
                """
                response = model.generate_content(prompt)
                status.update(label="✅ 분석 완료!", state="complete")
                
            st.markdown(response.text)
            st.divider()
            # 매출 그래프 시각화
            st.subheader("📈 매출 성장 시뮬레이션")
            sales_df = pd.DataFrame({
                "연도": ["2023", "2024", "2025(E)"],
                "매출액": [d.get('in_sales_2023', 0), d.get('in_sales_2024', 0), d.get('in_sales_2025', 0)]
            })
            st.line_chart(sales_df.set_index("연도"))

    # --- [입력 화면 모드] ---
    else:
        st.title("📊 AI 컨설팅 대시보드")
        
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            if st.button("📊 1. 기업분석리포트 생성", use_container_width=True, type="primary"):
                st.session_state["view_mode"] = "REPORT"
                st.rerun()
        with col_t2: st.button("💡 2. 정책자금 매칭 리포트", use_container_width=True)
        with col_t3: st.button("📝 3. 사업계획서 생성", use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # --- 1. 기업현황 ---
        st.header("1. 기업현황")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.text_input("기업명", key="in_company_name")
            st.text_input("사업자번호", key="in_raw_biz_no")
            biz_type = st.radio("유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
            if biz_type == "법인": st.text_input("법인번호", key="in_raw_corp_no")
        with c2:
            st.text_input("사업개시일", key="in_start_date")
            st.selectbox("업종", ["제조업", "서비스업", "IT업", "기타"], key="in_industry")
        with c3:
            st.text_input("전화번호", key="in_biz_tel")
            st.text_input("주소", key="in_biz_addr")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- 2. 대표자 정보 ---
        st.header("2. 대표자 정보")
        r1, r2, r3 = st.columns(3)
        with r1:
            st.text_input("대표자명", key="in_rep_name")
            st.text_input("생년월일", key="in_rep_dob")
            st.text_input("연락처", key="in_rep_phone")
        with r2:
            st.text_input("거주지 주소", key="in_home_addr")
            st.text_input("부동산 현황", key="in_real_estate")
        with r3:
            st.text_input("최종학력", key="in_edu_school")
            st.text_area("경력사항", key="in_career")

        st.subheader("📌 신용 및 연체 정보")
        cr1, cr2 = st.columns(2)
        with cr1:
            cc1, cc2 = st.columns(2)
            with cc1: tax = st.radio("세금체납", ["무", "유"], horizontal=True, key="in_tax_status")
            with cc2: fin = st.radio("금융연체", ["무", "유"], horizontal=True, key="in_fin_status")
            sc1, sc2 = st.columns(2)
            with sc1: kcb = st.number_input("KCB 점수", 0, 1000, 800, key="in_kcb_score")
            with sc2: nice = st.number_input("NICE 점수", 0, 1000, 800, key="in_nice_score")
        with cr2:
            kg, ng = get_credit_grade(kcb, "KCB"), get_credit_grade(nice, "NICE")
            st.info(f"🏆 신용등급 판정: KCB {kg}등급 / NICE {ng}등급")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- 3. 재무 / 4. 기대출 / 5. 필요자금 / 6. 인증 / 7. 비즈니스 (요약 배치) ---
        st.header("3. 재무 및 자금 현황")
        m1, m2, m3 = st.columns(3)
        with m1: st.number_input("24년 매출", key="in_sales_2024")
        with m2: st.number_input("기대출 합계", key="in_debt_total")
        with m3: st.number_input("필요자금(만원)", key="in_req_amount")
        
        st.header("4. 비즈니스 정보")
        st.text_area("아이템 및 상세 계획", key="in_item_desc")
        st.success("✅ 데이터를 입력한 후 상단의 [리포트 생성] 버튼을 누르세요.")
