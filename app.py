import streamlit as st
import json
import os
import time
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go

# ==========================================
# 0. 디자인 커스텀 (CSS)
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

st.markdown("""
<style>
    [data-testid="stWidgetLabel"] p { font-weight: 400 !important; font-size: 14px !important; color: #31333F !important; margin-bottom: 5px !important; }
    h2 { font-weight: 700 !important; margin-top: 25px !important; }
    input::placeholder { font-size: 0.8em !important; color: #888 !important; }
    input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    [data-testid="stCheckbox"] label p { font-size: 15px !important; font-weight: 450 !important; }
    .blue-bold-label-16 { color: #1E88E5 !important; font-size: 16px !important; font-weight: 700 !important; display: inline-block; margin-bottom: 12px !important; }
    .std-label-14 { font-size: 14px !important; font-weight: 400 !important; display: inline-block; margin-bottom: 12px !important; }
</style>
""", unsafe_allow_html=True)

# --- 헬퍼 함수 ---
def safe_int(value):
    try:
        if value is None or value == "": return 0
        return int(float(str(value).replace(',', '').strip()))
    except: return 0

def get_best_model_name(): return 'gemini-1.5-flash'

def get_kcb_info(score):
    s = safe_int(score)
    if s >= 942: return "1등급", "#43A047"
    elif s >= 832: return "3등급", "#43A047"
    elif s >= 630: return "6등급", "#FB8C00"
    else: return "저신용", "#E53935"

def get_nice_info(score):
    s = safe_int(score)
    if s >= 900: return "1등급", "#1E88E5"
    elif s >= 840: return "3등급", "#43A047"
    elif s >= 665: return "6등급", "#FB8C00"
    else: return "저신용", "#E53935"

def create_gauge(score, title, color):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number", value = safe_int(score),
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 14}},
        gauge = {
            'axis': {'range': [None, 1000]}, 'bar': {'color': color},
            'bgcolor': "white", 'borderwidth': 1,
            'steps': [{'range': [0, 600], 'color': '#FFEBEE'}, {'range': [600, 850], 'color': '#FFF3E0'}, {'range': [850, 1000], 'color': '#E8F5E9'}],
        }
    ))
    fig.update_layout(height=165, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)")
    return fig

# ==========================================
# 1. 상태 관리 및 사이드바 (업체 목록 보존)
# ==========================================
DB_FILE = "company_db.json"
def load_db(): return json.load(open(DB_FILE, "r", encoding="utf-8")) if os.path.exists(DB_FILE) else {}
def save_db(data): json.dump(data, open(DB_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)

# 초기 세션 설정
if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
if "api_key" not in st.session_state: st.session_state["api_key"] = ""
if "form_id" not in st.session_state: st.session_state["form_id"] = 0

st.sidebar.header("⚙️ AI 엔진 설정")
api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")
if st.sidebar.button("💾 API KEY 저장"):
    st.session_state["api_key"] = api_key_input
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("📂 업체 관리")
db = load_db()
company_list = ["선택 안 함"] + list(db.keys())
selected_company = st.sidebar.selectbox("불러올 업체 선택", company_list)

col_s1, col_s2 = st.sidebar.columns(2)
with col_s1:
    if st.button("📂 불러오기", use_container_width=True):
        if selected_company != "선택 안 함":
            # DB 데이터를 현재 세션(in_...)으로 복사
            company_data = db[selected_company]
            for k, v in company_data.items():
                st.session_state[k] = v
            st.rerun()
with col_s2:
    if st.button("💾 정보 저장", use_container_width=True):
        name = st.session_state.get("in_company_name", "").strip()
        if name:
            # 현재 입력된 in_ 데이터만 필터링하여 저장
            current_data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            db[name] = current_data
            save_db(db); st.sidebar.success("저장 완료!")

st.sidebar.markdown("---")
# [초기화] API KEY와 DB는 남기고 대시보드 입력값(in_)만 싹 비움
if st.sidebar.button("🧹 전체 데이터 초기화", use_container_width=True):
    for k in list(st.session_state.keys()):
        if k.startswith("in_"): del st.session_state[k]
    # 위젯 잔상 제거를 위해 ID 변경
    st.session_state["form_id"] += 1
    st.rerun()

# ==========================================
# 2. 메인 대시보드 (입력창 리셋 가능 구조)
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

# 위젯 고유 키 생성을 위한 ID
fid = st.session_state["form_id"]
GUIDE_STR = "1억=10000으로 입력"

if st.session_state["view_mode"] == "INPUT":
    # --- 1. 기업현황 ---
    st.header("1. 기업현황")
    c1r1 = st.columns([2, 1, 1.5, 1.5])
    with c1r1[0]: st.text_input("기업명", key="in_company_name")
    with c1r1[1]: st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
    with c1r1[2]: st.text_input("사업자번호", placeholder="000-00-00000", key="in_raw_biz_no")
    with c1r1[3]: st.text_input("법인등록번호", placeholder="000000-0000000", key="in_raw_corp_no")

    c1r2 = st.columns([1, 2, 1])
    with c1r2[0]: st.text_input("사업개시일", placeholder="YYYY.MM.DD", key="in_start_date")
    with c1r2[1]: st.text_input("사업장 주소", key="in_biz_addr")
    with c1r2[2]: st.selectbox("업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")

    c1r3 = st.columns([1, 1, 1, 1])
    with c1r3[0]: st.text_input("사업장 전화번호", placeholder="000-0000-0000", key="in_biz_tel")
    with c1r3[1]: st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
    with c1r3[2]: st.number_input("보증금 (만원)", value=st.session_state.get("in_lease_deposit", None), key="in_lease_deposit", placeholder=GUIDE_STR, step=1, format="%d")
    with c1r3[3]: st.number_input("월임대료 (만원)", value=st.session_state.get("in_lease_rent", None), key="in_lease_rent", placeholder=GUIDE_STR, step=1, format="%d")
    st.markdown("---")

    # --- 2. 대표자 정보 ---
    st.header("2. 대표자 정보")
    c2r1 = st.columns(4)
    with c2r1[0]: st.text_input("대표자명", key="in_rep_name")
    with c2r1[1]: st.text_input("생년월일", placeholder="YYYY.MM.DD", key="in_rep_dob")
    with c2r1[2]: st.text_input("연락처", placeholder="010-0000-0000", key="in_rep_phone")
    with c2r1[3]: st.selectbox("최종학력", ["선택", "중학교 졸업", "고등학교 졸업", "대학교 졸업", "석사 수료", "박사 수료"], key="in_edu_school")
    st.markdown("---")

    # --- 3. 대표자 신용정보 ---
    st.header("3. 대표자 신용정보")
    c3_col1, c3_col2, c3_col3 = st.columns([1.1, 1.2, 1.8])
    with c3_col1:
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        t_c = st.columns(2); t_c[0].markdown("금융연체 여부"); t_c[1].markdown("세금체납 여부")
        r_c = st.columns(2)
        delinquency = r_c[0].radio("f_d", ["무", "유"], horizontal=True, key="in_fin_delinquency", label_visibility="collapsed")
        tax_delin = r_c[1].radio("t_d", ["무", "유"], horizontal=True, key="in_tax_delinquency", label_visibility="collapsed")
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        s_c = st.columns(2); s_c[0].markdown("KCB 점수"); s_c[1].markdown("NICE 점수")
        r2_c = st.columns(2)
        s_kcb = r2_c[0].number_input("k_i", value=st.session_state.get("in_kcb_score", None), key="in_kcb_score", label_visibility="collapsed", placeholder="점수", step=1)
        s_nice = r2_c[1].number_input("n_i", value=st.session_state.get("in_nice_score", None), key="in_nice_score", label_visibility="collapsed", placeholder="점수", step=1)
    with c3_col2:
        st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
        vk, vn = safe_int(s_kcb), safe_int(s_nice)
        has_issue = (delinquency == "유" or tax_delin == "유")
        low_score = (vk > 0 and vk < 630) or (vn > 0 and vn < 665)
        if has_issue: status, color, text = "🔴 진행 불가", "#FFEBEE", "연체 또는 체납 정보가 있습니다."
        elif low_score: status, color, text = "🟡 진행 주의", "#FFF3E0", "신용 점수가 낮아 한도가 제한될 수 있습니다."
        elif vk == 0: status, color, text = "⚪ 대기 중", "#F8F9FA", "신용 정보를 입력해 주세요."
        else: status, color, text = "🟢 진행 원활", "#E8F5E9", "양호한 신용 상태입니다."
        st.markdown(f"<div style='background-color:{color}; padding:20px; border-radius:10px; height:185px;'><p style='font-weight:700;'>금융 상태 요약</p><p style='font-size:1.2em; font-weight:700;'>{status}</p><p>{text}</p></div>", unsafe_allow_html=True)
    with c3_col3:
        v_cols = st.columns(2); kg, kc = get_kcb_info(vk); ng, nc = get_nice_info(vn)
        with v_cols[0]: 
            st.plotly_chart(create_gauge(vk, "KCB", kc), use_container_width=True, config={'displayModeBar': False})
            st.markdown(f"<div style='text-align:center; margin-top:-20px; color:{kc}; font-weight:700;'>{kg}</div>", unsafe_allow_html=True)
        with v_cols[1]: 
            st.plotly_chart(create_gauge(vn, "NICE", nc), use_container_width=True, config={'displayModeBar': False})
            st.markdown(f"<div style='text-align:center; margin-top:-20px; color:{nc}; font-weight:700;'>{ng}</div>", unsafe_allow_html=True)
    st.markdown("---")

    # --- 4. 매출현황 ---
    st.header("4. 매출현황")
    exp_r = st.columns([1, 1, 2])
    with exp_r[0]: has_exp = st.radio("수출매출 여부", ["무", "유"], horizontal=True, key="in_export_revenue")
    with exp_r[1]: plan_exp = st.radio("수출예정 여부", ["무", "유"], horizontal=True, key="in_planned_export")
    mc = st.columns(4)
    m_keys = [("금년 매출", "in_sales_cur"), ("25년 매출", "in_sales_25"), ("24년 매출", "in_sales_24"), ("23년 매출", "in_sales_23")]
    for i, (t, k) in enumerate(m_keys):
        mc[i].number_input(f"{t} (만원)", value=st.session_state.get(k, None), key=k, placeholder=GUIDE_STR, step=1)
    if has_exp == "유":
        ec = st.columns(4)
        e_keys = [("금년 수출", "in_exp_cur"), ("25년 수출", "in_exp_25"), ("24년 수출", "in_exp_24"), ("23년 수출", "in_exp_23")]
        for i, (t, k) in enumerate(e_keys):
            ec[i].number_input(f"{t} (만원)", value=st.session_state.get(k, None), key=k, placeholder=GUIDE_STR, step=1)
    st.markdown("---")

    # --- 8. 비즈니스 상세 ---
    st.header("8. 비즈니스 상세 정보")
    r8_1 = st.columns(2)
    with r8_1[0]: st.text_area("핵심 아이템", key="in_item_desc", height=100)
    with r8_1[1]: st.text_area("판매 루트", key="in_sales_route", height=100)
    r8_2 = st.columns(2)
    with r8_2[0]: st.text_area("경쟁력/차별성", key="in_item_diff")
    with r8_2[1]: st.text_area("시장 현황", key="in_market_status")
    r8_3 = st.columns(2)
    with r8_3[0]: st.text_area("공정도", key="in_process_desc")
    with r8_3[1]: st.text_area("타겟 고객", key="in_target_cust")
    r8_4 = st.columns(2)
    with r8_4[0]: st.text_area("수익 모델", key="in_revenue_model")
    with r8_4[1]: st.text_area("앞으로의 계획", key="in_future_plan")
    st.markdown("---")

    # --- 9. 자금 계획 (정렬 완료) ---
    st.header("9. 자금 계획")
    c9 = st.columns([1, 2])
    with c9[0]:
        st.markdown('<p class="blue-bold-label-16">이번 조달 필요 자금 (만원)</p>', unsafe_allow_html=True)
        st.number_input("조달금액", value=st.session_state.get("in_req_funds", None), key="in_req_funds", placeholder=GUIDE_STR, step=1, label_visibility="collapsed")
    with c9[1]:
        st.markdown('<p class="std-label-14">상세 자금 집행 계획</p>', unsafe_allow_html=True)
        st.text_area("집행계획", key="in_fund_plan", placeholder="예: 연구인력 채용(40%) 등", label_visibility="collapsed")

# ==========================================
# 3. 리포트 (데이터 확인용)
# ==========================================
else:
    if st.button("⬅️ 입력 화면으로 돌아가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    st.subheader("📑 입력 정보 요약")
    data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
    st.json(data)
