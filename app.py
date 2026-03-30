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
# 0. 핵심 설정 및 데이터 보존 (Data Safeguard)
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
    return "\n".join([l.lstrip() for l in text.replace("```html", "").replace("```", "").strip().split("\n")])

def get_best_model_name():
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        if 'models/gemini-1.5-flash' in available: return 'models/gemini-1.5-flash'
        return 'models/gemini-pro'
    except: return 'models/gemini-1.5-flash'

# --- 탭 이동 시 데이터 보존 로직 ---
if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"

def change_mode(target):
    # 현재 화면의 모든 입력값을 백업 저장소로 복사하여 휘발 방지
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
# 2. 사이드바 및 업체 관리
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
if st.sidebar.button("📊 AI기업분석리포트 생성", key="side_1", use_container_width=True): change_mode("REPORT")
if st.sidebar.button("💡 AI 정책자금 매칭리포트", key="side_2", use_container_width=True): change_mode("MATCHING")
if st.sidebar.button("📝 기관별 융자/사업계획서", key="side_3", use_container_width=True): change_mode("PLAN")

# ==========================================
# 3. 메인 상단 탭 (Persistence 유지)
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

# ==========================================
# 4. 모드별 렌더링 (입력 및 출력)
# ==========================================
if st.session_state["view_mode"] == "INPUT":
    # --- 1. 기업현황 (순서 조정 단계) ---
    st.header("1. 기업현황")
    
    # 1행: 기업명 -> 사업자유형 -> 사업자번호 -> 법인번호
    c1_r1, c1_r2, c1_r3, c1_r4 = st.columns([2, 1, 1.5, 1.5])
    with c1_r1: st.text_input("기업명", key="in_company_name")
    with c1_r2: biz_type = st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
    with c1_r3: st.text_input("사업자번호", key="in_raw_biz_no", on_change=lambda: st.session_state.update({"in_raw_biz_no": format_biz_no(st.session_state.in_raw_biz_no)}))
    with c1_r4: 
        if biz_type == "법인":
            st.text_input("법인등록번호", key="in_raw_corp_no", on_change=lambda: st.session_state.update({"in_raw_corp_no": format_corp_no(st.session_state.in_raw_corp_no)}))
        else: st.empty()

    # 2행: 사업개시일 -> 사업장 주소 -> 업종
    c2_r1, c2_r2, c2_r3 = st.columns([1, 2, 1])
    with c2_r1: st.text_input("사업개시일", placeholder="YYYY.MM.DD", key="in_start_date")
    with c2_r2: st.text_input("사업장 주소", key="in_biz_addr")
    with c2_r3: st.selectbox("업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")

    # 3행: 전화번호 -> 사업장 임대여부 -> 추가사업장현황
    c3_r1, c3_r2, c3_r3 = st.columns(3)
    with c3_r1: st.text_input("전화번호", key="in_biz_tel")
    with c3_r2: st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
    with c3_r3: 
        has_add = st.radio("추가사업장현황", ["무", "유"], horizontal=True, key="in_has_additional_biz")
        if has_add == "유": st.text_input("추가 사업장 정보", key="in_additional_biz_addr")

    # 4행: 상시근로자수
    st.number_input("상시근로자수(명)", value=0, step=1, key="in_employee_count")

    # --- 나머지 섹션 (유지) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("2. 대표자 정보")
    r2c1, r2c2, r2c3 = st.columns(3)
    with r2c1: st.text_input("대표자명", key="in_rep_name"); st.number_input("NICE 점수", value=0, key="in_nice")
    with r2c2: st.number_input("금년 매출(만)", value=0, key="in_sales_cur"); st.number_input("25년 매출(만)", value=0, key="in_sales_25")
    with r2c3: st.number_input("중진공 기대출(만)", value=0, key="in_debt_kosme"); st.number_input("소진공 기대출(만)", value=0, key="in_debt_semas")

    st.header("3. 필요자금 및 인증")
    r3c1, r3c2 = st.columns(2)
    with r3c1:
        p1, p2 = st.columns(2)
        with p1: st.selectbox("자금구분", ["운전자금", "시설자금"], key="in_fund_type")
        with p2: st.number_input("금액(만원)", value=0, key="in_req_amount")
        st.text_input("자금용도", key="in_fund_purpose")
    with r3c2:
        st.markdown("**보유 인증 (4열 배치)**")
        cert_list = ["소상공인", "창업기업", "여성기업", "이노비즈", "벤처인증", "뿌리기업", "ISO인증", "HACCP"]
        for i in range(0, len(cert_list), 4):
            cols = st.columns(4)
            for j in range(4):
                if i+j < len(cert_list): cols[j].checkbox(cert_list[i+j], key=f"in_cert_{cert_list[i+j]}")

    st.header("4. 특허 및 비즈니스 정보")
    if st.radio("특허보유", ["무", "유"], horizontal=True, key="in_has_patent") == "유":
        st.text_area("특허 상세 내용", key="in_pat_desc")
    st.text_area("핵심 아이템 상세", key="in_item_desc")
    st.text_area("차별화 포인트 및 계획", key="in_future_plan")
    st.success("✅ 기업현황 설정 완료! 상단 리포트 버튼을 클릭하세요.")

# ---------------------------------------------------------
# [리포트 출력 파트]
# ---------------------------------------------------------
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
        with st.status("🚀기업분석리포트는 생성중입니다"):
            # 입력 순서가 변경된 기업현황 데이터를 표로 구성
            pr = f"""전문 컨설턴트. {cn} 분석 리포트 HTML 작성. 
            최상단에 <table border='1' width='100%'>
            <tr><th>항목</th><th colspan='3'>내용</th></tr>
            <tr><td>기업명</td><td colspan='3'>{cn}</td></tr>
            <tr><td>사업자번호</td><td>{d.get('in_raw_biz_no','')}</td><td>법인번호</td><td>{d.get('in_raw_corp_no','-')}</td></tr>
            <tr><td>사업장주소</td><td colspan='3'>{d.get('in_biz_addr','')}</td></tr>
            <tr><td>업종</td><td>{d.get('in_industry','')}</td><td>유형</td><td>{d.get('in_biz_type','')}</td></tr>
            </table> 포함. 매출 전망(1/3/5년) 및 아이템 분석."""
            res = clean_html(model.generate_content(pr).text)
        st.markdown(res, unsafe_allow_html=True)

    elif st.session_state["view_mode"] == "MATCHING":
        st.subheader(f"💡 AI 정책자금 매칭리포트: {cn}")
        with st.status("🚀정책자금 심사 중..."):
            pr = f"{cn} 매칭 리포트 HTML. 매출/기대출 요약표 포함. 중진공/소진공 위주 전략 수립."
            res = clean_html(model.generate_content(pr).text)
        st.markdown(res, unsafe_allow_html=True)

    elif st.session_state["view_mode"] == "PLAN":
        st.subheader("📝 기관별 서식 자동 생성")
        tabs = st.tabs(["중소벤처기업진흥공단", "소상공인시장진흥공단"])
        with tabs[0]: st.info("자금을 선택하고 생성을 눌러주세요.")
        with tabs[1]: st.info("소진공 서식 생성 대기 중")
