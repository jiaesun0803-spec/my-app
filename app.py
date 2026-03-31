import streamlit as st
import json
import os
import time
import pandas as pd
import numpy as np
import google.generativeai as genai
import plotly.graph_objects as go

# ==========================================
# 0. 핵심 설정 및 디자인 커스텀 (CSS)
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

st.markdown("""
<style>
    /* 1. 일반 위젯 라벨 설정 (표준 14px) */
    [data-testid="stWidgetLabel"] p {
        font-weight: 400 !important;
        font-size: 14px !important;
        color: #31333F !important;
        margin-bottom: 5px !important;
    }
    /* 2. 섹션 헤더 스타일 */
    h2 { font-weight: 700 !important; margin-top: 25px !important; }
    
    /* 3. 입력창 내부 Placeholder(흐릿한 글씨) 크기 조절 */
    input::placeholder {
        font-size: 0.85em !important;
        color: #888 !important;
    }
    
    /* 4. 숫자 입력창 우측 증감 버튼 제거 */
    input::-webkit-outer-spin-button,
    input::-webkit-inner-spin-button {
        -webkit-appearance: none;
        margin: 0;
    }
    
    /* 5. 6번 보유인증 폰트 설정 (15px) */
    [data-testid="stCheckbox"] label p {
        font-size: 15px !important;
        font-weight: 450 !important;
    }

    /* [해결] 라디오 버튼 옵션 너비 고정 (임대/유 위치 동일화) */
    [data-testid="stHorizontalRadio"] div label {
        min-width: 75px !important;
        margin-right: 0px !important;
    }

    /* 6. 9번 섹션 강조 라벨: 16px + 볼드 + 파란색 */
    .blue-bold-label-16 {
        color: #1E88E5 !important;
        font-size: 16px !important;
        font-weight: 700 !important;
        display: inline-block;
        margin-bottom: 12px !important;
    }
    
    /* 7. 상세 자금 집행 계획 라벨 높이 조정용 */
    .std-label-14 {
        font-size: 14px !important;
        font-weight: 400 !important;
        display: inline-block;
        margin-bottom: 12px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 헬퍼 함수 ---
def safe_int(value):
    try:
        if value is None or value == "": return 0
        return int(float(str(value).replace(',', '').strip()))
    except: return 0

def clean_html(text):
    if not text: return ""
    return text.replace("```html", "").replace("```", "").strip()

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
# 1. 상태 관리 및 사이드바
# ==========================================
DB_FILE = "company_db.json"
def load_db(): return json.load(open(DB_FILE, "r", encoding="utf-8")) if os.path.exists(DB_FILE) else {}
def save_db(data): json.dump(data, open(DB_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=4)

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
if "api_key" not in st.session_state: st.session_state["api_key"] = ""

st.sidebar.header("⚙️ AI 엔진 설정")
api_key_input = st.sidebar.text_input("Gemini API Key", value=st.session_state["api_key"], type="password")
if st.sidebar.button("💾 API KEY 저장", use_container_width=True):
    st.session_state["api_key"] = api_key_input
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("📂 업체 관리")
db = load_db()
selected_company = st.sidebar.selectbox("불러올 업체 선택", ["선택 안 함"] + list(db.keys()))

sb_col1, sb_col2 = st.sidebar.columns(2)
with sb_col1:
    if st.button("📂 불러오기", use_container_width=True):
        if selected_company != "선택 안 함":
            for k, v in db[selected_company].items(): st.session_state[k] = v
            st.rerun()
with sb_col2:
    if st.button("💾 정보 저장", use_container_width=True):
        name = st.session_state.get("in_company_name", "").strip()
        if name:
            current_data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            db[name] = current_data
            save_db(db); st.sidebar.success("저장 완료!")

st.sidebar.markdown("---")
st.sidebar.header("🚀 리포트 생성")
if st.sidebar.button("📊 AI 기업분석리포트", key="sb_r1", use_container_width=True): st.session_state["view_mode"] = "REPORT"; st.rerun()
if st.sidebar.button("💡 AI 정책자금 매칭", key="sb_r2", use_container_width=True): st.session_state["view_mode"] = "MATCHING"; st.rerun()
if st.sidebar.button("📝 기관별 융자/사업계획서", key="sb_r3", use_container_width=True): st.session_state["view_mode"] = "LOAN_PLAN"; st.rerun()
if st.sidebar.button("📑 AI 사업계획서", key="sb_r4", use_container_width=True): st.session_state["view_mode"] = "AI_PLAN"; st.rerun()

# ==========================================
# 2. 메인 대시보드
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
t_cols = st.columns(4)
with t_cols[0]: 
    if st.button("📊 AI 기업분석리포트", use_container_width=True, type="primary", key="main_b1"): st.session_state["view_mode"] = "REPORT"; st.rerun()
with t_cols[1]: 
    if st.button("💡 AI 정책자금 매칭", use_container_width=True, type="primary", key="main_b2"): st.session_state["view_mode"] = "MATCHING"; st.rerun()
with t_cols[2]: 
    if st.button("📝 기관별 융자/사업계획서", use_container_width=True, type="primary", key="main_b3"): st.session_state["view_mode"] = "LOAN_PLAN"; st.rerun()
with t_cols[3]: 
    if st.button("📑 AI 사업계획서", use_container_width=True, type="primary", key="main_b4"): st.session_state["view_mode"] = "AI_PLAN"; st.rerun()
st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

GUIDE_STR = "1억=10000으로 입력"

if st.session_state["view_mode"] == "INPUT":
    # --- 1. 기업현황 ---
    st.header("1. 기업현황")
    c1r1 = st.columns([2, 1, 1.5, 1.5])
    with c1r1[0]: st.text_input("기업명", key="in_company_name")
    with c1r1[1]: st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
    with c1r1[2]: st.text_input("사업자번호", placeholder="000-00-00000", key="in_raw_biz_no")
    with c1r1[3]: st.text_input("법인등록번호", placeholder="000000-0000000", key="in_raw_corp_no")

    c1r2 = st.columns([1, 2.5, 1.5])
    with c1r2[0]: st.text_input("사업개시일", placeholder="YYYY.MM.DD", key="in_start_date")
    with c1r2[1]: st.text_input("사업장 주소", key="in_biz_addr")
    with c1r2[2]: st.selectbox("업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")

    c1r3 = st.columns([1, 1, 1, 1])
    with c1r3[0]: st.text_input("사업장 전화번호", placeholder="000-0000-0000", key="in_biz_tel")
    with c1r3[1]: st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
    with c1r3[2]: st.number_input("보증금 (만원)", value=st.session_state.get("in_lease_deposit", None), key="in_lease_deposit", placeholder=GUIDE_STR, step=1)
    with c1r3[3]: st.number_input("월임대료 (만원)", value=st.session_state.get("in_lease_rent", None), key="in_lease_rent", placeholder=GUIDE_STR, step=1)
    
    # 이메일 - 추가사업장 유무 - 정보입력 한 줄 배치
    c1r4 = st.columns([1, 1, 2])
    with c1r4[0]: st.text_input("이메일 주소", placeholder="example@email.com", key="in_email_addr")
    with c1r4[1]: st.radio("추가 사업장 유무", ["무", "유"], horizontal=True, key="in_has_extra_biz")
    with c1r4[2]: st.text_input("추가사업장 정보입력", placeholder="사업장명/사업자등록번호 기재", key="in_extra_biz_info")
    st.markdown("---")

    # --- 2. 대표자 정보 ---
    st.header("2. 대표자 정보")
    c2r1 = st.columns(4)
    with c2r1[0]: st.text_input("대표자명", key="in_rep_name")
    with c2r1[1]: st.text_input("생년월일", placeholder="YYYY.MM.DD", key="in_rep_dob")
    with c2r1[2]: st.text_input("연락처", placeholder="010-0000-0000", key="in_rep_phone")
    with c2r1[3]: st.selectbox("최종학력", ["선택", "중학교 졸업", "고등학교 졸업", "대학교 졸업", "석사 수료", "박사 수료"], key="in_edu_school")
    
    c2r2 = st.columns([2, 1, 2])
    with c2r2[0]: st.text_input("거주지 주소", key="in_home_addr")
    with c2r2[1]: st.radio("거주지 임대여부", ["자가", "임대"], horizontal=True, key="in_home_status")
    with c2r2[2]: st.multiselect("부동산 보유현황", ["아파트", "빌라", "토지", "공장", "임야"], key="in_real_estate")
    st.markdown("---")

    # --- 3. 대표자 신용정보 ---
    st.header("3. 대표자 신용정보")
    c3_col1, c3_col2, c3_col3 = st.columns([1.1, 1.2, 1.8])
    with c3_col1:
        st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
        t_c = st.columns(2); t_c[0].markdown("금융연체 여부"); t_c[1].markdown("세금체납 여부")
        r_c = st.columns(2)
        delinquency = r_c[0].radio("f_d", ["무", "유"], horizontal=True, key="in_fin_delinquency", label_visibility="collapsed")
        tax_delin = r_c[1].radio("t_d", ["무", "유"], horizontal=True, key="in_tax_delinquency", label_visibility="collapsed")
        st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
        s_c = st.columns(2); s_c[0].markdown("KCB 점수"); s_c[1].markdown("NICE 점수")
        r2_c = st.columns(2)
        s_kcb = r2_c[0].number_input("k_i", value=st.session_state.get("in_kcb_score", None), key="in_kcb_score", label_visibility="collapsed", placeholder="점수", step=1)
        s_nice = r2_c[1].number_input("n_i", value=st.session_state.get("in_nice_score", None), key="in_nice_score", label_visibility="collapsed", placeholder="점수", step=1)
    with c3_col2:
        st.markdown("<div style='margin-top:25px;'></div>", unsafe_allow_html=True)
        vk, vn = safe_int(s_kcb), safe_int(s_nice)
        has_issue = (delinquency == "유" or tax_delin == "유")
        low_score = (vk > 0 and vk < 630) or (vn > 0 and vn < 665)
        if has_issue: status, color, text = "🔴 진행 불가", "#FFEBEE", "연체 또는 체납은 조달의 최대 걸림돌입니다."
        elif low_score: status, color, text = "🟡 진행 주의", "#FFF3E0", "신용 점수가 낮아 정밀 심사가 권장됩니다."
        elif vk == 0: status, color, text = "⚪ 대기 중", "#F8F9FA", "정보를 입력하시면 진단이 시작됩니다."
        else: status, color, text = "🟢 진행 원활", "#E8F5E9", "정책자금 조달에 유리한 신용 등급입니다."
        st.markdown(f"<div style='background-color:{color}; padding:20px; border-radius:10px; height:185px;'><p style='font-weight:700;'>금융 상태 요약</p><p style='font-size:1.2em; font-weight:700;'>{status}</p><p>{text}</p></div>", unsafe_allow_html=True)
    with c3_col3:
        v_cols = st.columns(2); kg, kc = get_kcb_info(vk); ng, nc = get_nice_info(vn)
        with v_cols[0]: 
            st.plotly_chart(create_gauge(vk, "KCB Score", kc), use_container_width=True, config={'displayModeBar': False})
            st.markdown(f"<div style='text-align:center; margin-top:-20px; color:{kc}; font-weight:700;'>KCB: {kg}</div>", unsafe_allow_html=True)
        with v_cols[1]: 
            st.plotly_chart(create_gauge(vn, "NICE Score", nc), use_container_width=True, config={'displayModeBar': False})
            st.markdown(f"<div style='text-align:center; margin-top:-20px; color:{nc}; font-weight:700;'>NICE: {ng}</div>", unsafe_allow_html=True)
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

    # --- 5. 기대출 현황 ---
    st.header("5. 기대출 현황")
    debt_items = [("중진공 (만원)", "in_debt_kosme"), ("소진공 (만원)", "in_debt_semas"), ("신보 (만원)", "in_debt_kodit"), ("기보 (만원)", "in_debt_kibo"), ("재단 (만원)", "in_debt_foundation"), ("회사담보 (만원)", "in_debt_corp_coll"), ("대표신용 (만원)", "in_debt_rep_cred"), ("대표담보 (만원)", "in_debt_rep_coll")]
    for row in range(0, 8, 4):
        cols = st.columns(4)
        for i in range(4):
            idx = row + i; title, key = debt_items[idx]
            cols[i].number_input(title, value=st.session_state.get(key, None), key=key, placeholder=GUIDE_STR, step=1)
    st.markdown("---")

    # --- 6. 보유 인증 ---
    st.header("6. 보유 인증")
    cert_list = ["소상공인확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
    for i in range(0, 8, 4):
        cols = st.columns(4)
        for j in range(4):
            if i+j < len(cert_list): cols[j].checkbox(cert_list[i+j], key=f"in_cert_{i+j}")
    st.markdown("---")

    # --- 7. 특허 및 정부지원 ---
    st.header("7. 특허 및 정부지원")
    c7 = st.columns(2)
    with c7[0]:
        st.radio("특허 보유 여부", ["무", "유"], horizontal=True, key="in_has_patent")
        st.number_input("보유 건수", value=st.session_state.get("in_pat_cnt", None), key="in_pat_cnt", step=1)
        st.text_area("특허 상세 내용", key="in_pat_desc")
    with c7[1]:
        st.radio("정부지원 수혜이력", ["무", "유"], horizontal=True, key="in_has_gov")
        st.number_input("수혜 건수", value=st.session_state.get("in_gov_cnt", None), key="in_gov_cnt", step=1)
        st.text_area("수혜 사업명 상세", key="in_gov_desc")
    st.markdown("---")

    # --- 8. 비즈니스 상세 정보 ---
    st.header("8. 비즈니스 상세 정보")
    r8_1 = st.columns(2)
    with r8_1[0]: st.text_area("핵심 아이템", key="in_item_desc", height=100)
    with r8_1[1]: st.text_area("판매 루트(유통망)", key="in_sales_route", height=100)
    r8_2 = st.columns(2)
    with r8_2[0]: st.text_area("경쟁력 및 차별성", key="in_item_diff")
    with r8_2[1]: st.text_area("시장 현황", key="in_market_status")
    r8_3 = st.columns(2)
    with r8_3[0]: st.text_area("제품생산/서비스 공정도", key="in_process_desc")
    with r8_3[1]: st.text_area("구체적인 타겟 고객", key="in_target_cust")
    r8_4 = st.columns(2)
    with r8_4[0]: st.text_area("수익 모델", key="in_revenue_model")
    with r8_4[1]: st.text_area("앞으로의 계획", key="in_future_plan")
    st.markdown("---")

    # --- 9. 자금 계획 ---
    st.header("9. 자금 계획")
    c9 = st.columns([1, 2])
    with c9[0]:
        st.markdown('<p class="blue-bold-label-16">이번 조달 필요 자금 (만원)</p>', unsafe_allow_html=True)
        st.number_input("조달금액", value=st.session_state.get("in_req_funds", None), key="in_req_funds", placeholder=GUIDE_STR, step=1, label_visibility="collapsed")
    with c9[1]:
        st.markdown('<p class="std-label-14">상세 자금 집행 계획</p>', unsafe_allow_html=True)
        st.text_area("자금집행", key="in_fund_plan", placeholder="예: 연구인력 채용(40%) 등", label_visibility="collapsed")

# ==========================================
# 3. 리포트 출력
# ==========================================
else:
    if st.button("⬅️ 입력 화면으로 돌아가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    current_data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
    
    # 뷰 모드별 명칭 매핑
    v_titles = {"REPORT": "AI 기업분석리포트", "MATCHING": "AI 정책자금 매칭 결과", "LOAN_PLAN": "기관별 융자/사업계획서", "AI_PLAN": "AI 사업계획서"}
    mode_name = v_titles.get(st.session_state["view_mode"], "전문 리포트")
    
    st.subheader(f"📊 {current_data.get('in_company_name', '미입력')} - {mode_name}")
    
    with st.status(f"🚀 AI가 전문적인 {mode_name}를 작성 중입니다..."):
        if not st.session_state.get("api_key"): 
            st.error("사이드바에서 API Key를 먼저 저장해 주세요.")
        else:
            genai.configure(api_key=st.session_state["api_key"])
            model = genai.GenerativeModel(get_best_model_name())
            prompt = f"기업 데이터: {current_data} 를 기반으로 {mode_name} 성격에 부합하는 상세 보고서를 작성하라."
            try:
                res = model.generate_content(prompt).text
                st.markdown(res)
            except Exception as e:
                st.error(f"리포트 생성 중 오류 발생: {e}")
