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

# --- 신용 등급 판정 로직 (유지) ---
def get_kcb_info(score):
    s = safe_int(score)
    if s >= 942: return "1등급", "#1E88E5" # 파랑
    if s >= 891: return "2등급", "#1E88E5"
    if s >= 832: return "3등급", "#43A047" # 초록
    if s >= 768: return "4등급", "#43A047"
    if s >= 698: return "5등급", "#FB8C00" # 주황
    if s >= 630: return "6등급", "#FB8C00"
    if s >= 530: return "7등급", "#E53935" # 빨강
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

# --- [수정] 게이지 그래프 생성 함수 (크기 축소) ---
def create_small_gauge(score, title, color):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = score,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 14}}, # 폰트 크기 축소
        gauge = {
            'axis': {'range': [None, 1000], 'tickwidth': 1, 'tickcolor': "darkblue", 'tickfont': {'size': 10}},
            'bar': {'color': color},
            'bgcolor': "white",
            'borderwidth': 1,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 500], 'color': '#FFEBEE'},
                {'range': [500, 800], 'color': '#FFF3E0'},
                {'range': [800, 1000], 'color': '#E8F5E9'}],
        }
    ))
    # [핵심수정] 높이를 160으로 줄이고, 마진을 최소화하여 꽉 차게 배치
    fig.update_layout(height=160, margin=dict(l=10, r=10, t=30, b=10))
    return fig

# --- 탭 이동 데이터 보존 ---
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
# 2. 메인 대시보드
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
    # --- 1. 기업현황 & 2. 대표자 정보 (유지) ---
    # (생략: 이전 코드와 동일)

    # --- [수정] 3. 신용 정보 시각화 (크기 축소 적용) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("3. 신용 정보 시각화")
    
    # 비율 조정: 입력을 조금 더 넓게, 시각화를 조금 더 좁게 하여 균형 확보
    credit_input_col, credit_viz_col = st.columns([1.3, 1])
    
    with credit_input_col:
        st.markdown("**신용 상태 입력**")
        c_r1_1, c_r1_2 = st.columns(2)
        with c_r1_1: delinquency = st.radio("금융연체 여부", ["무", "유"], horizontal=True, key="in_fin_delinquency")
        with c_r1_2: tax_delin = st.radio("세금체납 여부", ["무", "유"], horizontal=True, key="in_tax_delinquency")
        
        c_r2_1, c_r2_2 = st.columns(2)
        with c_r2_1: s_kcb = st.number_input("KCB 점수", value=0, max_value=1000, step=1, key="in_kcb_score")
        with c_r2_2: s_nice = st.number_input("NICE 점수", value=0, max_value=1000, step=1, key="in_nice_score")
        
    with credit_viz_col:
        # 상태 경고창 (내용 유지)
        if delinquency == "유" or tax_delin == "유":
            st.error("🚨 **연체/체납 주의:** 자금 신청 시 제한이 있을 수 있습니다.")
        else:
            st.success("✅ **신용 양호:** 현재 연체 및 체납 내역이 없습니다.")
        
        v_k1, v_k2 = st.columns(2)
        k_grade, k_color = get_kcb_info(s_kcb)
        n_grade, n_color = get_nice_info(s_nice)
        
        with v_k1:
            # 축소된 게이지 그래프 호출
            st.plotly_chart(create_small_gauge(s_kcb, "KCB Score", k_color), use_container_width=True, config={'displayModeBar': False})
            st.markdown(f"<div style='text-align:center; padding:3px; background-color:{k_color}; color:white; border-radius:3px; font-size:0.85em;'><b>KCB: {k_grade}</b></div>", unsafe_allow_html=True)
        with v_k2:
            st.plotly_chart(create_small_gauge(s_nice, "NICE Score", n_color), use_container_width=True, config={'displayModeBar': False})
            st.markdown(f"<div style='text-align:center; padding:3px; background-color:{n_color}; color:white; border-radius:3px; font-size:0.85em;'><b>NICE: {n_grade}</b></div>", unsafe_allow_html=True)

    # --- 나머지 정보 유지 ---
    # (생략: 이전 코드와 동일)

    st.success("✅ 신용 시각화 정렬 완료! 상단 버튼을 클릭하세요.")

# ==========================================
# 5. 리포트 출력 (생략)
# ==========================================
