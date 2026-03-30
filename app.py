import streamlit as st
import streamlit.components.v1 as components
import json
import os
import time
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go
from datetime import datetime

# ==========================================
# 0. 필수 유틸리티 및 AI 모델 설정 (에러 방지 최상단 배치)
# ==========================================
def safe_int(value):
    try: return int(float(str(value or "").replace(',', '').strip() or 0))
    except: return 0

def format_kr_currency(value):
    val = safe_int(value)
    if val == 0: return "0원"
    uk, man = val // 10000, val % 10000
    if uk > 0 and man > 0: return f"{uk}억 {man:,}만원"
    elif uk > 0: return f"{uk}억원"
    else: return f"{man:,}만원"

def clean_html(text): 
    return "\n".join([l.lstrip() for l in text.replace("```html", "").replace("```", "").strip().split("\n")])

# 에러의 원인이었던 모델명 획득 함수 정의
def get_best_model_name():
    try:
        # 가용한 모델 리스트 확인 및 최적 모델 반환
        av = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for pref in ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']:
            if pref in av: return pref
        return 'gemini-pro'
    except:
        return 'gemini-pro'

def get_credit_grade(sc, t="NICE"):
    sc = safe_int(sc)
    if sc == 0: return "-"
    if t == "NICE": return 1 if sc>=900 else 2 if sc>=870 else 3 if sc>=840 else 4 if sc>=805 else 5 if sc>=750 else 6 if sc>=665 else 7 if sc>=600 else 8 if sc>=515 else 9 if sc>=445 else 10
    else: return 1 if sc>=942 else 2 if sc>=891 else 3 if sc>=832 else 4 if sc>=768 else 5 if sc>=698 else 6 if sc>=630 else 7 if sc>=530 else 8 if sc>=454 else 9 if sc>=335 else 10

class VarObj: pass
def get_common_vars(d):
    v = VarObj()
    g = lambda k, df="": d.get(k, df)
    v.c_name = str(g('in_company_name')).strip()
    v.rep_name, v.biz_type, v.c_ind = g('in_rep_name'), g('in_biz_type'), g('in_industry')
    v.address, v.biz_no, v.corp_no = g('in_biz_addr'), str(g('in_raw_biz_no')), str(g('in_raw_corp_no'))
    v.s_25, v.s_cur = format_kr_currency(g('in_sales_2025', 0)), format_kr_currency(g('in_sales_current', 0))
    v.sales_24, v.sales_23 = format_kr_currency(g('in_sales_2024', 0)), format_kr_currency(g('in_sales_2023', 0))
    v.req_fund, v.fund_type, v.fund_purpose = format_kr_currency(g('in_req_amount', 0)), g('in_fund_type'), g('in_fund_purpose')
    v.item, v.market, v.diff = g('in_item_desc'), g('in_market_status'), g('in_diff_point')
    v.val_cur = safe_int(g('in_sales_current', 0))
    v.guarantee = "확인필요"
    v.tot_debt = format_kr_currency(sum([safe_int(g(k, 0)) for k in ['in_debt_kosme', 'in_debt_semas', 'in_debt_kodit', 'in_debt_kibo']]))
    return v

# ==========================================
# 1. 보안 및 DB 설정
# ==========================================
CONFIG_FILE = "config.json"
DB_FILE = "company_db.json"
def load_config(): return json.load(open(CONFIG_FILE, "r", encoding="utf-8")) if os.path.exists(CONFIG_FILE) else {}
def save_config(d): json.dump(d, open(CONFIG_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)
def load_db(): return json.load(open(DB_FILE, "r", encoding="utf-8")) if os.path.exists(DB_FILE) else {}
def save_db(d): json.dump(d, open(DB_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)

if "password_correct" not in st.session_state:
    st.title("🔐 AI 컨설팅 시스템")
    pw = st.text_input("접속 비밀번호를 입력하세요", type="password")
    if st.button("접속"):
        if pw == st.secrets.get("LOGIN_PASSWORD", "1234"): st.session_state["password_correct"] = True; st.rerun()
        else: st.error("비밀번호 불일치")
    st.stop()

# ==========================================
# 2. 사이드바 및 UI 상단 버튼
# ==========================================
st.markdown("""<style>
div.stButton > button { min-height: 55px !important; font-size: 16.5px !important; font-weight: bold !important; }
section[data-testid="stSidebar"] div.stButton > button { min-height: 45px !important; font-size: 12.5px !important; }
</style>""", unsafe_allow_html=True)

config = load_config()
if "api_key" not in st.session_state: st.session_state["api_key"] = config.get("GEMINI_API_KEY", "")
api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")
if st.sidebar.button("💾 API KEY 저장"):
    config["GEMINI_API_KEY"] = api_key_input; save_config(config); st.session_state["api_key"] = api_key_input; st.sidebar.success("저장됨")
if st.session_state["api_key"]: genai.configure(api_key=st.session_state["api_key"])

# 사이드바 업체 관리
st.sidebar.markdown("---")
st.sidebar.header("📂 업체 관리")
db = load_db()
if st.sidebar.button("💾 현재 정보 저장", use_container_width=True):
    cn = st.session_state.get("in_company_name", "").strip()
    if cn: db[cn] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}; save_db(db); st.sidebar.success(f"✅ '{cn}' 저장!")

selected_company = st.sidebar.selectbox("저장된 업체 목록", ["선택 안 함"] + list(db.keys()))
if st.sidebar.button("📂 불러오기", use_container_width=True) and selected_company != "선택 안 함":
    for k, v in db[selected_company].items(): st.session_state[k] = v
    st.rerun()

# 리포트 모드 전환 함수
def set_mode(m):
    if not st.session_state.get("in_company_name", "").strip(): st.error("🚨 기업명을 입력해 주세요.")
    else:
        st.session_state["permanent_data"] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        st.session_state["view_mode"] = m
        st.session_state.pop("generated_report", None)
        st.session_state.pop("generated_matching", None)
        st.rerun()

# 좌측 빠른 생성 버튼 복구
st.sidebar.markdown("---")
st.sidebar.header("🚀 빠른 리포트 생성")
if st.sidebar.button("📊 AI기업분석리포트", key="side_1", use_container_width=True): set_mode("REPORT")
if st.sidebar.button("💡 AI 정책자금 매칭리포트", key="side_2", use_container_width=True): set_mode("MATCHING")
if st.sidebar.button("📝 기관별 융자/사업계획서", key="side_3", use_container_width=True): set_mode("PLAN")

# 상단 탭 명칭 수정 반영
t1, t2, t3, t4 = st.columns(4)
with t1: st.button("📊 AI기업분석리포트", key="top_1", use_container_width=True, type="primary", on_click=set_mode, args=("REPORT",))
with t2: st.button("💡 AI 정책자금 매칭리포트", key="top_2", use_container_width=True, type="primary", on_click=set_mode, args=("MATCHING",))
with t3: st.button("📝 기관별 융자/사업계획서", key="top_3", use_container_width=True, type="primary", on_click=set_mode, args=("PLAN",))
with t4: st.button("📑 AI 사업계획서", key="top_4", use_container_width=True, type="primary", on_click=set_mode, args=("FULL_PLAN",))
st.markdown("<hr>", unsafe_allow_html=True)

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"

# ==========================================
# 3. 리포트 렌더링 파트
# ==========================================
if st.session_state["view_mode"] in ["REPORT", "MATCHING", "PLAN"]:
    if st.button("⬅️ 입력 화면으로 돌아가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    v = get_common_vars(st.session_state["permanent_data"])
    
    if st.session_state["view_mode"] == "REPORT":
        if "generated_report" not in st.session_state:
            with st.status("🚀 리포트 분석 및 시장 조사 중..."):
                val_cur = v.val_cur if v.val_cur > 0 else 1000
                m_vals = [int((val_cur/12) + ((val_cur/12)*0.5)*(i/11.0) + ((val_cur/12)*0.5)*0.15*np.sin((i/11.0)*np.pi*3.5)) for i in range(12)]
                fig = go.Figure(go.Scatter(x=[f"{i}월" for i in range(1, 13)], y=m_vals, mode='lines+markers+text', text=[format_kr_currency(x) for x in m_vals], textposition="top center", line=dict(color='#ab47bc', width=4, shape='spline')))
                plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
                pr = f"전문 컨설턴트. HTML 파스텔톤 표. [기업]{v.c_name}/업종:{v.c_ind}/아이템:{v.item}. 시장 동향 및 분석 결과 서술. [GRAPH_INSERT_POINT] 키워드 필수 포함."
                st.session_state["generated_report"] = clean_html(genai.GenerativeModel(get_best_model_name()).generate_content(pr).text).replace('[GRAPH_INSERT_POINT]', f"<div style='text-align:center;'>{plotly_html}</div>")
        res = st.session_state.get("generated_report", "")
    elif st.session_state["view_mode"] == "MATCHING":
        if "generated_matching" not in st.session_state:
            with st.status("🚀 AI 정책자금 매칭 심사 중..."):
                pr = f"정책자금 컨설턴트. HTML 박스 레이아웃. [기업]{v.c_name}/매출:{v.s_25}/보증:{v.guarantee}. 1~4순위 자금 추천."
                st.session_state["generated_matching"] = clean_html(genai.GenerativeModel(get_best_model_name()).generate_content(pr).text)
        res = st.session_state.get("generated_matching", "")
    else: res = "<div style='padding:50px; text-align:center;'><h2>기관별 서식 생성 준비 중...</h2></div>"

    CSS = "<style>body{font-family:'Malgun Gothic';background:#525659;padding:40px 0;}.doc{max-width:900px;margin:0 auto;background:#fff;padding:60px;box-shadow:0 4px 20px rgba(0,0,0,0.3);border-radius:8px;}table{width:100%;border-collapse:collapse;margin-bottom:20px;border:1.5px solid #333;}td,th{border:1px solid #333;padding:12px; font-size:14px;}</style>"
    full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{CSS}</head><body><div class='doc'>{res}</div></body></html>"
    components.html(full_html, height=1000, scrolling=True)
    st.download_button("📥 리포트 다운로드", full_html, f"{v.c_name}_리포트.html", "text/html")

# ==========================================
# 4. 입력 화면 (메인 대시보드)
# ==========================================
else:
    st.markdown("<p style='color:#c62828; font-weight:bold;'>※ 아래 정보를 입력해 주세요.</p>", unsafe_allow_html=True)
    st.header("1. 기업현황")
    r1c1, r1c2, r1c3 = st.columns(3)
    with r1c1:
        # 법인번호 배치 수정
        biz_col1, biz_col2 = st.columns([1, 1.2])
        with biz_col1: biz_type = st.radio("* 사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
        with biz_col2: 
            if biz_type == "법인": st.text_input("* 법인등록번호", placeholder="숫자만", key="in_raw_corp_no", on_change=cb_format_corp_no)
    with r1c2: st.text_input("* 기업명", key="in_company_name")
    with r1c3: st.text_input("* 사업자번호", placeholder="숫자만", key="in_raw_biz_no", on_change=cb_format_biz_no)

    r2c1, r2c2, r2c3 = st.columns(3)
    with r2c1: st.text_input("* 사업개시일", placeholder="YYYYMMDD", key="in_start_date", on_change=cb_format_date, args=("in_start_date",))
    with r2c2: st.text_input("* 사업장 주소", key="in_biz_addr")
    with r2c3: st.selectbox("* 업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")

    r3c1, r3c2, r3c3 = st.columns(3)
    with r3c1:
        st.text_input("전화번호", placeholder="숫자만", key="in_biz_tel", on_change=cb_format_phone, args=("in_biz_tel",))
        st.number_input("상시근로자수(명)", value=0, format="%d", key="in_employee_count")
    with r3c2:
        ls = st.radio("임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
        if ls == "임대":
            ilc1, ilc2 = st.columns(2)
            with ilc1: st.number_input("보증금(만)", value=0, key="in_lease_deposit")
            with ilc2: st.number_input("월세(만)", value=0, key="in_lease_rent")
    with r3c3:
        if st.radio("추가사업장", ["무", "유"], horizontal=True, key="in_has_additional_biz") == "유":
            st.text_input("추가 정보", key="in_additional_biz_addr")

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("2. 대표자 정보")
    dob = str(st.session_state.get("in_rep_dob", "") or "").replace(".", "")
    is_youth = len(dob)==8 and (2026 - int(dob[:4]) <= 39)
    d_lbl = "* 생년월일" + (" 🌟 청년" if is_youth else "")
    r4c1, r4c2, r4c3, r4c4 = st.columns(4)
    with r4c1: st.text_input("* 대표자명", key="in_rep_name")
    with r4c2: st.text_input(d_lbl, placeholder="YYYYMMDD", key="in_rep_dob", on_change=cb_format_date, args=("in_rep_dob",))
    with r4c3: st.selectbox("통신사", ["SKT", "KT", "LG U+", "알뜰폰"], key="in_rep_telecom")
    with r4c4: st.text_input("* 휴대폰", placeholder="숫자만", key="in_rep_phone", on_change=cb_format_phone, args=("in_rep_phone",))

    r5c1, r5c2, r5c3 = st.columns([2, 1, 1])
    with r5c1: st.text_input("* 거주지 주소", key="in_home_addr")
    with r5c2: st.selectbox("학력", ["중졸", "고졸", "전문대졸", "대졸", "석사", "박사"], key="in_edu_school")
    with r5c3: st.text_input("전공", key="in_edu_major")

    r6c1, r6c2, r6c3 = st.columns([1, 1, 2])
    with r6c1: st.radio("* 거주지 상태", ["자가", "임대"], horizontal=True, key="in_home_status")
    with r6c2:
        st.text_input("이메일", key="in_rep_email")
        st.multiselect("부동산 현황", ["아파트", "빌라", "단독", "토지", "상가", "공장", "기타"], key="in_real_estate")
    with r6c3: st.text_area("* 경력", key="in_career", height=135)

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("3. 신용 및 연체 정보")
    cr1, cr2 = st.columns([1.2, 1])
    with cr1:
        stc1, stc2 = st.columns(2)
        with stc1: st.radio("세금체납", ["무", "유"], horizontal=True, key="in_tax_status")
        with stc2: st.radio("금융연체", ["무", "유"], horizontal=True, key="in_fin_status")
        sc1, sc2 = st.columns(2)
        with sc1: kcb = st.number_input("KCB 점수", value=0, key="in_kcb_score")
        with sc2: nice = st.number_input("NICE 점수", value=0, key="in_nice_score")
    with cr2:
        kg, ng = get_credit_grade(kcb, 'KCB'), get_credit_grade(nice, 'NICE')
        st.markdown(f"<div style='padding:25px; background:#e8f0fe; border-radius:15px; text-align:center; border:2px solid #a4c2f4; margin-top:10px;'><h3>🏆 신용등급 판정</h3><p style='font-size:30px; font-weight:900;'>KCB: {kg}등급 | NICE: {ng}등급</p></div>", unsafe_allow_html=True)

    st.header("4. 매출현황")
    m1, m2, m3, m4 = st.columns(4)
    with m1: st.number_input("금년 매출(만)", value=0, key="in_sales_current")
    with m2: st.number_input("25년 매출(만)", value=0, key="in_sales_2025")
    with m3: st.number_input("24년 매출(만)", value=0, key="in_sales_2024")
    with m4: st.number_input("23년 매출(만)", value=0, key="in_sales_2023")

    st.header("5. 부채현황")
    d1, d2, d3, d4 = st.columns(4)
    with d1: st.number_input("중진공(만)", value=0, key="in_debt_kosme")
    with d2: st.number_input("소진공(만)", value=0, key="in_debt_semas")
    with d3: st.number_input("신보(만)", value=0, key="in_debt_kodit")
    with d4: st.number_input("기보(만)", value=0, key="in_debt_kibo")

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("8. 특허 및 지식재산권")
    pc1, pc2 = st.columns(2)
    with pc1:
        if st.radio("특허보유여부", ["무", "유"], horizontal=True, key="in_has_patent") == "유":
            for pt in ["특허출원", "특허등록", "상표등록", "디자인등록"]:
                cnt = st.number_input(f"➤ {pt} 건수", min_value=0, step=1, format="%d", key=f"in_{pt}_cnt")
                for i in range(int(cnt)): st.text_input(f"↪ {pt}번호 {i+1}", key=f"in_{pt}_num_{i}")
    with pc2:
        if st.radio("지원사업이력", ["무", "유"], horizontal=True, key="in_has_gov") == "유":
            cnt = st.number_input("➤ 지원사업 건수", min_value=0, step=1, format="%d", key="in_gov_cnt")
            for i in range(int(cnt)): st.text_input(f"↪ 사업명 {i+1}", key=f"in_gov_name_{i}")

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("9. 비즈니스 상세 정보")
    st.text_area("* [아이템]", key="in_item_desc")
    st.text_input("[생산공정도]", key="in_process_desc")
    st.text_area("* [판매루트]", key="in_sales_route")
    st.text_area("[시장현황]", key="in_market_status")
    st.text_area("[차별화]", key="in_diff_point")
    st.text_area("* [앞으로의 계획]", key="in_future_plan")

    st.header("6. 필요자금")
    p1, p2, p3 = st.columns([1, 1, 2])
    with p1: st.selectbox("* 자금구분", ["운전자금", "시설자금"], key="in_fund_type")
    with p2: st.number_input("* 금액(만원)", value=0, key="in_req_amount")
    with p3: st.text_input("용도", key="in_fund_purpose")

    st.header("7. 인증현황")
    certs = ["소상공인", "창업", "여성기업", "이노비즈", "벤처", "뿌리", "ISO", "HACCP"]
    for i in range(0, 8, 4):
        cols = st.columns(4)
        for j in range(4):
            idx = i + j
            with cols[j]:
                if st.checkbox(certs[idx], key=f"in_chk_{idx}"):
                    st.text_input(f"↪ {certs[idx]} 일자", key=f"in_cert_date_{idx}", on_change=cb_format_date, args=(f"in_cert_date_{idx}",))
    
    st.success("✅ 세팅 완료! 상단 버튼을 클릭해 리포트를 생성하세요.")
