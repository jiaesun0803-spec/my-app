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
    """숫자 입력이 None이거나 비어있을 때 0으로 처리하는 안전 함수"""
    try:
        if value is None: return 0
        clean_val = str(value).replace(',', '').strip()
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
    if s >= 832: return "3등급", "#43A047"
    if s >= 630: return "6등급", "#FB8C00"
    return "저신용", "#E53935"

def get_nice_info(score):
    s = safe_int(score)
    if s >= 900: return "1등급", "#1E88E5"
    if s >= 840: return "3등급", "#43A047"
    if s >= 665: return "6등급", "#FB8C00"
    return "저신용", "#E53935"

def create_gauge(score, title, color):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = score if score else 0,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font': {'size': 14, 'color': '#666'}},
        gauge = {
            'axis': {'range': [None, 1000], 'tickwidth': 1, 'tickfont': {'size': 10}},
            'bar': {'color': color},
            'bgcolor': "white",
            'borderwidth': 1,
            'steps': [
                {'range': [0, 600], 'color': '#FFEBEE'},
                {'range': [600, 850], 'color': '#FFF3E0'},
                {'range': [850, 1000], 'color': '#E8F5E9'}],
        }
    ))
    fig.update_layout(height=165, margin=dict(l=10, r=10, t=40, b=10), paper_bgcolor="rgba(0,0,0,0)")
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
        else: st.error("비밀번호 불일치")
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
if st.sidebar.button("💾 현재 업체 정보 저장", use_container_width=True):
    cn = st.session_state.get("in_company_name", "").strip()
    if cn:
        db[cn] = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        save_db(db); st.sidebar.success(f"✅ '{cn}' 저장!")

selected_company = st.sidebar.selectbox("불러올 업체 선택", ["선택 안 함"] + list(db.keys()))
if st.sidebar.button("📂 불러오기", use_container_width=True) and selected_company != "선택 안 함":
    for k, v in db[selected_company].items(): st.session_state[k] = v
    st.session_state["view_mode"] = "INPUT"; st.rerun()

# ==========================================
# 3. 메인 대시보드 화면
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

# 공통 안내 문구 및 라벨 접미사
GUIDE_VAL = "1억=10000으로 입력"
# 폰트 0.75em으로 더 축소 및 색상 조정
LABEL_SUFFIX = f" <span style='font-size:0.75em; font-weight:normal; color:#888;'>(만원-{GUIDE_VAL})</span>"

if st.session_state["view_mode"] == "INPUT":
    # --- 1. 기업현황 ---
    st.header("1. 기업현황")
    c1r1 = st.columns([2, 1, 1.5, 1.5])
    with c1r1[0]: st.text_input("기업명", key="in_company_name")
    with c1r1[1]: biz_type = st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
    with c1r1[2]: st.text_input("사업자번호", placeholder="000-00-00000", key="in_raw_biz_no")
    with c1r1[3]: 
        if biz_type == "법인": st.text_input("법인등록번호", placeholder="000000-0000000", key="in_raw_corp_no")

    c1r2 = st.columns([1, 2, 1])
    with c1r2[0]: st.text_input("사업개시일", placeholder="YYYY.MM.DD", key="in_start_date")
    with c1r2[1]: st.text_input("사업장 주소", key="in_biz_addr")
    with c1r2[2]: st.selectbox("업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")

    c1r3 = st.columns([1, 3])
    with c1r3[0]: st.text_input("전화번호", placeholder="010-0000-0000", key="in_biz_tel")
    with c1r3[1]:
        ls_cols = st.columns([1, 1, 1])
        with ls_cols[0]: ls = st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
        if ls == "임대":
            with ls_cols[1]: 
                st.markdown(f"**보증금**{LABEL_SUFFIX}", unsafe_allow_html=True)
                # value=None으로 설정해야 Placeholder(흐릿한 글씨)가 나타남
                st.number_input("보증금", value=st.session_state.get("in_lease_deposit", None), key="in_lease_deposit", placeholder=GUIDE_VAL, label_visibility="collapsed")
            with ls_cols[2]: 
                st.markdown(f"**월임대료**{LABEL_SUFFIX}", unsafe_allow_html=True)
                st.number_input("월임대료", value=st.session_state.get("in_lease_rent", None), key="in_lease_rent", placeholder=GUIDE_VAL, label_visibility="collapsed")

    # --- 2. 대표자 정보 ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("2. 대표자 정보")
    c2r1 = st.columns(4)
    with c2r1[0]: st.text_input("대표자명", key="in_rep_name")
    with c2r1[1]: st.text_input("생년월일", placeholder="YYYY.MM.DD", key="in_rep_dob")
    with c2r1[2]: st.text_input("연락처", placeholder="010-0000-0000", key="in_rep_phone")
    with c2r1[3]: st.selectbox("통신사", ["SKT", "KT", "LG U+", "알뜰폰"], key="in_rep_telecom")

    c2r2 = st.columns([2, 1, 1])
    with c2r2[0]: st.text_input("거주지 주소", key="in_home_addr")
    with c2r2[1]: st.selectbox("최종학력", ["중학교 졸업", "고등학교 졸업", "대학교 졸업", "석사 수료", "박사 수료"], key="in_edu_school")
    with c2r2[2]: st.text_input("전공", key="in_edu_major")

    c2r3 = st.columns([1.5, 2.5])
    with c2r3[0]: st.radio("거주지 상태", ["자가", "임대"], horizontal=True, key="in_home_status")
    with c2r3[1]: st.multiselect("부동산 소유현황", ["아파트", "빌라", "토지", "임야", "공장", "기타"], key="in_real_estate")

    c2r4 = st.columns(4)
    with c2r4[0]: st.text_input("이메일 주소", key="in_rep_email")
    with c2r4[1]: st.text_input("주요경력 1", key="in_career_1")
    with c2r4[2]: st.text_input("주요경력 2", key="in_career_2")
    with c2r4[3]: st.text_input("주요경력 3", key="in_career_3")

    # --- 3. 신용 정보 시각화 (정렬 유지) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("3. 신용 정보 시각화")
    c3_col1, c3_col2, c3_col3 = st.columns([1.1, 1.2, 1.8])
    with c3_col1:
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        t1_c1, t1_c2 = st.columns(2)
        t1_c1.markdown("<p style='font-size:0.9em; font-weight:bold; margin-bottom: 0;'>금융연체 여부</p>", unsafe_allow_html=True)
        t1_c2.markdown("<p style='font-size:0.9em; font-weight:bold; margin-bottom: 0;'>세금체납 여부</p>", unsafe_allow_html=True)
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        r1_c1, r1_c2 = st.columns(2)
        with r1_c1: delinquency = st.radio("f_delin", ["무", "유"], horizontal=True, key="in_fin_delinquency", label_visibility="collapsed")
        with r1_c2: tax_delin = st.radio("t_delin", ["무", "유"], horizontal=True, key="in_tax_delinquency", label_visibility="collapsed")
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        t2_c1, t2_c2 = st.columns(2)
        t2_c1.markdown("<p style='font-size:0.9em; font-weight:bold; margin-bottom: 0;'>KCB 점수</p>", unsafe_allow_html=True)
        t2_c2.markdown("<p style='font-size:0.9em; font-weight:bold; margin-bottom: 0;'>NICE 점수</p>", unsafe_allow_html=True)
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        r2_c1, r2_c2 = st.columns(2)
        # 점수는 Placeholder 보다는 '점수입력' 등으로 표시
        with r2_c1: s_kcb = st.number_input("k_in", value=st.session_state.get("in_kcb_score", None), key="in_kcb_score", label_visibility="collapsed", placeholder="점수입력")
        with r2_c2: s_nice = st.number_input("n_in", value=st.session_state.get("in_nice_score", None), key="in_nice_score", label_visibility="collapsed", placeholder="점수입력")
    with c3_col2:
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        if delinquency == "유" or tax_delin == "유":
            st.markdown(f"""<div style='background-color: #FFEBEE; padding: 20px; border-radius: 10px; border-left: 5px solid #E53935; height: 180px; overflow: hidden;'><h3 style='color: #B71C1C; margin-top: 0;'>⚠️ 연체/체납 주의</h3><p style='color: #D32F2F; font-size: 0.9em; line-height: 1.5;'>즉시 해결이 필요합니다.</p></div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div style='background-color: #E8F5E9; padding: 20px; border-radius: 10px; border-left: 5px solid #43A047; height: 180px; overflow: hidden;'><h3 style='color: #1B5E20; margin-top: 0;'>✅ 신용 양호</h3><p style='color: #2E7D32; font-size: 0.9em; line-height: 1.5;'>기초 신용 요건을 충족한 상태입니다.</p></div>""", unsafe_allow_html=True)
    with c3_col3:
        v_cols = st.columns(2)
        k_grade, k_color = get_kcb_info(s_kcb); n_grade, n_color = get_nice_info(s_nice)
        with v_cols[0]:
            st.plotly_chart(create_gauge(s_kcb, "KCB Score", k_color), use_container_width=True, config={'displayModeBar': False})
            st.markdown(f"<div style='text-align:center; padding:5px; background-color:{k_color}; color:white; border-radius:5px; font-size:0.9em; margin-top:-15px;'><b>KCB: {k_grade}</b></div>", unsafe_allow_html=True)
        with v_cols[1]:
            st.plotly_chart(create_gauge(s_nice, "NICE Score", n_color), use_container_width=True, config={'displayModeBar': False})
            st.markdown(f"<div style='text-align:center; padding:5px; background-color:{n_color}; color:white; border-radius:5px; font-size:0.9em; margin-top:-15px;'><b>NICE: {n_grade}</b></div>", unsafe_allow_html=True)

    # --- 4. 매출현황 ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("4. 매출현황")
    st.markdown("**수출현황**")
    
    # 수출현황 버튼 위치 복구
    exp_labels = st.columns([1, 1, 2])
    with exp_labels[0]: st.markdown("<p style='font-size:0.9em; font-weight:bold;'>수출매출 여부</p>", unsafe_allow_html=True)
    with exp_labels[1]: st.markdown("<p style='font-size:0.9em; font-weight:bold;'>수출진행예정 여부</p>", unsafe_allow_html=True)
    exp_radios = st.columns([1, 1, 2])
    with exp_radios[0]: has_export = st.radio("ex_rev_r", ["무", "유"], horizontal=True, key="in_export_revenue", label_visibility="collapsed")
    with exp_radios[1]: plan_export = st.radio("ex_plan_r", ["무", "유"], horizontal=True, key="in_planned_export", label_visibility="collapsed")
    
    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
    
    m_titles = ["금년 매출합계", "25년도 매출합계", "24년도 매출합계", "23년도 매출합계"]
    m_keys = ["in_sales_cur", "in_sales_25", "in_sales_24", "in_sales_23"]
    
    lc = st.columns(4)
    for i, title in enumerate(m_titles): lc[i].markdown(f"**{title}**{LABEL_SUFFIX}", unsafe_allow_html=True)
    ic = st.columns(4)
    for i, key in enumerate(m_keys): 
        # [중요] value=None 으로 설정하여 모든 칸에 흐릿한 글씨 노출
        ic[i].number_input(label=m_titles[i], value=st.session_state.get(key, None), key=key, placeholder=GUIDE_VAL, label_visibility="collapsed")
    
    if has_export == "유":
        st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
        e_titles = ["금년 수출매출", "25년도 수출매출합계", "24년도 수출매출합계", "23년도 수출매출합계"]
        e_keys = ["in_exp_cur", "in_exp_25", "in_exp_24", "in_exp_23"]
        elc = st.columns(4)
        for i, title in enumerate(e_titles): elc[i].markdown(f"<p style='color:#1E88E5;'><b>{title}</b>{LABEL_SUFFIX}</p>", unsafe_allow_html=True)
        eic = st.columns(4)
        for i, key in enumerate(e_keys): eic[i].number_input(label=e_titles[i], value=st.session_state.get(key, None), key=key, placeholder=GUIDE_VAL, label_visibility="collapsed")

    # --- 5. 기대출 현황 ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("5. 기대출 현황")
    debt_items = [
        ("중진공 대출금", "in_debt_kosme"), ("소진공 대출금", "in_debt_semas"), 
        ("신용보증기금 대출금", "in_debt_kodit"), ("기술보증기금 대출금", "in_debt_kibo"),
        ("신용보증재단 대출금", "in_debt_foundation"), ("회사 담보 대출금", "in_debt_corp_collateral"),
        ("대표 신용 대출금", "in_debt_rep_credit"), ("대표 담보 대출금", "in_debt_rep_collateral")
    ]
    for row_idx in range(0, len(debt_items), 4):
        cols = st.columns(4)
        for col_idx in range(4):
            item_idx = row_idx + col_idx
            if item_idx < len(debt_items):
                title, key = debt_items[item_idx]
                with cols[col_idx]:
                    st.markdown(f"**{title}**{LABEL_SUFFIX}", unsafe_allow_html=True)
                    # [중요] value=None 으로 설정하여 모든 칸에 흐릿한 글씨 노출
                    st.number_input(title, value=st.session_state.get(key, None), key=key, placeholder=GUIDE_VAL, label_visibility="collapsed")

    # --- 6, 7, 8번 ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("6. 보유 인증")
    cert_list = ["소상공인확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
    for i in range(0, len(cert_list), 4):
        cols = st.columns(4)
        for j in range(4):
            if i+j < len(cert_list): cols[j].checkbox(cert_list[i+j], key=f"in_cert_{cert_list[i+j]}")

    st.header("7. 특허 및 정부지원")
    c7r1 = st.columns(2)
    with c7r1[0]:
        if st.radio("특허 보유 여부", ["무", "유"], horizontal=True, key="in_has_patent") == "유":
            st.number_input("특허 건수", value=st.session_state.get("in_pat_cnt", None), key="in_pat_cnt", placeholder="건수 입력"); st.text_area("특허 명칭 상세", key="in_pat_desc")
    with c7r1[1]:
        if st.radio("정부지원 수혜이력", ["무", "유"], horizontal=True, key="in_has_gov") == "유":
            st.number_input("수혜 건수", value=st.session_state.get("in_gov_cnt", None), key="in_gov_cnt", placeholder="건수 입력"); st.text_area("사업명 상세", key="in_gov_desc")

    st.header("8. 비즈니스 정보")
    st.text_area("핵심 아이템 상세 설명", key="in_item_desc")
    st.text_input("제품 생산 공정도 상세", key="in_process_desc")
    st.text_area("시장 현황 및 미래 계획", key="in_future_plan")

    st.success("✅ [Placeholder 전체 적용 완료] 모든 금액창에 흐릿한 안내 문구가 나타납니다.")

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
        with st.status("🚀분석 중..."):
            res = clean_html(model.generate_content(f"{cn} 기업 통합 분석 리포트 HTML 작성").text)
        st.markdown(res, unsafe_allow_html=True)
