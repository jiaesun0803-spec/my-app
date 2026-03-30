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
    return "\n".join([l.lstrip() for l in text.replace("```html", "").replace("```", "").strip().split("\n")])

def get_best_model_name():
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # models/ 접두사가 포함된 명칭을 그대로 사용하여 NotFound 에러 방지
        if 'models/gemini-1.5-flash' in available: return 'models/gemini-1.5-flash'
        if 'models/gemini-1.5-pro' in available: return 'models/gemini-1.5-pro'
        if 'models/gemini-pro' in available: return 'models/gemini-pro'
        return available[0] if available else 'models/gemini-1.5-flash'
    except: return 'models/gemini-1.5-flash'

# --- 탭 이동 시 데이터 보존 및 복원 함수 ---
if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"

def change_mode(target):
    # 현재 입력된 모든 데이터를 shadow dictionary에 복사하여 보존
    current_inputs = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
    st.session_state["permanent_data"] = current_inputs
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
# 2. 사이드바 (업체 관리)
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
if st.sidebar.button("💾 현재 정보 저장", use_container_width=True):
    cn = st.session_state.get("in_company_name", "").strip()
    if cn:
        db[cn] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        save_db(db); st.sidebar.success(f"✅ '{cn}' 저장 완료!")

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

st.sidebar.markdown("---")
st.sidebar.header("🚀 빠른 리포트 생성")
if st.sidebar.button("📊 AI기업분석리포트", key="side_1", use_container_width=True): change_mode("REPORT")
if st.sidebar.button("💡 AI 정책자금 매칭리포트", key="side_2", use_container_width=True): change_mode("MATCHING")
if st.sidebar.button("📝 기관별 융자/사업계획서", key="side_3", use_container_width=True): change_mode("PLAN")

# ==========================================
# 3. 메인 상단 탭
# ==========================================
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
st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

# ==========================================
# 4. 입력 화면 (대시보드)
# ==========================================
if st.session_state["view_mode"] == "INPUT":
    st.header("1. 기업현황")
    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        st.text_input("기업명", key="in_company_name")
        st.text_input("사업자번호", key="in_raw_biz_no", on_change=lambda: st.session_state.update({"in_raw_biz_no": format_biz_no(st.session_state.in_raw_biz_no)}))
        biz_type = st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
        if biz_type == "법인": st.text_input("법인등록번호", key="in_raw_corp_no", on_change=lambda: st.session_state.update({"in_raw_corp_no": format_corp_no(st.session_state.in_raw_corp_no)}))
    with r1c2:
        st.text_input("사업개시일", placeholder="YYYY.MM.DD", key="in_start_date")
        st.selectbox("업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")
        st.number_input("상시근로자수(명)", value=0, step=1, key="in_employee_count")
    with r1c3:
        st.text_input("전화번호", key="in_biz_tel")
        st.text_input("사업장 주소", key="in_biz_addr")

    st.header("2. 대표자 및 신용 정보")
    r2c1, r2c2 = st.columns(2)
    with r2c1:
        st.text_input("대표자명", key="in_rep_name")
        st.number_input("NICE 점수", value=0, key="in_nice")
    with r2c2:
        m_c1, m_c2 = st.columns(2)
        with m_c1: st.number_input("금년 매출(만)", value=0, key="in_sales_cur"); st.number_input("25년 매출(만)", value=0, key="in_sales_25")
        with m_c2: st.number_input("24년 매출(만)", value=0, key="in_sales_24"); st.number_input("23년 매출(만)", value=0, key="in_sales_23")

    st.header("3. 기대출 및 필요자금")
    d1, d2, d3, d4 = st.columns(4)
    with d1: st.number_input("중진공(만)", value=0, key="in_debt_kosme")
    with d2: st.number_input("소진공(만)", value=0, key="in_debt_semas")
    with d3: st.number_input("신보/기보(만)", value=0, key="in_debt_guarantee")
    with d4: st.number_input("필요금액(만)", value=0, key="in_req_amount")

    # [수정] 6. 보유인증 4개씩 배치
    st.header("6. 보유 인증")
    cert_list = ["소상공인확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
    for i in range(0, len(cert_list), 4):
        cols = st.columns(4)
        for j in range(4):
            if i + j < len(cert_list):
                c_name = cert_list[i + j]
                cols[j].checkbox(c_name, key=f"in_cert_{c_name}")

    # [수정] 7. 특허 및 8. 정부지원 한 줄 배치
    st.header("7. 특허 및 8. 정부지원")
    c7, c8 = st.columns(2)
    with c7:
        if st.radio("특허 보유여부", ["무", "유"], horizontal=True, key="in_has_patent") == "유":
            st.number_input("보유 건수", value=0, key="in_pat_cnt")
            st.text_area("특허 번호/내용", key="in_pat_desc")
    with c8:
        if st.radio("정부지원 수혜이력", ["무", "유"], horizontal=True, key="in_has_gov") == "유":
            st.number_input("수혜 건수", value=0, key="in_gov_cnt")
            st.text_area("지원사업명", key="in_gov_desc")

    st.header("9. 비즈니스 상세 정보")
    st.text_area("핵심 아이템", key="in_item_desc")
    st.text_input("제품 생산 공정도", key="in_process_desc")
    st.text_area("판매루트 및 차별화", key="in_sales_route")
    st.text_area("시장 현황 및 앞으로의 계획", key="in_future_plan")
    st.success("✅ 대시보드 준비 완료! 상단 탭을 눌러 리포트를 생성하세요.")

# ==========================================
# 5. 리포트 출력 화면
# ==========================================
else:
    if st.button("⬅️ 입력 화면으로 돌아가기"):
        # 보존된 데이터를 다시 세션에 로드 (데이터 복구)
        if "permanent_data" in st.session_state:
            for k, v in st.session_state["permanent_data"].items(): st.session_state[k] = v
        st.session_state["view_mode"] = "INPUT"; st.rerun()

    d = st.session_state.get("permanent_data", {})
    cn = d.get('in_company_name', '미입력').strip()
    model = genai.GenerativeModel(get_best_model_name())

    if st.session_state["view_mode"] == "REPORT":
        st.subheader(f"📊 AI기업분석리포트: {cn}")
        # 매출 그래프 생성 로직
        val_cur = safe_int(d.get('in_sales_cur', 0))
        if val_cur <= 0: val_cur = 1000
        start_val = val_cur / 12
        monthly_vals = [int(start_val * (1 + 0.05*i + 0.1*np.sin(i/2))) for i in range(12)]
        fig = go.Figure(go.Scatter(x=[f"{i}월" for i in range(1, 13)], y=monthly_vals, mode='lines+markers+text', text=[format_kr_currency(v) for v in monthly_vals], line=dict(color='#1E88E5', width=4)))
        fig.update_layout(title="📈 향후 1년 월별 매출 추이 전망", template="plotly_white")
        plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn')

        if "generated_report" not in st.session_state:
            with st.status("🚀기업분석리포트는 생성중입니다"):
                pr = f"""전문 컨설턴트로서 {cn} 리포트를 HTML로 작성하세요. 
                최상단에 <table border='1' width='100%'><tr><th>기업명</th><td>{cn}</td></tr><tr><td>사업자/법인번호</td><td>{d.get('in_raw_biz_no','')}({d.get('in_raw_corp_no','')})</td></tr><tr><td>업종</td><td>{d.get('in_industry','')}</td></tr><tr><td>주소</td><td>{d.get('in_biz_addr','')}</td></tr></table>를 포함하세요.
                매출 전망은 단기(1년), 중기(3년), 장기(5년)로 상세 서술하고 중간에 [GRAPH_POINT]를 넣으세요."""
                st.session_state["generated_report"] = clean_html(model.generate_content(pr).text)
        
        res = st.session_state["generated_report"]
        st.markdown(res.replace("[GRAPH_POINT]", ""), unsafe_allow_html=True); st.plotly_chart(fig, use_container_width=True)
        st.download_button("📥 리포트 다운로드(HTML)", f"<!DOCTYPE html><html><body>{res.replace('[GRAPH_POINT]', plotly_html)}</body></html>", f"{cn}_분석.html", "text/html")

    elif st.session_state["view_mode"] == "MATCHING":
        st.subheader(f"💡 AI 정책자금 매칭리포트: {cn}")
        with st.status("🚀전년도 매출 기준으로 심사를 진행 중입니다"):
            cur_sales = safe_int(d.get('in_sales_cur', 0))
            tot_debt = sum([safe_int(d.get(k, 0)) for k in ['in_debt_kosme', 'in_debt_semas', 'in_debt_guarantee']])
            is_mfg = (d.get('in_industry') == "제조업" or safe_int(d.get('in_employee_count')) >= 5 or cur_sales >= 500000)
            ranking = "제조/대규모형(1:중진공+소진공, 2:기보/신보, 3:지역신보, 4:은행)" if is_mfg else "일반소상공인형(1:소진공, 2:신보, 3:지역신보, 4:은행)"
            pr = f"""{cn} 매칭 리포트. HTML 작성. 기업현황표(매출:{format_kr_currency(cur_sales)}, 기대출:{format_kr_currency(tot_debt)}) 요약 포함.
            추천순위: {ranking} 적용. 1순위:Green, 2순위:Blue, 3순위:Orange, 4순위:Red 테두리 박스 사용."""
            st.session_state["generated_matching"] = clean_html(model.generate_content(pr).text)
        st.markdown(st.session_state["generated_matching"], unsafe_allow_html=True)
        st.download_button("📥 매칭리포트 다운로드(HTML)", st.session_state["generated_matching"], f"{cn}_매칭.html", "text/html")

    elif st.session_state["view_mode"] == "PLAN":
        st.subheader("📝 기관별 융자/사업계획서 자동 생성")
        tabs = st.tabs(["중소벤처기업진흥공단", "소상공인시장진흥공단"])
        with tabs[0]:
            k_cats = {"혁신창업": ["청년전용창업자금", "개발기술사업화자금"], "신시장": ["수출기업화자금"], "신성장": ["혁신성장자금"]}
            mk = st.selectbox("대분류", list(k_cats.keys())); sk = st.selectbox("세부자금", k_cats[mk])
            if st.button(f"🚀 {cn} 중진공 {sk} 서식 생성"):
                with st.status("서식 작성 중..."):
                    pr = f"<h2 style='text-align:center;'>{cn} 중진공 {sk} 융자신청서 및 사업계획서</h2> 내용을 HTML 표로만 상세히 작성."
                    st.session_state["kosme_html"] = clean_html(model.generate_content(pr).text)
            if "kosme_html" in st.session_state: st.markdown(st.session_state["kosme_html"], unsafe_allow_html=True)
        with tabs[1]:
            s_cats = ["혁신성장촉진", "상생성장지원", "재도전특별", "일시적경영애로"]
            sk_s = st.selectbox("소진공 자금종류", s_cats)
            if st.button(f"🚀 {cn} 소진공 {sk_s} 서식 생성"):
                with st.status("서식 작성 중..."):
                    pr = f"{cn} 소상공인 {sk_s} 신청용 사업계획서 HTML 작성."
                    st.session_state["semas_html"] = clean_html(model.generate_content(pr).text)
            if "semas_html" in st.session_state: st.markdown(st.session_state["semas_html"], unsafe_allow_html=True)
