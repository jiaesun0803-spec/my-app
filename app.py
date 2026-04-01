import streamlit as st
import json
import os
import time
import streamlit.components.v1 as components
import google.generativeai as genai

# ==========================================
# 0. 파일 데이터 관리 및 영구 저장 시스템
# ==========================================
SETTINGS_FILE = "settings.json"
DATA_FILE = "companies_data.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {"api_key": ""}
    return {"api_key": ""}

def save_settings(api_key):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_key": api_key}, f, ensure_ascii=False, indent=4)

def load_companies():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

def save_companies(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ==========================================
# 1. AI 리포트 생성 통합 엔진 (404 에러 완벽 차단)
# ==========================================
def generate_ai_report(api_key, data, mode):
    """
    모든 리포트 생성을 담당하는 통합 함수.
    모델명을 'gemini-1.5-flash-latest'로 고정하여 오류를 방지합니다.
    """
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        # 리포트 종류에 따른 프롬프트 설정
        prompts = {
            "REPORT": "이 기업의 시장 경쟁력과 성장 가능성을 분석한 전문 경영 리포트를 HTML 형식으로 작성해줘.",
            "MATCHING": "이 기업의 조건(업종, 매출, 부채 등)에 가장 적합한 정부지원 정책자금 3가지를 매칭하여 리포트해줘.",
            "LOAN_PLAN": "금융권 융자 및 기관 제출용 사업계획서의 핵심 요약본을 전문적인 톤으로 작성해줘.",
            "AI_PLAN": "이 기업의 신규 사업 아이템을 기반으로 한 미래 비전 사업계획서를 HTML 형식으로 작성해줘."
        }
        
        base_prompt = f"""
        [기업 정보]
        - 기업명: {data.get('in_company_name')}
        - 업종: {data.get('in_industry')}
        - 매출: {data.get('in_sales_cur')}만원
        - 주요내용: {data.get('in_item_desc', '내용없음')}
        
        [요청사항]
        {prompts.get(mode)}
        - 반드시 시각적으로 보기 좋은 HTML/CSS 스타일을 포함할 것.
        - 전문 컨설턴트의 어조를 유지할 것.
        """
        
        response = model.generate_content(base_prompt)
        return response.text.replace('```html', '').replace('```', '')
    except Exception as e:
        return f"<div style='color:red; padding:20px;'>AI 분석 중 오류 발생: {str(e)}</div>"

# ==========================================
# 2. 초기 설정 및 디자인 커스텀
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

st.markdown("""
<style>
    [data-testid="stWidgetLabel"] p { font-weight: 400 !important; font-size: 14px !important; color: #31333F !important; margin-bottom: 2px !important; }
    h2 { font-weight: 700 !important; margin-top: 25px !important; }
    input::placeholder { font-size: 0.85em !important; color: #888 !important; }
    .summary-box-compact { background-color: #E8F5E9; padding: 12px; border-radius: 10px; height: 145px; border: 1px solid #ddd; text-align: center; display: flex; flex-direction: column; justify-content: center; margin-top: 25px; }
    .score-result-box { background-color: #F1F8E9; padding: 12px; border-radius: 10px; height: 145px; border: 1px solid #C8E6C9; text-align: center; display: flex; flex-direction: column; justify-content: center; margin-top: 25px; }
    .result-title { font-size: 18px !important; font-weight: 700 !important; color: #2E7D32; margin-bottom: 5px !important; }
    .blue-bold-label-16 { color: #1E88E5 !important; font-size: 16px !important; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
if "settings" not in st.session_state: st.session_state["settings"] = load_settings()
if "company_list" not in st.session_state: st.session_state["company_list"] = load_companies()
if "edit_api_key" not in st.session_state: st.session_state["edit_api_key"] = False

def safe_int(value):
    try: return int(float(str(value).replace(',', '').strip())) if value else 0
    except: return 0

def get_kcb_grade(score):
    s = safe_int(score)
    if s >= 942: return "1등급", "#43A047"
    elif s >= 832: return "3등급", "#66BB6A"
    elif s >= 630: return "6등급", "#EF6C00"
    else: return f"{s}점(등급외)", "#E53935"

def get_nice_grade(score):
    s = safe_int(score)
    if s >= 900: return "1등급", "#1E88E5"
    elif s >= 840: return "3등급", "#42A5F5"
    elif s >= 665: return "6등급", "#EF6C00"
    else: return f"{s}점(등급외)", "#E53935"

# ==========================================
# 3. 사이드바 (업체 관리 및 리포트 탭)
# ==========================================
st.sidebar.header("⚙️ AI 엔진 설정")
saved_key = st.session_state["settings"].get("api_key", "")

if saved_key and not st.session_state["edit_api_key"]:
    st.sidebar.success("✅ API Key 영구 저장됨")
    if st.sidebar.button("🔄 API Key 변경"):
        st.session_state["edit_api_key"] = True; st.rerun()
else:
    new_key = st.sidebar.text_input("Gemini API Key 입력", value=saved_key, type="password")
    if st.sidebar.button("💾 영구 저장"):
        save_settings(new_key); st.session_state["settings"]["api_key"] = new_key
        st.session_state["edit_api_key"] = False; st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("📁 업체 관리")
tab_save, tab_load = st.sidebar.tabs(["💾 저장하기", "📂 불러오기"])

with tab_save:
    if st.button("현재 정보 저장", use_container_width=True):
        c_name = st.session_state.get("in_company_name", "").strip()
        if c_name:
            current_data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
            st.session_state["company_list"][c_name] = current_data
            save_companies(st.session_state["company_list"])
            st.success(f"'{c_name}' 저장 완료!")
        else: st.error("기업명을 입력하세요.")

with tab_load:
    if st.session_state["company_list"]:
        target = st.selectbox("업체 선택", options=list(st.session_state["company_list"].keys()))
        if st.button("데이터 불러오기", use_container_width=True):
            loaded = st.session_state["company_list"][target]
            for k, v in loaded.items(): st.session_state[k] = v
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🚀 리포트 생성")
if st.sidebar.button("📊 AI 기업분석리포트", use_container_width=True): st.session_state["view_mode"] = "REPORT"; st.rerun()
if st.sidebar.button("💡 AI 정책자금 매칭", use_container_width=True): st.session_state["view_mode"] = "MATCHING"; st.rerun()
if st.sidebar.button("📝 기관별 융자/사업계획서", use_container_width=True): st.session_state["view_mode"] = "LOAN_PLAN"; st.rerun()
if st.sidebar.button("📑 AI 사업계획서", use_container_width=True): st.session_state["view_mode"] = "AI_PLAN"; st.rerun()

# ==========================================
# 4. 메인 화면 구성
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
t_cols = st.columns(4)
v_modes = ["REPORT", "MATCHING", "LOAN_PLAN", "AI_PLAN"]
v_labels = ["📊 AI 기업분석리포트", "💡 AI 정책자금 매칭", "📝 기관별 융자/사업계획서", "📑 AI 사업계획서"]
for i in range(4):
    if t_cols[i].button(v_labels[i], key=f"t_{i}", use_container_width=True, type="primary"):
        st.session_state["view_mode"] = v_modes[i]; st.rerun()
st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

GUIDE_STR = "1억=10000으로 입력"

if st.session_state["view_mode"] == "INPUT":
    # --- 1. 기업현황 (요청하신 4층 정렬 복구) ---
    st.header("1. 기업현황")
    c1_f1 = st.columns([2, 1, 1.5, 1.5])
    with c1_f1[0]: st.text_input("기업명", key="in_company_name")
    with c1_f1[1]: st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
    with c1_f1[2]: st.text_input("사업자번호", key="in_raw_biz_no", placeholder="000-00-00000")
    with c1_f1[3]: st.text_input("법인등록번호", key="in_raw_corp_no", placeholder="000000-0000000")
    
    c1_f2 = st.columns([1, 1, 1])
    with c1_f2[0]: st.text_input("사업개시일", key="in_start_date", placeholder="YYYY.MM.DD")
    with c1_f2[1]: st.text_input("사업장 전화번호", key="in_biz_tel", placeholder="000-00-0000")
    with c1_f2[2]: st.text_input("이메일 주소", key="in_email_addr", placeholder="example@email.com")
    
    c1_f3 = st.columns([1.2, 3, 0.9, 0.9])
    with c1_f3[0]: st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
    with c1_f3[1]: st.text_input("사업장 주소", key="in_biz_addr", placeholder="소재지를 입력하세요")
    with c1_f3[2]: st.number_input("보증금 (만원)", key="in_lease_deposit", step=1, placeholder=GUIDE_STR, value=None)
    with c1_f3[3]: st.number_input("월임대료 (만원)", key="in_lease_rent", step=1, placeholder=GUIDE_STR, value=None)
    
    c1_f4 = st.columns([1.2, 3, 1.8])
    with c1_f4[0]: st.radio("추가 사업장 여부", ["없음", "있음"], horizontal=True, key="in_has_extra_biz")
    with c1_f4[1]: st.text_input("추가사업장 정보입력", key="in_extra_biz_info", placeholder="사업장명/사업자등록번호")
    with c1_f4[2]: st.selectbox("현 사업장 업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")
    st.markdown("---")

    # --- 2. 대표자 정보 ---
    st.header("2. 대표자 정보")
    c2r1 = st.columns([1, 1, 1, 1])
    with c2r1[0]: st.text_input("대표자명", key="in_rep_name")
    with c2r1[1]: st.text_input("생년월일", key="in_rep_dob")
    with c2r1[2]: st.text_input("연락처", key="in_rep_phone")
    with c2r1[3]: st.selectbox("통신사", ["선택", "SKT", "KT", "LGU+", "알뜰폰"], key="in_rep_carrier")
    st.markdown("---")

    # --- 3. 대표자 신용정보 ---
    st.header("3. 대표자 신용정보")
    c3_c1, c3_c2, c3_c3 = st.columns([1.5, 1.3, 1.8])
    with c3_c1:
        s_kcb = st.number_input("KCB 점수", key="in_kcb_score", step=1, value=None)
        s_nice = st.number_input("NICE 점수", key="in_nice_score", step=1, value=None)
    with c3_c2:
        vk, vn = safe_int(s_kcb), safe_int(s_nice)
        status = "🟢 진행 원활" if vk > 700 else "🟡 진행 주의"
        st.markdown(f'<div class="summary-box-compact"><p>신용요약</p><h3>{status}</h3></div>', unsafe_allow_html=True)
    with c3_c3:
        kg, kc = get_kcb_grade(vk); ng, nc = get_nice_grade(vn)
        st.markdown(f'<div class="score-result-box"><p>KCB: {vk}점 ({kg})</p><p>NICE: {vn}점 ({ng})</p></div>', unsafe_allow_html=True)
    st.markdown("---")

    # --- 4. 매출현황 ---
    st.header("4. 매출현황")
    exp_c1, exp_c2 = st.columns(2)
    with exp_c1: has_exp = st.radio("수출매출 여부", ["없음", "있음"], horizontal=True, key="in_export_revenue")
    mc = st.columns(4)
    m_keys = [("금년 매출", "in_sales_cur"), ("25년 매출", "in_sales_25"), ("24년 매출", "in_sales_24"), ("23년 매출", "in_sales_23")]
    for i, (t, k) in enumerate(m_keys): mc[i].number_input(f"{t} (만원)", key=k, step=1, value=None)
    if has_exp == "있음":
        st.markdown("<p style='font-size:14px; font-weight:600;'>[수출매출 상세역사 복구됨]</p>", unsafe_allow_html=True)
        ec = st.columns(4)
        e_keys = [("금년 수출액", "in_exp_cur"), ("25년 수출액", "in_exp_25"), ("24년 수출액", "in_exp_24"), ("23년 수출액", "in_exp_23")]
        for i, (t, k) in enumerate(e_keys): ec[i].number_input(f"{t} (만원)", key=k, step=1, value=None)
    st.markdown("---")

    # --- 8. 비즈니스 상세 정보 (복구됨) ---
    st.header("8. 비즈니스 상세 정보")
    r8_1 = st.columns(2)
    with r8_1[0]: st.text_area("핵심 아이템", key="in_item_desc", height=100)
    with r8_1[1]: st.text_area("판매 루트(유통망)", key="in_sales_route", height=100)
    r8_2 = st.columns(2)
    with r8_2[0]: st.text_area("경쟁력 및 차별성", key="in_item_diff", height=100)
    with r8_2[1]: st.text_area("시장 현황", key="in_market_status", height=100)
    st.markdown("---")

    # --- 9. 자금 계획 ---
    st.header("9. 자금 계획")
    st.number_input("조달금액 (만원)", key="in_req_funds", step=1, value=None)
    st.text_area("자금집행 계획", key="in_fund_plan")

else:
    # --- 리포트 출력 모드 ---
    if st.button("⬅️ 입력 화면으로 돌아가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    
    current_data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
    mode = st.session_state["view_mode"]
    biz_name = current_data.get("in_company_name", "미입력")
    api_key = st.session_state["settings"].get("api_key", "")
    
    if not api_key: st.error("사이드바에서 API Key를 먼저 저장해 주세요.")
    elif not biz_name or biz_name == "미입력": st.warning("기업 정보를 입력하고 불러오기 탭에서 선택해 주세요.")
    else:
        with st.status(f"🚀 AI 리포트 생성 중..."):
            res_html = generate_ai_report(api_key, current_data, mode)
            components.html(res_html, height=1200, scrolling=True)
