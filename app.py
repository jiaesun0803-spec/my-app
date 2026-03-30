import streamlit as st
import json
import os
import time
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go
from datetime import datetime

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

# --- 유틸리티 함수 ---
def safe_int(value):
    try:
        clean_val = str(value).replace(',', '').strip()
        if not clean_val: return 0
        return int(float(clean_val))
    except: return 0

def format_kr_currency(value):
    try:
        val = safe_int(value)
        if val == 0: return "0원"
        uk, man = val // 10000, val % 10000
        if uk > 0 and man > 0: return f"{uk}억 {man:,}만원"
        elif uk > 0: return f"{uk}억원"
        else: return f"{man:,}만원"
    except: return str(value)

def format_biz_no(raw_no):
    no = str(raw_no).replace("-", "").strip()
    return f"{no[:3]}-{no[3:5]}-{no[5:]}" if len(no) == 10 else raw_no

def format_corp_no(raw_no):
    no = str(raw_no).replace("-", "").strip()
    return f"{no[:6]}-{no[6:]}" if len(no) == 13 else raw_no

# [수정] NotFound 에러 방지를 위한 안정적인 모델 선택 로직
def get_best_model_name():
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # 가장 범용적인 gemini-1.5-flash 모델을 우선적으로 models/ 경로를 포함하여 지정
        if 'models/gemini-1.5-flash' in available: return 'models/gemini-1.5-flash'
        if 'models/gemini-pro' in available: return 'models/gemini-pro'
        return available[0] if available else 'models/gemini-1.5-flash'
    except:
        return 'models/gemini-1.5-flash'

def clean_html(text): 
    return "\n".join([l.lstrip() for l in text.replace("```html", "").replace("```", "").strip().split("\n")])

if check_password():
    DB_FILE = "company_db.json"
    def load_db():
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f: return json.load(f)
            except: return {}
        return {}
    def save_db(db_data):
        with open(DB_FILE, "w", encoding="utf-8") as f: json.dump(db_data, f, ensure_ascii=False, indent=4)

    # ==========================================
    # 1. 사이드바 (데이터 보존 로직 강화)
    # ==========================================
    st.sidebar.header("⚙️ AI 엔진 설정")
    if "api_key" not in st.session_state: 
        st.session_state["api_key"] = st.secrets.get("GEMINI_API_KEY", "")
    api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")
    if st.sidebar.button("💾 API KEY 저장"):
        st.session_state["api_key"] = api_key_input
        st.sidebar.success("✅ 저장 완료!")

    if st.session_state["api_key"]:
        genai.configure(api_key=st.session_state["api_key"])

    st.sidebar.markdown("---")
    st.sidebar.header("📂 업체 관리")
    db = load_db()
    if st.sidebar.button("💾 현재 업체 정보 저장", use_container_width=True):
        cn = st.session_state.get("in_company_name", "").strip()
        if cn:
            current_data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            db[cn] = current_data
            save_db(db)
            st.sidebar.success(f"✅ '{cn}' 저장 완료!")

    selected_company = st.sidebar.selectbox("저장된 업체 목록", ["선택 안 함"] + list(db.keys()))
    col_s1, col_s2 = st.sidebar.columns(2)
    with col_s1:
        if st.button("📂 불러오기", use_container_width=True) and selected_company != "선택 안 함":
            for k, v in db[selected_company].items(): st.session_state[k] = v
            st.session_state["view_mode"] = "INPUT"
            st.rerun()
    with col_s2:
        if st.button("🔄 초기화", use_container_width=True):
            for k in [k for k in st.session_state.keys() if k.startswith("in_") or k in ["permanent_data", "generated_report", "generated_matching", "kosme_result_html", "semas_result_html"]]:
                del st.session_state[k]
            st.cache_data.clear()
            st.rerun()

    # 빠른 리포트 생성 탭 복구
    def change_mode(mode):
        st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        st.session_state["view_mode"] = mode
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("🚀 빠른 리포트 생성")
    if st.sidebar.button("📊 AI기업분석리포트", key="side_1", use_container_width=True): change_mode("REPORT")
    if st.sidebar.button("💡 AI 정책자금 매칭리포트", key="side_2", use_container_width=True): change_mode("MATCHING")
    if st.sidebar.button("📝 기관별 융자/사업계획서", key="side_3", use_container_width=True): change_mode("PLAN")

    # ==========================================
    # 2. 메인 대시보드 (입력 폼)
    # ==========================================
    if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"

    st.title("📊 AI 컨설팅 대시보드")
    t1, t2, t3, t4 = st.columns(4)
    with t1: 
        if st.button("📊 AI기업분석리포트", key="top_1", use_container_width=True, type="primary"): change_mode("REPORT")
    with t2: 
        if st.button("💡 AI 정책자금 매칭리포트", key="top_2", use_container_width=True, type="primary"): change_mode("MATCHING")
    with t3: 
        if st.button("📝 기관별 융자/사업계획서", key="top_3", use_container_width=True, type="primary"): change_mode("PLAN")
    with t4: 
        if st.button("📑 AI 사업계획서", key="top_4", use_container_width=True, type="primary"): change_mode("FULL_PLAN")
    st.markdown("<hr>", unsafe_allow_html=True)

    if st.session_state["view_mode"] == "INPUT":
        st.header("1. 기업현황")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.text_input("기업명", key="in_company_name")
            st.text_input("사업자번호", key="in_raw_biz_no")
            if st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type") == "법인":
                st.text_input("법인등록번호", key="in_raw_corp_no")
        with c2:
            st.text_input("사업개시일", placeholder="YYYY.MM.DD", key="in_start_date")
            st.selectbox("업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")
            st.number_input("상시근로자수(명)", value=0, step=1, key="in_employee_count")
        with c3:
            st.text_input("전화번호", key="in_biz_tel")
            st.text_input("사업장 주소", key="in_biz_addr")

        st.header("2. 대표자 정보")
        r1, r2, r3 = st.columns(3)
        with r1:
            st.text_input("대표자명", key="in_rep_name")
            st.text_input("연락처", key="in_rep_phone")
        with r2:
            st.text_input("이메일 주소", key="in_rep_email")
            st.text_input("거주지 주소", key="in_home_addr")
        with r3:
            st.selectbox("최종학력", ["고졸", "전문대졸", "대졸", "석사", "박사"], key="in_edu_school")
            st.text_area("경력사항", key="in_career", height=68)

        st.header("3. 신용 및 매출 현황")
        cr1, cr2 = st.columns(2)
        with cr1:
            st.number_input("NICE 신용점수", value=0, key="in_nice_score")
            st.radio("세금체납 여부", ["무", "유"], horizontal=True, key="in_tax_status")
        with cr2:
            st.number_input("금년 매출(만원)", value=0, key="in_sales_current")
            st.number_input("전년 매출(만원)", value=0, key="in_sales_2025")

        st.header("4. 기대출 현황(만원)")
        d1, d2, d3, d4 = st.columns(4)
        with d1: st.number_input("중진공", value=0, key="in_debt_kosme")
        with d2: st.number_input("소진공", value=0, key="in_debt_semas")
        with d3: st.number_input("신보/기보", value=0, key="in_debt_guarantee")
        with d4: st.number_input("은행/기타", value=0, key="in_debt_etc")

        st.header("5. 필요자금")
        p1, p2, p3 = st.columns([1, 1, 2])
        with p1: st.selectbox("자금구분", ["운전자금", "시설자금"], key="in_fund_type")
        with p2: st.number_input("요청금액(만원)", value=0, key="in_req_amount")
        with p3: st.text_input("자금용도", key="in_fund_purpose")

        # [복구] 보유인증 2열 나열
        st.header("6. 보유 인증 (복구)")
        cert_list = ["소상공인확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
        cols = st.columns(2)
        for idx, cert in enumerate(cert_list):
            with cols[idx % 2]:
                st.checkbox(cert, key=f"in_cert_{cert}")

        # [복구] 특허 및 정부지원 조건부 입력
        st.header("7. 특허 및 정부지원 (복구)")
        pat_col, gov_col = st.columns(2)
        with pat_col:
            if st.radio("특허 보유여부", ["무", "유"], horizontal=True, key="in_has_patent") == "유":
                st.number_input("보유 건수", min_value=0, step=1, key="in_pat_cnt")
                st.text_area("특허 번호/명칭", key="in_pat_details", placeholder="번호와 명칭을 입력하세요")
        with gov_col:
            if st.radio("정부지원 수혜이력", ["무", "유"], horizontal=True, key="in_has_gov") == "유":
                st.number_input("수혜 건수", min_value=0, step=1, key="in_gov_cnt")
                st.text_area("지원사업명", key="in_gov_details", placeholder="수혜받은 사업명을 입력하세요")

        # [복구] 비즈니스 정보 7종
        st.header("8. 비즈니스 상세 정보 (복구)")
        st.text_area("핵심 아이템", key="in_item_desc", placeholder="제품/서비스의 핵심 내용을 입력하세요")
        st.text_input("제품 생산 공정도", key="in_process_desc", placeholder="예: 원물 입고 -> 세척 -> 조리 -> 포장")
        b_c1, b_c2 = st.columns(2)
        with b_c1:
            st.text_input("주거래처 1", key="in_client_1")
            st.text_input("주거래처 2", key="in_client_2")
            st.text_input("주거래처 3", key="in_client_3")
        with b_c2:
            st.text_area("판매루트 및 시장현황", key="in_sales_route", height=110)
        st.text_area("차별화 포인트", key="in_diff_point")
        st.text_area("앞으로의 계획", key="in_future_plan")
        st.success("✅ 모든 정보가 입력되었습니다. 상단 탭에서 리포트를 생성하세요.")

    # ---------------------------------------------------------
    # 3. 리포트 출력 화면 (데이터 보존 로직 적용)
    # ---------------------------------------------------------
    else:
        if st.button("⬅️ 입력 화면으로 돌아가기"):
            st.session_state["view_mode"] = "INPUT"; st.rerun()

        d = st.session_state.get("permanent_data", {})
        cn = d.get('in_company_name', '미입력').strip()
        model_name = get_best_model_name()
        model = genai.GenerativeModel(model_name)

        if st.session_state["view_mode"] == "REPORT":
            st.subheader(f"📊 AI기업분석리포트: {cn}")
            with st.status("🚀기업분석리포트는 생성중입니다"):
                # 프롬프트에서 컨설턴트 정보 배제 및 기업현황표 강화
                pr = f"전문 컨설턴트. {cn} 기업 분석. HTML 작성. 최상단에 기업명, 사업자번호({d.get('in_raw_biz_no','')}), 업종({d.get('in_industry','')}), 주소({d.get('in_biz_addr','')}) 표 포함. 아이템 {d.get('in_item_desc','')} 분석."
                res = clean_html(model.generate_content(pr).text)
            st.markdown(res, unsafe_allow_html=True)

        elif st.session_state["view_mode"] == "MATCHING":
            st.subheader(f"💡 AI 정책자금 매칭리포트: {cn}")
            with st.status("🚀전년도 매출 기준으로 심사를 진행 중입니다"):
                # 대표님 요청 순위 로직 적용
                is_mfg = (d.get('in_industry') == "제조업" or safe_int(d.get('in_employee_count')) >= 5 or safe_int(d.get('in_sales_current')) >= 500000)
                rank = "제조/대규모형(1:중진공+소진공, 2:기보, 3:지역신보, 4:은행)" if is_mfg else "소상공인형(1:소진공, 2:신보, 3:지역신보, 4:은행)"
                pr = f"정책자금 전문가. {cn} 매칭 리포트. HTML. 매출({format_kr_currency(d.get('in_sales_current',0))}), 필요자금({format_kr_currency(d.get('in_req_amount',0))}) 요약표 포함. 추천순서: {rank} 준수."
                res = clean_html(model.generate_content(pr).text)
            st.markdown(res, unsafe_allow_html=True)

        elif st.session_state["view_mode"] == "PLAN":
            st.subheader("📝 기관별 융자/사업계획서 자동 생성")
            tabs = st.tabs(["중소벤처기업진흥공단", "소상공인시장진흥공단"])
            with tabs[0]:
                k_cats = {"혁신창업": ["청년전용창업", "개발기술사업화"], "신시장": ["수출기업글로벌화"], "신성장": ["혁신성장", "스케일업금융"]}
                c1, c2 = st.columns(2); mk = c1.selectbox("대분류", list(k_cats.keys())); sk = c2.selectbox("세부자금", k_cats[mk])
                if st.button(f"🚀 {cn} 중진공 {sk} 신청서 생성"):
                    with st.status("서식 작성 중..."):
                        pr = f"<h2 style='text-align:center;'>{cn} 중진공 {sk} 융자신청서 및 사업계획서</h2> 내용을 HTML 표로 아주 상세히 작성."
                        st.session_state["kosme_html"] = clean_html(model.generate_content(pr).text)
                if "kosme_html" in st.session_state: st.markdown(st.session_state["kosme_html"], unsafe_allow_html=True)
            with tabs[1]:
                s_cats = ["혁신성장촉진자금", "상생성장지원자금", "재도전특별자금", "일시적경영애로자금"]
                sk_s = st.selectbox("소진공 자금종류", s_cats)
                if st.button(f"🚀 {cn} 소진공 {sk_s} 신청서 생성"):
                    with st.status("서식 작성 중..."):
                        pr = f"{cn} 소상공인 {sk_s} 신청용 사업계획서. HTML로 작성."
                        st.session_state["semas_html"] = clean_html(model.generate_content(pr).text)
                if "semas_html" in st.session_state: st.markdown(st.session_state["semas_html"], unsafe_allow_html=True)
