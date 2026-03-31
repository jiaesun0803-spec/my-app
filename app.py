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
# 0. 핵심 설정 및 데이터 세이프가드 (Data Safeguard)
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

# --- 신용 등급 판정 로직 ---
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

# --- 게이지 그래프 생성 (여백 및 높이 튜닝) ---
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
    # 상단 글자 잘림 방지를 위해 마진 t=60 확보
    fig.update_layout(height=190, margin=dict(l=15, r=15, t=60, b=10), paper_bgcolor="rgba(0,0,0,0)")
    return fig

# --- 탭 이동 데이터 보존 로직 ---
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
# 2. 사이드바 관리 (복구 완료)
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
if st.sidebar.button("💾 현재 업체 정보 저장", use_container_width=True):
    cn = st.session_state.get("in_company_name", "").strip()
    if cn:
        db[cn] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        save_db(db); st.sidebar.success(f"✅ 저장 완료!")

selected_company = st.sidebar.selectbox("저장된 업체 목록", ["선택 안 함"] + list(db.keys()))
c_s1, c_s2 = st.sidebar.columns(2)
with c_s1:
    if st.button("📂 불러오기", use_container_width=True) and selected_company != "선택 안 함":
        for k, v in db[selected_company].items(): st.session_state[k] = v
        st.session_state["view_mode"] = "INPUT"; st.rerun()
with c_s2:
    if st.button("🔄 초기화", use_container_width=True):
        for k in [k for k in st.session_state.keys() if k.startswith("in_")]: del st.session_state[k]
        st.session_state.pop("permanent_data", None); st.session_state["view_mode"] = "INPUT"; st.cache_data.clear(); st.rerun()

# [복구] 사이드바 빠른 이동 탭
st.sidebar.markdown("---")
st.sidebar.header("🚀 빠른 리포트 생성")
if st.sidebar.button("📊 AI기업분석리포트 생성", key="side_btn_1", use_container_width=True): change_mode("REPORT")
if st.sidebar.button("💡 AI 정책자금 매칭리포트", key="side_btn_2", use_container_width=True): change_mode("MATCHING")
if st.sidebar.button("📝 기관별 융자/사업계획서", key="side_btn_3", use_container_width=True): change_mode("PLAN")

# ==========================================
# 3. 메인 상단 UI
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
    # --- 1. 기업현황 (레이아웃 유지) ---
    st.header("1. 기업현황")
    c1r1, c1r2, c1r3, c1r4 = st.columns([2, 1, 1.5, 1.5])
    with c1r1: st.text_input("기업명", key="in_company_name")
    with c1r2: biz_type = st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
    with c1r3: st.text_input("사업자번호", placeholder="000-00-00000", key="in_raw_biz_no")
    with c1r4: 
        if biz_type == "법인": st.text_input("법인등록번호", placeholder="000000-0000000", key="in_raw_corp_no")

    # --- 2. 대표자 정보 (레이아웃 유지) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("2. 대표자 정보")
    c2r1_1, c2r1_2, c2r1_3, c2r1_4 = st.columns(4)
    with c2r1_1: st.text_input("대표자명", key="in_rep_name")
    with c2r1_2: st.text_input("생년월일", placeholder="YYYY.MM.DD", key="in_rep_dob")
    with c2r1_3: st.text_input("연락처", placeholder="010-0000-0000", key="in_rep_phone")
    with c2r1_4: st.selectbox("통신사", ["SKT", "KT", "LG U+", "알뜰폰"], key="in_rep_telecom")

    # --- 3. 신용 정보 시각화 (줄간격 및 높이 맞춤 튜닝) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("3. 신용 정보 시각화")
    
    credit_in, credit_out = st.columns([1.5, 1])
    
    with credit_in:
        # 좌측 상단 마진으로 시작
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        
        # 1행: 금융연체 - 세금체납 - 알림
        ci_r1 = st.columns([1, 1, 2.2])
        with ci_r1[0]: delinquency = st.radio("금융연체 여부", ["무", "유"], horizontal=True, key="in_fin_delinquency")
        with ci_r1[1]: tax_delin = st.radio("세금체납 여부", ["무", "유"], horizontal=True, key="in_tax_delinquency")
        with ci_r1[2]:
            if delinquency == "유" or tax_delin == "유":
                st.error("🚨 **연체/체납 주의:** 자금 신청 제한 가능성")
            else:
                st.success("✅ **신용 양호:** 특이사항 없음")

        # [핵심] 높이를 맞추기 위한 수직 스페이서 삽입
        st.markdown("<div style='margin-top: 45px;'></div>", unsafe_allow_html=True)

        # 2행: KCB 점수 - NICE 점수
        ci_r2 = st.columns(2)
        with ci_r2[0]: s_kcb = st.number_input("KCB 점수", value=0, max_value=1000, key="in_kcb_score")
        with ci_r2[1]: s_nice = st.number_input("NICE 점수", value=0, max_value=1000, key="in_nice_score")
        
    with credit_out:
        # 우측 게이지 영역
        v_cols = st.columns(2)
        k_grade, k_color = get_kcb_info(s_kcb)
        n_grade, n_color = get_nice_info(s_nice)
        
        with v_cols[0]:
            st.plotly_chart(create_balanced_gauge(s_kcb, "KCB Score", k_color), use_container_width=True, config={'displayModeBar': False})
            st.markdown(f"<div style='text-align:center; padding:5px; background-color:{k_color}; color:white; border-radius:5px; font-size:0.9em; margin-top:-15px;'><b>KCB: {k_grade}</b></div>", unsafe_allow_html=True)
        with v_cols[1]:
            st.plotly_chart(create_balanced_gauge(s_nice, "NICE Score", n_color), use_container_width=True, config={'displayModeBar': False})
            st.markdown(f"<div style='text-align:center; padding:5px; background-color:{n_color}; color:white; border-radius:5px; font-size:0.9em; margin-top:-15px;'><b>NICE: {n_grade}</b></div>", unsafe_allow_html=True)

    # --- 4. 매출 및 기대출 (하단 배치 유지) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("4. 매출 및 기대출 정보")
    c4r1_1, c4r1_2, c4r1_3, c4r1_4 = st.columns(4)
    with c4r1_1: st.number_input("금년 매출(만)", value=0, key="in_sales_cur")
    with c4r1_2: st.number_input("24년 매출(만)", value=0, key="in_sales_24")
    with c4r1_3: st.number_input("중진공 기대출(만)", value=0, key="in_debt_kosme")
    with c4r1_4: st.number_input("필요자금(만)", value=0, key="in_req_amount")

    st.success("✅ 대시보드 정렬 및 사이드바 복구가 완료되었습니다.")

# ==========================================
# 5. 리포트 출력 화면 (데이터 연동 확인)
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
            k_grade, _ = get_kcb_info(d.get('in_kcb_score', 0))
            pr = f"{cn} 기업분석 HTML. 대표자:{d.get('in_rep_name')}, 신용상태(KCB:{k_grade}) 반영 리포트."
            res = clean_html(model.generate_content(pr).text)
        st.markdown(res, unsafe_allow_html=True)
