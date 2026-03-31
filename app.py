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

# --- 신용 등급 판정 및 시각화 로직 ---
def get_kcb_info(score):
    s = safe_int(score)
    if s >= 942: return "1등급", "#1E88E5"
    if s >= 891: return "2등급", "#1E88E5"
    if s >= 832: return "3등급", "#43A047"
    if s >= 768: return "4등급", "#43A047"
    if s >= 698: return "5등급", "#FB8C00"
    if s >= 630: return "6등급", "#FB8C00"
    if s >= 530: return "7등급", "#E53935"
    return "저신용", "#E53935"

def get_nice_info(score):
    s = safe_int(score)
    if s >= 900: return "1등급", "#1E88E5"
    if s >= 870: return "2등급", "#1E88E5"
    if s >= 840: return "3등급", "#43A047"
    if s >= 805: return "4등급", "#43A047"
    if s >= 750: return "5등급", "#FB8C00"
    if s >= 665: return "6등급", "#FB8C00"
    if s >= 600: return "7등급", "#E53935"
    return "저신용", "#E53935"

def create_balanced_gauge(score, title, color):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 15, 'color': '#555'}},
        gauge = {
            'axis': {'range': [None, 1000], 'tickwidth': 1, 'tickfont': {'size': 10}},
            'bar': {'color': color},
            'bgcolor': "white",
            'borderwidth': 1,
            'steps': [
                {'range': [0, 500], 'color': '#FFEBEE'},
                {'range': [500, 800], 'color': '#FFF3E0'},
                {'range': [800, 1000], 'color': '#E8F5E9'}],
        }
    ))
    fig.update_layout(height=185, margin=dict(l=15, r=15, t=60, b=10), paper_bgcolor="rgba(0,0,0,0)")
    return fig

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"

def change_mode(target):
    st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
    st.session_state["view_mode"] = target
    st.rerun()

# ==========================================
# 1. 파일 및 보안 설정
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
# 2. 사이드바 (복구 완료)
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
if st.sidebar.button("💾 현재 업체 정보 저장"):
    cn = st.session_state.get("in_company_name", "").strip()
    if cn:
        db[cn] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        save_db(db); st.sidebar.success(f"✅ '{cn}' 저장 완료!")

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

st.sidebar.markdown("---")
st.sidebar.header("🚀 빠른 리포트 생성")
if st.sidebar.button("📊 AI기업분석리포트 생성"): change_mode("REPORT")
if st.sidebar.button("💡 AI 정책자금 매칭리포트"): change_mode("MATCHING")
if st.sidebar.button("📝 기관별 융자/사업계획서"): change_mode("PLAN")

# ==========================================
# 3. 메인 대시보드 입력 화면
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
    # --- 1. 기업현황 (완벽 복구) ---
    st.header("1. 기업현황")
    c1r1_1, c1r1_2, c1r1_3, c1r1_4 = st.columns([2, 1, 1.5, 1.5])
    with c1r1_1: st.text_input("기업명", key="in_company_name")
    with c1r1_2: biz_type = st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
    with c1r1_3: st.text_input("사업자번호", placeholder="000-00-00000", key="in_raw_biz_no")
    with c1r1_4: 
        if biz_type == "법인": st.text_input("법인등록번호", placeholder="000000-0000000", key="in_raw_corp_no")

    c1r2_1, c1r2_2, c1r2_3 = st.columns([1, 2, 1])
    with c1r2_1: st.text_input("사업개시일", placeholder="YYYY.MM.DD", key="in_start_date")
    with c1r2_2: st.text_input("사업장 주소", key="in_biz_addr")
    with c1r2_3: st.selectbox("업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")

    c1r3_1, c1r3_2 = st.columns([1, 3])
    with c1r3_1: st.text_input("전화번호", placeholder="010-0000-0000", key="in_biz_tel")
    with c1r3_2:
        ls_cols = st.columns([1, 1, 1])
        with ls_cols[0]: lease_status = st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
        if lease_status == "임대":
            with ls_cols[1]: st.number_input("보증금(만원)", value=0, key="in_lease_deposit")
            with ls_cols[2]: st.number_input("월임대료(만원)", value=0, key="in_lease_rent")

    c1r4_1, c1r4_2 = st.columns([1, 3])
    with c1r4_1: st.number_input("상시근로자수(명)", value=0, key="in_employee_count")
    with c1r4_2:
        add_cols = st.columns([1, 2])
        if add_cols[0].radio("추가사업장현황", ["무", "유"], horizontal=True, key="in_has_add") == "유":
            add_cols[1].text_input("추가 사업장명", key="in_add_info")

    # --- 2. 대표자 정보 (완벽 복구) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("2. 대표자 정보")
    c2r1_cols = st.columns(4)
    with c2r1_cols[0]: st.text_input("대표자명", key="in_rep_name")
    with c2r1_cols[1]: st.text_input("생년월일", placeholder="YYYY.MM.DD", key="in_rep_dob")
    with c2r1_cols[2]: st.text_input("연락처", placeholder="010-0000-0000", key="in_rep_phone")
    with c2r1_cols[3]: st.selectbox("통신사", ["SKT", "KT", "LG U+", "알뜰폰"], key="in_rep_telecom")

    c2r2_cols = st.columns([2, 1, 1])
    with c2r2_cols[0]: st.text_input("거주지 주소", key="in_home_addr")
    with c2r2_cols[1]: st.selectbox("최종학력", ["중학교 졸업", "고등학교 졸업", "대학교 졸업", "석사 수료", "박사 수료"], key="in_edu_school")
    with c2r2_cols[2]: st.text_input("전공", key="in_edu_major")

    c2r3_cols = st.columns([1, 2])
    with c2r3_cols[0]: st.text_input("이메일 주소", key="in_rep_email")
    with c2r3_cols[1]: st.text_area("경력사항", key="in_career", height=68)

    c2r4_cols = st.columns([1.5, 2.5])
    with c2r4_cols[0]: st.radio("거주지 상태", ["자가", "임대"], horizontal=True, key="in_home_status")
    with c2r4_cols[1]: st.multiselect("부동산 소유현황", ["아파트", "빌라", "토지", "임야", "공장", "기타"], key="in_real_estate")

    # --- 3. 신용 정보 시각화 (높이 및 정렬 최종 튜닝) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("3. 신용 정보 시각화")
    
    c3_in, c3_out = st.columns([1.6, 1])
    
    with c3_in:
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        ci_r1 = st.columns([1, 1, 2.5])
        with ci_r1[0]: delin = st.radio("금융연체 여부", ["무", "유"], horizontal=True, key="in_fin_delinquency")
        with ci_r1[1]: tax = st.radio("세금체납 여부", ["무", "유"], horizontal=True, key="in_tax_delinquency")
        with ci_r1[2]:
            if delin == "유" or tax == "유": st.error("🚨 **연체/체납 주의:** 신청 제한 가능성")
            else: st.success("✅ **신용 양호:** 특이사항 없음")

        st.markdown("<div style='margin-top: 42px;'></div>", unsafe_allow_html=True)
        # 입력창 너비를 줄이기 위해 중첩 컬럼 사용
        ci_r2 = st.columns([1, 1, 0.5])
        with ci_r2[0]: s_kcb = st.number_input("KCB 점수", value=0, max_value=1000, key="in_kcb_score")
        with ci_r2[1]: s_nice = st.number_input("NICE 점수", value=0, max_value=1000, key="in_nice_score")
        
    with c3_out:
        v_cols = st.columns(2)
        k_grade, k_color = get_kcb_info(s_kcb)
        n_grade, n_color = get_nice_info(s_nice)
        with v_cols[0]:
            st.plotly_chart(create_balanced_gauge(s_kcb, "KCB Score", k_color), use_container_width=True, config={'displayModeBar': False})
            st.markdown(f"<div style='text-align:center; padding:5px; background-color:{k_color}; color:white; border-radius:5px; font-size:0.9em; margin-top:-20px;'><b>KCB: {k_grade}</b></div>", unsafe_allow_html=True)
        with v_cols[1]:
            st.plotly_chart(create_balanced_gauge(s_nice, "NICE Score", n_color), use_container_width=True, config={'displayModeBar': False})
            st.markdown(f"<div style='text-align:center; padding:5px; background-color:{n_color}; color:white; border-radius:5px; font-size:0.9em; margin-top:-20px;'><b>NICE: {n_grade}</b></div>", unsafe_allow_html=True)

    # --- 4. 매출 및 기대출 (하단 유지) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("4. 매출 및 기대출 정보")
    c4_cols = st.columns(4)
    with c4_cols[0]: st.number_input("금년 매출(만)", value=0, key="in_sales_cur")
    with c4_cols[1]: st.number_input("24년 매출(만)", value=0, key="in_sales_24")
    with c4_cols[2]: st.number_input("중진공 기대출(만)", value=0, key="in_debt_kosme")
    with c4_cols[3]: st.number_input("필요자금(만)", value=0, key="in_req_amount")

    st.success("✅ 모든 대시보드 레이아웃 복구 및 정렬이 완료되었습니다.")

# ==========================================
# 4. 리포트 출력 화면
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
        with st.status("🚀데이터 분석 중..."):
            pr = f"{cn} 기업분석 HTML. 최상단에 기업현황표(사업자:{d.get('in_raw_biz_no')}, 대표:{d.get('in_rep_name')}) 포함 리포트."
            res = clean_html(model.generate_content(pr).text)
        st.markdown(res, unsafe_allow_html=True)
