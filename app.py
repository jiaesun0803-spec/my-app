import streamlit as st
import json
import os
import time
import pandas as pd
import google.generativeai as genai

# ==========================================
# 0. 기본 설정 및 보안
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
    # --- 파일 관리 및 신용등급 로직 ---
    DB_FILE = "company_db.json"
    def load_db():
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
        return {}
    def save_db(db_data):
        with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(db_data, f, ensure_ascii=False, indent=4)

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
    # 1. 사이드바 (API, 업체관리, 빠른실행 완벽 복원)
    # ==========================================
    st.sidebar.header("⚙️ AI 엔진 설정")
    # session_state를 활용하여 API 키를 메모리에 즉시 저장
    if "api_key" not in st.session_state:
        st.session_state["api_key"] = ""
        
    api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")
    if st.sidebar.button("💾 API 키 적용"):
        st.session_state["api_key"] = api_key_input
        st.sidebar.success("✅ API 키 적용 완료!")
        st.rerun()

    if st.session_state["api_key"]:
        genai.configure(api_key=st.session_state["api_key"])

    st.sidebar.markdown("---")
    st.sidebar.header("📂 업체 관리")
    db = load_db()
    
    if st.sidebar.button("💾 현재 정보 저장", use_container_width=True):
        c_name = st.session_state.get("in_company_name", "").strip()
        if c_name:
            db[c_name] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            save_db(db)
            st.sidebar.success(f"✅ '{c_name}' 저장 완료!")

    selected_company = st.sidebar.selectbox("저장된 업체 목록", ["선택 안 함"] + list(db.keys()))
    col_s1, col_s2 = st.sidebar.columns(2)
    with col_s1:
        if st.button("📂 불러오기", use_container_width=True):
            if selected_company != "선택 안 함":
                for k, v in db[selected_company].items(): st.session_state[k] = v
                st.rerun()
    with col_s2:
        if st.button("🔄 초기화", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith("in_"): del st.session_state[k]
            st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("🚀 빠른 리포트 생성")
    if st.sidebar.button("📊 1. 기업분석리포트 생성", use_container_width=True):
        st.session_state["view_mode"] = "REPORT"
        st.rerun()
    if st.sidebar.button("💡 2. 정책자금 매칭 리포트", use_container_width=True):
        st.sidebar.info("개발 중입니다.")
    if st.sidebar.button("📝 3. 사업계획서 생성", use_container_width=True):
        st.sidebar.info("개발 중입니다.")

    # ==========================================
    # 2. 화면 모드 제어
    # ==========================================
    if "view_mode" not in st.session_state:
        st.session_state["view_mode"] = "INPUT"

    # --- [리포트 화면] ---
    if st.session_state["view_mode"] == "REPORT":
        if st.button("⬅️ 대시보드로 돌아가기"):
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
        
        st.title("📋 AI 기업분석 결과보고서")
        d = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        
        if not st.session_state["api_key"]:
            st.error("⚠️ 좌측 사이드바에 API 키를 입력하고 [적용]을 눌러주세요.")
        else:
            try:
                with st.status("🚀 AI가 분석을 진행하고 있습니다...", expanded=True) as status:
                    # [핵심] 가장 안정적인 'gemini-pro' 모델로 고정하여 404 에러 완전 차단
                    model = genai.GenerativeModel('gemini-pro')
                    
                    st.write("📍 재무/신용 데이터 및 비즈니스 현황 종합 중...")
                    time.sleep(1)
                    
                    prompt = f"""
                    당신은 전문 경영컨설턴트입니다. 다음 데이터를 바탕으로 9개 항목의 리포트를 작성하세요.
                    기업명: {d.get('in_company_name')} / 업종: {d.get('in_industry')}
                    매출(만 원): 23년({d.get('in_sales_2023')}), 24년({d.get('in_sales_2024')}), 25년({d.get('in_sales_2025')})
                    신용점수:
