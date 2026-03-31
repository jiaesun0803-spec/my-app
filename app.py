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
# 0. 핵심 설정 및 디자인 커스텀 (CSS)
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

st.markdown("""
<style>
    /* 모든 위젯 라벨 설정: 일반 굵기, 크기 통일 */
    [data-testid="stWidgetLabel"] p {
        font-weight: 400 !important;
        font-size: 14px !important;
        color: #31333F !important;
        margin-bottom: 5px !important;
    }
    h2 { font-weight: 700 !important; }
    input::placeholder { font-size: 0.8em !important; color: #888 !important; }
    
    /* 9번 섹션 전용 파란색 라벨 스타일 */
    .blue-label {
        color: #1E88E5 !important;
        font-size: 14px !important;
        font-weight: 400 !important;
        margin-bottom: 5px !important;
        display: inline-block;
    }
    
    /* 입력창 정렬 보정 */
    .stNumberInput, .stTextInput, .stTextArea {
        margin-top: 0px !important;
    }
</style>
""", unsafe_allow_html=True)

def safe_int(value):
    try:
        if value is None or value == "": return 0
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

# --- 신용 등급/게이지 로직 (유지) ---
def get_kcb_info(score):
    s = safe_int(score)
    if s >= 942: return "1등급", "#43A047"
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
        mode = "gauge+number", value = score if score else 0,
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
# 1. 파일 및 보안 DB 설정
# ==========================================
DB_FILE = "company_db.json"
def load_db(): return json.load(open(DB_FILE, "r", encoding="utf-8")) if os.path.exists(DB_FILE) else {}
def save_db(data): json.dump(data, open(DB_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"

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
if st.sidebar.button("💾 현재 정보 저장", use_container_width=True):
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
t_cols = st.columns(4)
with t_cols[0]: 
    if st.button("📊 AI기업분석리포트", use_container_width=True, type="primary"): st.session_state["view_mode"] = "REPORT"; st.rerun()
with t_cols[1]: 
    if st.button("💡 AI 정책자금 매칭", use_container_width=True, type="primary"): st.session_state["view_mode"] = "MATCHING"; st.rerun()
with t_cols[2]: 
    if st.button("📝 융자/사업계획서", use_container_width=True, type="primary"): st.session_state["view_mode"] = "PLAN"; st.rerun()
with t_cols[3]: 
    if st.button("📑 전체 데이터 리셋", use_container_width=True): 
        for key in list(st.session_state.keys()): 
            if key.startswith("in_"): del st.session_state[key]
        st.rerun()
st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

GUIDE_STR = "1억=10000으로 입력"

if st.session_state["view_mode"] == "INPUT":
    # --- 1. 기업현황 (정렬 보완) ---
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

    # [수정] 3열로 전화번호, 보증금, 월임대료 위치 일치
    c1r3 = st.columns([1, 1, 1, 1])
    with c1r3[0]: st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
    with c1r3[1]: st.text_input("전화번호", placeholder="010-0000-0000", key="in_biz_tel")
    with c1r3[2]: st.number_input("보증금 (만원)", value=st.session_state.get("in_lease_deposit", None), key="in_lease_deposit", placeholder=GUIDE_STR, step=1, format="%d")
    with c1r3[3]: st.number_input("월임대료 (만원)", value=st.session_state.get("in_lease_rent", None), key="in_lease_rent", placeholder=GUIDE_STR, step=1, format="%d")

    # --- 2~7번 항목 (유지) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("2. 대표자 정보")
    c2r1 = st.columns(4)
    with c2r1[0]: st.text_input("대표자명", key="in_rep_name")
    with c2r1[1]: st.text_input("생년월일", placeholder="YYYY.MM.DD", key="in_rep_dob")
    with c2r1[2]: st.text_input("연락처", placeholder="010-0000-0000", key="in_rep_phone")
    with c2r1[3]: st.selectbox("통신사", ["SKT", "KT", "LG U+", "알뜰폰"], key="in_rep_telecom")
    c2r2 = st.columns([2, 1, 1])
    with c2r2[0]: st.text_input("거주지 주소", key="in_home_addr")
    with c2r2[1]: st.selectbox("최종학력", ["선택", "중학교 졸업", "고등학교 졸업", "대학교 졸업", "석사 수료", "박사 수료"], key="in_edu_school")
    with c2r2[2]: st.text_input("전공", key="in_edu_major")
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("3. 대표자 신용정보")
    c3_col1, c3_col2, c3_col3 = st.columns([1.1, 1.2, 1.8])
    with c3_col1:
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        t1 = st.columns(2); t1[0].markdown("금융연체 여부"); t1[1].markdown("세금체납 여부")
        r1 = st.columns(2); delinquency = r1[0].radio("f_d", ["무", "유"], horizontal=True, key="in_fin_delinquency", label_visibility="collapsed")
        tax_delin = r1[1].radio("t_d", ["무", "유"], horizontal=True, key="in_tax_delinquency", label_visibility="collapsed")
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        t2 = st.columns(2); t2[0].markdown("KCB 점수"); t2[1].markdown("NICE 점수")
        r2 = st.columns(2); s_kcb = r2[0].number_input("k_i", value=st.session_state.get("in_kcb_score", None), key="in_kcb_score", label_visibility="collapsed", placeholder="점수입력", step=1, format="%d")
        s_nice = r2[1].number_input("n_i", value=st.session_state.get("in_nice_score", None), key="in_nice_score", label_visibility="collapsed", placeholder="점수입력", step=1, format="%d")
    with c3_col2:
        st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
        if delinquency == "유" or tax_delin == "유":
            st.markdown(f"""<div style='background-color: #FFEBEE; padding: 20px; border-radius: 10px; border-left: 5px solid #E53935; height: 185px;'><p style='color:#B71C1C; font-weight:700;'>⚠️ 주의 요망</p><p style='font-size:0.9em;'>연체/체납 해결이 급선무입니다.</p></div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div style='background-color: #E8F5E9; padding: 20px; border-radius: 10px; border-left: 5px solid #43A047; height: 185px;'><p style='color:#1B5E20; font-weight:700;'>✅ 신용 양호</p><p style='font-size:0.9em;'>기초 요건을 충족하고 있습니다.</p></div>""", unsafe_allow_html=True)
    with c3_col3:
        v_cols = st.columns(2); k_grade, k_color = get_kcb_info(s_kcb); n_grade, n_color = get_nice_info(s_nice)
        with v_cols[0]: st.plotly_chart(create_gauge(s_kcb, "KCB", k_color), use_container_width=True, config={'displayModeBar': False})
        with v_cols[1]: st.plotly_chart(create_gauge(s_nice, "NICE", n_color), use_container_width=True, config={'displayModeBar': False})

    # --- 4~7번 중략 (기능 유지) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("4. 매출현황")
    exp_r = st.columns([1, 1, 2])
    with exp_r[0]: has_export = st.radio("수출매출 여부", ["무", "유"], horizontal=True, key="in_export_revenue")
    with exp_r[1]: plan_export = st.radio("수출예정 여부", ["무", "유"], horizontal=True, key="in_planned_export")
    m_titles = ["금년 매출합계", "25년도 매출합계", "24년도 매출합계", "23년도 매출합계"]
    m_keys = ["in_sales_cur", "in_sales_25", "in_sales_24", "in_sales_23"]
    mc = st.columns(4)
    for i, key in enumerate(m_keys): mc[i].number_input(f"{m_titles[i]} (만원)", value=st.session_state.get(key, None), key=key, placeholder=GUIDE_STR, step=1, format="%d")

    st.markdown("<br>", unsafe_allow_html=True)
    st.header("5. 기대출 현황")
    debt_items = [("중진공", "in_debt_kosme"), ("소진공", "in_debt_semas"), ("신보", "in_debt_kodit"), ("기보", "in_debt_kibo")]
    dc = st.columns(4)
    for i, (name, key) in enumerate(debt_items): dc[i].number_input(f"{name} 대출금 (만원)", value=st.session_state.get(key, None), key=key, placeholder=GUIDE_STR, step=1, format="%d")

    # --- 8. 비즈니스 정보 (세분화 및 AI 기능) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("8. 비즈니스 상세 정보")
    
    # AI 자동 채우기 로직
    if st.button("🪄 핵심아이템 기반 AI 자동 초안 생성", type="secondary"):
        if not st.session_state.get("in_item_desc"):
            st.warning("먼저 '핵심 아이템' 내용을 입력해주세요.")
        elif not st.session_state.get("api_key"):
            st.error("사이드바에 API Key를 먼저 저장해주세요.")
        else:
            with st.spinner("AI가 비즈니스 전략을 구상 중입니다..."):
                try:
                    model = genai.GenerativeModel(get_best_model_name())
                    fill_prompt = f"""
                    아이템: {st.session_state['in_item_desc']}
                    위 아이템을 바탕으로 전문적인 사업계획서의 다음 항목들을 작성하라.
                    반드시 JSON 형식으로 출력하라: 
                    {{"diff": "차별성", "process": "공정도 설명", "market": "시장현황", "target": "타겟고객", "revenue": "수익모델", "plan": "앞으로의계획"}}
                    """
                    response = model.generate_content(fill_prompt)
                    res_json = json.loads(response.text.replace("```json", "").replace("```", ""))
                    st.session_state["in_item_diff"] = res_json['diff']
                    st.session_state["in_process_desc"] = res_json['process']
                    st.session_state["in_market_status"] = res_json['market']
                    st.session_state["in_target_cust"] = res_json['target']
                    st.session_state["in_revenue_model"] = res_json['revenue']
                    st.session_state["in_future_plan"] = res_json['plan']
                    st.success("AI 초안 작성이 완료되었습니다! 내용을 검토하고 수정하세요.")
                    st.rerun()
                except Exception as e:
                    st.error(f"AI 생성 중 오류 발생: {e}")

    st.text_area("핵심 아이템", key="in_item_desc", placeholder="제품/서비스의 핵심 내용을 입력하세요.")
    col8a, col8b = st.columns(2)
    with col8a:
        st.text_area("경쟁력 및 차별성", key="in_item_diff")
        st.text_area("시장 현황", key="in_market_status")
        st.text_area("수익 모델", key="in_revenue_model")
    with col8b:
        st.text_area("제품생산/서비스 공정도", key="in_process_desc")
        st.text_area("구체적인 타겟 고객", key="in_target_cust")
        st.text_area("앞으로의 계획", key="in_future_plan")

    # --- 9. 자금 계획 (정렬 보완 및 파란색 라벨) ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.header("9. 자금 계획")
    
    c9 = st.columns([1, 2])
    with c9[0]:
        st.markdown('<p class="blue-label">이번 조달 필요 자금 (만원)</p>', unsafe_allow_html=True)
        st.number_input("조달금액", value=st.session_state.get("in_req_funds", None), key="in_req_funds", placeholder=GUIDE_STR, label_visibility="collapsed", step=1, format="%d")
    with c9[1]:
        st.markdown('<p style="font-size:14px; margin-bottom:5px;">상세 자금 집행 계획</p>', unsafe_allow_html=True)
        st.text_area("자금집행", key="in_fund_plan", placeholder="예: 연구인력 채용(40%), 시제품 제작(30%) 등", label_visibility="collapsed")

    st.success("✅ [최종 업데이트] 입력창 정렬 및 8번 섹션 세분화가 완료되었습니다.")

# ==========================================
# 4. 리포트 출력 화면
# ==========================================
else:
    if st.button("⬅️ 입력 화면으로 돌아가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    d = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
    cn = d.get('in_company_name', '미입력').strip()
    
    if st.session_state["view_mode"] == "REPORT":
        st.subheader(f"📊 AI 통합 기업분석 리포트: {cn}")
        with st.status("🚀 정밀 분석 및 사업계획서 초안 생성 중..."):
            model = genai.GenerativeModel(get_best_model_name())
            prompt = f"다음 기업 정보를 바탕으로 정책자금 심사위원을 설득할 수 있는 수준 높은 사업계획서 및 분석 리포트를 HTML로 작성하라. 데이터: {d}"
            res = clean_html(model.generate_content(prompt).text)
        st.markdown(res, unsafe_allow_html=True)
