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
# 0. 핵심 설정 및 데이터 세이프가드
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

def safe_int(value):
    try:
        clean_val = str(value or 0).replace(',', '').strip()
        return int(float(clean_val))
    except: return 0

def format_kr_currency(value):
    val = safe_int(value)
    if val == 0: return "0원"
    uk, man = val // 10000, val % 10000
    if uk > 0 and man > 0: return f"{uk}억 {man:,}만원"
    elif uk > 0: return f"{uk}억원"
    else: return f"{man:,}만원"

def format_biz_no(val):
    v = str(val or "").replace("-", "").strip()
    return f"{v[:3]}-{v[3:5]}-{v[5:]}" if len(v) == 10 else val

def format_corp_no(val):
    v = str(val or "").replace("-", "").strip()
    return f"{v[:6]}-{v[6:]}" if len(v) == 13 else val

def clean_html(text):
    if not text: return ""
    cleaned = text.replace("```html", "").replace("```", "").strip()
    return "\n".join([l.lstrip() for l in cleaned.split("\n")])

def get_best_model_name():
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        if 'models/gemini-1.5-flash' in available: return 'models/gemini-1.5-flash'
        return 'models/gemini-pro'
    except: return 'models/gemini-1.5-flash'

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"

def change_mode(target):
    st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
    st.session_state["view_mode"] = target
    st.rerun()

# ==========================================
# 1. 보안 및 DB 설정
# ==========================================
if "password_correct" not in st.session_state:
    st.title("🔐 AI 컨설팅 시스템")
    pw = st.text_input("접속 비밀번호를 입력하세요", type="password")
    if st.button("접속"):
        if pw == st.secrets.get("LOGIN_PASSWORD", "1234"):
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("비밀번호가 틀렸습니다.")
    st.stop()

DB_FILE = "company_db.json"
def load_db(): return json.load(open(DB_FILE, "r", encoding="utf-8")) if os.path.exists(DB_FILE) else {}
def save_db(data): json.dump(data, open(DB_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)

# ==========================================
# 2. 사이드바 관리
# ==========================================
st.sidebar.header("⚙️ AI 엔진 설정")
if "api_key" not in st.session_state: st.session_state["api_key"] = ""
api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")
if st.sidebar.button("💾 API KEY 저장"):
    st.session_state["api_key"] = api_key_input; st.sidebar.success("저장 완료!")
if st.session_state["api_key"]: genai.configure(api_key=st.session_state["api_key"])

st.sidebar.markdown("---")
st.sidebar.header("📂 업체 관리")
db = load_db()
if st.sidebar.button("💾 현재 정보 저장"):
    cn = st.session_state.get("in_company_name", "").strip()
    if cn:
        db[cn] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        save_db(db); st.sidebar.success(f"✅ 저장 완료!")

selected_company = st.sidebar.selectbox("저장된 업체 목록", ["선택 안 함"] + list(db.keys()))
c_s1, c_s2 = st.sidebar.columns(2)
with c_s1:
    if st.button("📂 불러오기") and selected_company != "선택 안 함":
        for k, v in db[selected_company].items(): st.session_state[k] = v
        st.session_state["view_mode"] = "INPUT"; st.rerun()
with c_s2:
    if st.button("🔄 초기화"):
        for k in [k for k in st.session_state.keys() if k.startswith("in_")]: del st.session_state[k]
        st.session_state.pop("permanent_data", None); st.session_state["view_mode"] = "INPUT"; st.cache_data.clear(); st.rerun()

# ==========================================
# 3. 메인 화면 로직
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
t1, t2, t3, t4 = st.columns(4)
with t1: 
    if st.button("📊 AI기업분석리포트", use_container_width=True, type="primary"): change_mode("REPORT")
with t2: 
    if st.button("💡 AI 정책자금 매칭리포트", use_container_width=True, type="primary"): change_mode("MATCHING")
with t3: 
    if st.button("📝 기관별 융자/사업계획서", use_container_width=True, type="primary"): change_mode("PLAN")
with t4: 
    if st.button("📑 AI 사업계획서", use_container_width=True, type="primary"): change_mode("FULL_PLAN")
st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

if st.session_state["view_mode"] == "INPUT":
    # --- 1. 기업현황 (유지) ---
    st.header("1. 기업현황")
    r1c1, r1c2, r1c3, r1c4 = st.columns([2, 1, 1.5, 1.5])
    with r1c1: st.text_input("기업명", key="in_company_name")
    with r1c2: biz_type = st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
    with r1c3: st.text_input("사업자번호", placeholder="000-00-00000", key="in_raw_biz_no", on_change=lambda: st.session_state.update({"in_raw_biz_no": format_biz_no(st.session_state.in_raw_biz_no)}))
    with r1c4: 
        if biz_type == "법인": st.text_input("법인등록번호", placeholder="000000-0000000", key="in_raw_corp_no", on_change=lambda: st.session_state.update({"in_raw_corp_no": format_corp_no(st.session_state.in_raw_corp_no)}))
    
    r2c1, r2c2, r2c3 = st.columns([1, 2, 1])
    with r2c1: st.text_input("사업개시일", placeholder="YYYY.MM.DD", key="in_start_date")
    with r2c2: st.text_input("사업장 주소", key="in_biz_addr")
    with r2c3: st.selectbox("업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")

    r3c1, r3c2 = st.columns([1, 3])
    with r3c1: st.text_input("전화번호", placeholder="010-0000-0000", key="in_biz_tel")
    with r3c2:
        ls_cols = st.columns([1, 1, 1])
        with ls_cols[0]: lease_status = st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
        if lease_status == "임대":
            with ls_cols[1]: st.number_input("보증금(만원)", value=0, step=1, key="in_lease_deposit")
            with ls_cols[2]: st.number_input("월임대료(만원)", value=0, step=1, key="in_lease_rent")

    r4c1, r4c2 = st.columns([1, 3])
    with r4c1: st.number_input("상시근로자수(명)", value=0, key="in_employee_count")
    with r4c2:
        add_cols = st.columns([1, 2])
        if add_cols[0].radio("추가사업장현황", ["무", "유"], horizontal=True, key="in_has_add") == "유":
            add_cols[1].text_input("추가 사업장명", key="in_add_info")

    # --- 2. 대표자 정보 (유지) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("2. 대표자 정보")
    rep_r1_cols = st.columns(4)
    with rep_r1_cols[0]: st.text_input("대표자명", key="in_rep_name")
    with rep_r1_cols[1]: st.text_input("생년월일", placeholder="YYYY.MM.DD", key="in_rep_dob")
    with rep_r1_cols[2]: st.text_input("연락처", placeholder="010-0000-0000", key="in_rep_phone")
    with rep_r1_cols[3]: st.selectbox("통신사", ["SKT", "KT", "LG U+", "알뜰폰"], key="in_rep_telecom")

    rep_r2_cols = st.columns([2, 1, 1])
    with rep_r2_cols[0]: st.text_input("거주지 주소", key="in_home_addr")
    with rep_r2_cols[1]: st.selectbox("최종학력", ["중학교 졸업", "고등학교 졸업", "대학교 졸업", "석사 수료", "박사 수료"], key="in_edu_school")
    with rep_r2_cols[2]: st.text_input("전공", key="in_edu_major")

    rep_r3_cols = st.columns([1, 1])
    with rep_r3_cols[0]: st.text_input("이메일 주소", key="in_rep_email")
    with rep_r3_cols[1]: st.text_area("경력사항", key="in_career", height=68)

    rep_r4_cols = st.columns([1.5, 2.5])
    with rep_r4_cols[0]: st.radio("거주지 상태", ["자가", "임대"], horizontal=True, key="in_home_status")
    with rep_r4_cols[1]: st.multiselect("부동산 소유현황", ["아파트", "빌라", "토지", "임야", "공장", "기타"], key="in_real_estate")

    # --- 3. 신용 정보 (수정 적용) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("3. 신용 정보")
    
    credit_col1, credit_col2 = st.columns([2, 1])
    
    with credit_col1:
        # 1행: 금융연체 / 세금체납
        c_r1_1, c_r1_2 = st.columns(2)
        with c_r1_1: st.radio("금융연체 여부", ["무", "유"], horizontal=True, key="in_fin_delinquency")
        with c_r1_2: st.radio("세금체납 여부", ["무", "유"], horizontal=True, key="in_tax_delinquency")
        
        # 2행: KCB 점수 / NICE 점수
        c_r2_1, c_r2_2 = st.columns(2)
        with c_r2_1: st.number_input("KCB 점수", value=0, key="in_kcb_score")
        with c_r2_2: st.number_input("NICE 점수", value=0, key="in_nice_score")
        
    with credit_col2:
        st.markdown("""
        <div style='background-color: #f8f9fa; padding: 10px; border-radius: 5px; border: 1px solid #dee2e6;'>
            <p style='margin-bottom: 5px; font-weight: bold; font-size: 0.9em; text-align: center;'>🏆 신용점수 등급표 (참고)</p>
            <table style='width: 100%; font-size: 0.8em; text-align: center;'>
                <tr style='background-color: #e9ecef;'><th>등급</th><th>KCB</th><th>NICE</th></tr>
                <tr><td>1</td><td>942~</td><td>900~</td></tr>
                <tr><td>2</td><td>891~</td><td>870~</td></tr>
                <tr><td>3</td><td>832~</td><td>840~</td></tr>
                <tr><td>4</td><td>768~</td><td>805~</td></tr>
                <tr><td>5</td><td>698~</td><td>750~</td></tr>
                <tr><td>6</td><td>630~</td><td>665~</td></tr>
                <tr><td>7</td><td>530~</td><td>600~</td></tr>
                <tr><td>8</td><td>454~</td><td>515~</td></tr>
                <tr><td>9</td><td>335~</td><td>445~</td></tr>
                <tr><td>10</td><td>~334</td><td>~444</td></tr>
            </table>
        </div>
        """, unsafe_allow_html=True)

    # --- 4. 매출 현황 ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("4. 매출 현황 (만원)")
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.number_input("금년 매출합계", value=0, key="in_sales_cur")
        st.number_input("24년 매출합계", value=0, key="in_sales_24")
    with m_col2:
        st.number_input("25년 예상매출", value=0, key="in_sales_25")
        st.number_input("23년 매출합계", value=0, key="in_sales_23")

    # --- 5. 기대출 및 필요자금 ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("5. 기대출 및 필요자금 (만원)")
    d_col1, d_col2, d_col3, d_col4 = st.columns(4)
    with d_col1: st.number_input("중진공", value=0, key="in_debt_kosme")
    with d_col2: st.number_input("소진공", value=0, key="in_debt_semas")
    with d_col3: st.number_input("보증기금(신/기)", value=0, key="in_debt_guarantee")
    with d_col4: st.number_input("필요자금", value=0, key="in_req_amount")
    st.text_input("자금 용도", key="in_req_purpose")

    # --- 6. 보유 인증 ---
    st.header("6. 보유 인증 (4열 배치)")
    cert_list = ["소상공인확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
    for i in range(0, len(cert_list), 4):
        cols = st.columns(4)
        for j in range(4):
            if i + j < len(cert_list): cols[j].checkbox(cert_list[i + j], key=f"in_cert_{cert_list[i + j]}")

    # --- 7. 특허 및 정부지원 ---
    st.header("7. 특허 및 정부지원")
    pg_col1, pg_col2 = st.columns(2)
    with pg_col1:
        if st.radio("특허 보유 여부", ["무", "유"], horizontal=True, key="in_has_patent") == "유":
            st.number_input("특허 건수", value=0, key="in_pat_cnt")
            st.text_area("특허 명칭/번호", key="in_pat_desc")
    with pg_col2:
        if st.radio("정부지원 수혜이력", ["무", "유"], horizontal=True, key="in_has_gov") == "유":
            st.number_input("수혜 건수", value=0, key="in_gov_cnt")
            st.text_area("지원 사업명", key="in_gov_desc")

    # --- 8. 비즈니스 정보 ---
    st.header("8. 비즈니스 정보")
    st.text_area("핵심 아이템 상세 설명", key="in_item_desc")
    st.text_input("제품 생산 공정도", key="in_process_desc")
    st.text_area("시장 현황 및 앞으로의 계획", key="in_future_plan")

    st.success("✅ 모든 정보 정렬 완료! 상단 리포트 버튼을 클릭하세요.")

# ==========================================
# 5. 리포트 출력 화면
# ==========================================
else:
    if st.button("⬅️ 입력 화면으로 돌아가기"):
        if "permanent_data" in st.session_state:
            for k, v in st.session_state["permanent_data"].items(): st.session_state[k] = v
        st.session_state["view_mode"] = "INPUT"; st.rerun()

    d = st.session_state.get("permanent_data", {})
    cn = d.get('in_company_name', '미입력').strip()
    model = genai.GenerativeModel(get_best_model_name())

    if st.session_state["view_mode"] == "REPORT":
        st.subheader(f"📊 AI기업분석리포트: {cn}")
        with st.status("🚀분석 중..."):
            pr = f"{cn} 기업분석 HTML. 최상단 현황표에 대표자:{d.get('in_rep_name')}, KCB:{d.get('in_kcb_score')}, NICE:{d.get('in_nice_score')} 포함."
            res = clean_html(model.generate_content(pr).text)
        st.markdown(res, unsafe_allow_html=True)
    
    elif st.session_state["view_mode"] == "MATCHING":
        st.subheader(f"💡 AI 정책자금 매칭리포트: {cn}")
        with st.status("🚀심사 중..."):
            pr = f"{cn} 정책자금 매칭 HTML. 신용점수 KCB:{d.get('in_kcb_score')}, NICE:{d.get('in_nice_score')} 반영."
            res = clean_html(model.generate_content(pr).text)
        st.markdown(res, unsafe_allow_html=True)
