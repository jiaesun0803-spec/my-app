import streamlit as st
import json
import os
import time
import streamlit.components.v1 as components
import google.generativeai as genai

# ==========================================
# 0. 데이터 보존 및 세션 초기화 (가장 중요)
# ==========================================
SETTINGS_FILE = "settings.json"
DATA_FILE = "companies_data.json"

# 모든 입력 필드의 Key 리스트 (데이터 유실 방지용)
INPUT_FIELDS = [
    "in_company_name", "in_biz_type", "in_raw_biz_no", "in_raw_corp_no",
    "in_start_date", "in_biz_tel", "in_email_addr", "in_industry",
    "in_lease_status", "in_biz_addr", "in_lease_deposit", "in_lease_rent",
    "in_has_extra_biz", "in_extra_biz_info", "in_rep_name", "in_rep_dob",
    "in_rep_phone", "in_rep_carrier", "in_home_addr", "in_home_status",
    "in_real_estate", "in_edu_level", "in_rep_major", "in_rep_career_1",
    "in_rep_career_2", "in_fin_delinquency", "in_tax_delinquency",
    "in_kcb_score", "in_nice_score", "in_export_revenue", "in_planned_export",
    "in_sales_cur", "in_sales_25", "in_sales_24", "in_sales_23",
    "in_exp_cur", "in_exp_25", "in_exp_24", "in_exp_23",
    "in_has_patent", "in_pat_cnt", "in_pat_desc", "in_has_gov",
    "in_gov_cnt", "in_gov_desc", "in_item_desc", "in_sales_route",
    "in_item_diff", "in_market_status", "in_process_desc", "in_target_cust",
    "in_revenue_model", "in_future_plan", "in_req_funds", "in_fund_plan"
]

# 체크박스(인증)를 위한 별도 리스트
CERT_KEYS = [f"in_cert_{i}" for i in range(8)]

# 세션 상태 초기화 (화면 전환 시 데이터 유실 방지의 핵심)
for field in INPUT_FIELDS + CERT_KEYS:
    if field not in st.session_state:
        st.session_state[field] = "" if "cnt" not in field and "score" not in field and "deposit" not in field else None

# 파일 로드/저장 함수
def load_json(file_path, default):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f: return json.load(f)
        except: return default
    return default

def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ==========================================
# 1. AI 리포트 생성 엔진
# ==========================================
def generate_ai_report(api_key, data, mode, style="문서형"):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        style_inst = "관공서/은행 제출용 전문 표 형식 리포트" if style == "문서형" else "카드형 레이아웃의 프리미엄 랜딩페이지 리포트"
        prompts = {
            "REPORT": "경영 분석 및 시장 경쟁력 리포트",
            "MATCHING": "정책자금 매칭 리포트",
            "LOAN_PLAN": "기관 제출용 사업계획서 요약",
            "AI_PLAN": "신규 아이템 비전 사업계획서"
        }
        
        # 데이터 수집
        summary = "\n".join([f"{k}: {v}" for k, v in data.items() if v])
        
        final_prompt = f"""
        당신은 기업 컨설턴트입니다. 다음 정보를 바탕으로 {style_inst}의 HTML 리포트를 작성하세요.
        [기업정보]\n{summary}
        [주제] {prompts.get(mode)}
        - 전문적인 CSS와 신뢰감 있는 톤을 유지하세요.
        - HTML 코드만 출력하세요.
        """
        response = model.generate_content(final_prompt)
        return response.text.replace('```html', '').replace('```', '').strip()
    except Exception as e:
        return f"<div style='color:red; padding:20px;'>AI 엔진 오류: {str(e)}</div>"

# ==========================================
# 2. 디자인 및 사이드바 (복구)
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")
st.markdown("""
<style>
    [data-testid="stWidgetLabel"] p { font-weight: 400; font-size: 14px; }
    h2 { font-weight: 700; margin-top: 20px; border-left: 5px solid #1E88E5; padding-left: 10px; }
    [data-testid="stCheckbox"] label p { font-size: 18px !important; font-weight: 500; }
    .score-result-box { background-color: #F1F8E9; padding: 15px; border-radius: 10px; border: 1px solid #C8E6C9; text-align: center; }
</style>
""", unsafe_allow_html=True)

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
if "settings" not in st.session_state: st.session_state["settings"] = load_json(SETTINGS_FILE, {"api_key": ""})
if "company_list" not in st.session_state: st.session_state["company_list"] = load_json(DATA_FILE, {})
if "edit_api_key" not in st.session_state: st.session_state["edit_api_key"] = False

# [사이드바 - API 설정]
st.sidebar.header("⚙️ AI 엔진 설정")
saved_key = st.session_state["settings"].get("api_key", "")
if saved_key and not st.session_state["edit_api_key"]:
    st.sidebar.success("✅ API Key 저장됨")
    if st.sidebar.button("🔄 API Key 변경"): st.session_state["edit_api_key"] = True; st.rerun()
else:
    new_key = st.sidebar.text_input("Gemini API Key", value=saved_key, type="password")
    if st.sidebar.button("💾 영구 저장"):
        save_json(SETTINGS_FILE, {"api_key": new_key}); st.session_state["settings"]["api_key"] = new_key
        st.session_state["edit_api_key"] = False; st.rerun()

# [사이드바 - 업체 관리]
st.sidebar.markdown("---")
st.sidebar.header("📁 업체 관리")
t_s, t_l = st.sidebar.tabs(["💾 저장", "📂 불러오기"])
with t_s:
    if st.button("현재 정보 파일 저장", use_container_width=True):
        name = st.session_state.in_company_name.strip()
        if name:
            st.session_state["company_list"][name] = {k: st.session_state[k] for k in INPUT_FIELDS + CERT_KEYS}
            save_json(DATA_FILE, st.session_state["company_list"])
            st.success(f"'{name}' 저장 완료!")
        else: st.error("기업명을 입력하세요.")
with t_l:
    if st.session_state["company_list"]:
        target = st.selectbox("선택", list(st.session_state["company_list"].keys()))
        if st.button("데이터 불러오기", use_container_width=True):
            for k, v in st.session_state["company_list"][target].items(): st.session_state[k] = v
            st.rerun()

# [사이드바 - 리포트 탭 복구]
st.sidebar.markdown("---")
st.sidebar.header("🚀 리포트 생성")
s_labels = ["📊 AI 기업분석리포트", "💡 AI 정책자금 매칭", "📝 융자/사업계획서", "📑 AI 사업계획서"]
s_modes = ["REPORT", "MATCHING", "LOAN_PLAN", "AI_PLAN"]
for i in range(4):
    if st.sidebar.button(s_labels[i], key=f"side_{i}", use_container_width=True):
        st.session_state["view_mode"] = s_modes[i]; st.rerun()

# ==========================================
# 3. 메인 레이아웃 및 입력 섹션
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
t_cols = st.columns(4)
for i in range(4):
    if t_cols[i].button(s_labels[i], key=f"top_{i}", use_container_width=True, type="primary"):
        st.session_state["view_mode"] = s_modes[i]; st.rerun()
st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

if st.session_state["view_mode"] == "INPUT":
    # --- 1. 기업현황 (4층 고정) ---
    st.header("1. 기업현황")
    c1 = st.columns([2, 1, 1.5, 1.5])
    c1[0].text_input("기업명", key="in_company_name")
    c1[1].radio("사업자유형", ["개인", "법인"], key="in_biz_type", horizontal=True)
    c1[2].text_input("사업자번호", key="in_raw_biz_no", placeholder="000-00-00000")
    c1[3].text_input("법인등록번호", key="in_raw_corp_no", placeholder="000000-0000000")
    
    c2 = st.columns([1, 1, 1, 1])
    c2[0].text_input("사업개시일", key="in_start_date", placeholder="YYYY.MM.DD")
    c2[1].text_input("사업장 전화번호", key="in_biz_tel", placeholder="000-00-0000")
    c2[2].text_input("이메일 주소", key="in_email_addr")
    c2[3].selectbox("현사업장 업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")
    
    c3 = st.columns([1.2, 3, 0.9, 0.9])
    c3[0].radio("사업장 임대여부", ["자가", "임대"], key="in_lease_status", horizontal=True)
    c3[1].text_input("사업장 주소", key="in_biz_addr")
    c3[2].number_input("보증금(만원)", key="in_lease_deposit", value=None)
    c3[3].number_input("월임대료(만원)", key="in_lease_rent", value=None)
    
    c4 = st.columns([1.2, 3, 1.8])
    c4[0].radio("추가 사업장 여부", ["없음", "있음"], key="in_has_extra_biz", horizontal=True)
    c4[1].text_input("추가사업장 정보입력", key="in_extra_biz_info")
    c4[2].empty()

    # --- 3. 대표자 신용정보 ---
    st.markdown("---")
    st.header("3. 대표자 신용정보")
    cc1, cc2, cc3 = st.columns([1.5, 1.3, 1.8])
    with cc1:
        r1 = st.columns(2)
        r1[0].radio("금융연체", ["없음", "있음"], key="in_fin_delinquency", horizontal=True)
        r1[1].radio("세금체납", ["없음", "있음"], key="in_tax_delinquency", horizontal=True)
        r2 = st.columns(2)
        sk = r2[0].number_input("KCB", key="in_kcb_score", value=None)
        sn = r2[1].number_input("NICE", key="in_nice_score", value=None)
    with cc2:
        vk = (sk or 0)
        st.markdown(f'<div style="text-align:center; padding:20px; background:#E3F2FD; border-radius:10px;">신용상태: <b>{"🟢 양호" if vk > 700 else "🟡 주의"}</b></div>', unsafe_allow_html=True)
    with cc3:
        st.markdown(f'<div class="score-result-box">KCB: {sk or 0}점 / NICE: {sn or 0}점</div>', unsafe_allow_html=True)

    # --- 4. 매출 및 수출매출 (완벽 복구) ---
    st.markdown("---")
    st.header("4. 매출 및 수출현황")
    ec = st.columns(2)
    with ec[0]: has_exp = st.radio("수출매출 여부", ["없음", "있음"], key="in_export_revenue", horizontal=True)
    with ec[1]: plan_exp = st.radio("수출예정 여부", ["없음", "있음"], key="in_planned_export", horizontal=True)
    
    st.write("**[매출 정보 (만원)]**")
    m_cols = st.columns(4)
    m_cols[0].number_input("금년 매출", key="in_sales_cur", value=None)
    m_cols[1].number_input("25년 매출", key="in_sales_25", value=None)
    m_cols[2].number_input("24년 매출", key="in_sales_24", value=None)
    m_cols[3].number_input("23년 매출", key="in_sales_23", value=None)
    
    if has_exp == "있음":
        st.write("**[수출 상세역사 (만원)]**")
        e_cols = st.columns(4)
        e_cols[0].number_input("금년 수출", key="in_exp_cur", value=None)
        e_cols[1].number_input("25년 수출", key="in_exp_25", value=None)
        e_cols[2].number_input("24년 수출", key="in_exp_24", value=None)
        e_cols[3].number_input("23년 수출", key="in_exp_23", value=None)

    # --- 6. 보유 인증 ---
    st.markdown("---")
    st.header("6. 보유 인증")
    c_list = ["중소기업확인서(소상공인확인서)", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
    for i in range(0, 8, 4):
        cols = st.columns(4)
        for j in range(4): cols[j].checkbox(c_list[i+j], key=f"in_cert_{i+j}")

    # --- 8. 비즈니스 상세 정보 (복구) ---
    st.markdown("---")
    st.header("8. 비즈니스 상세 정보")
    b1 = st.columns(2)
    b1[0].text_area("핵심 아이템", key="in_item_desc", height=100)
    b1[1].text_area("판매 루트", key="in_sales_route", height=100)
    b2 = st.columns(2)
    b2[0].text_area("경쟁력", key="in_item_diff", height=100)
    b2[1].text_area("시장 현황", key="in_market_status", height=100)
    b3 = st.columns(2)
    b3[0].text_area("공정도", key="in_process_desc", height=100)
    b3[1].text_area("타겟 고객", key="in_target_cust", height=100)

    # --- 9. 자금 계획 ---
    st.markdown("---")
    st.header("9. 자금 계획")
    c9 = st.columns([1, 2])
    c9[0].number_input("조달금액(만원)", key="in_req_funds", value=None)
    c9[1].text_area("집행 계획", key="in_fund_plan")

# ==========================================
# 4. 리포트 모드 (데이터 즉시 인식)
# ==========================================
else:
    cb1, cb2 = st.columns([6, 2])
    if cb1.button("⬅️ 입력 화면으로 돌아가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    r_style = cb2.selectbox("스타일", ["문서형", "랜딩페이지형"])

    api_key = st.session_state["settings"].get("api_key", "")
    # [핵심 로직] 세션에서 실시간 데이터를 즉시 긁어옴
    current_data = {k: st.session_state[k] for k in INPUT_FIELDS + CERT_KEYS}
    biz_name = st.session_state.in_company_name.strip()

    if not api_key: st.error("API Key를 저장하세요.")
    elif not biz_name: 
        st.warning("⚠️ 기업명이 없습니다. 입력 화면에서 기업명을 먼저 써주세요.")
        if st.button("입력하러 가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    else:
        with st.status(f"🚀 {biz_name} 리포트 분석 중..."):
            res_html = generate_ai_report(api_key, current_data, st.session_state["view_mode"], r_style)
            components.html(res_html, height=1200, scrolling=True)
