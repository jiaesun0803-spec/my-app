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
# 1. AI 리포트 생성 엔진 (요청하신 8단계 구성)
# ==========================================
def generate_ai_report(api_key, data):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        prompt = f"""
        당신은 대한민국 최고의 기업 컨설턴트입니다. 다음 정보를 바탕으로 전문 '기업분석리포트'를 HTML로 작성하세요.
        [기업정보]
        - 기업명: {data.get('in_company_name')}
        - 업종: {data.get('in_industry')}
        - 주요내용: {data.get('in_item_desc')}
        - 매출: {data.get('in_sales_cur')}만원

        [리포트 구성 순서]
        1. 기업현황분석 (표 형식)
        2. SWOT 분석
        3. 시장현황
        4. 경쟁력 분석 / 주요 경쟁사분석
        5. 핵심 경쟁력 분석
        6. 필요자금 및 자금사용계획
        7. 매출전망 (1년 전망 그래프 포함)
        8. 성장비전 (단기/중기/장기)
        ※ 컨설턴트 코멘트

        [지침]
        - 말투는 반드시 '있음', '함', '임'으로 끝낼 것.
        - 시각적으로 보기 좋게 박스, 표, 색상을 사용할 것.
        - 카테고리별로 페이지가 넘어가게 <div style="page-break-before: always;"></div>를 넣을 것.
        - HTML 코드만 출력할 것.
        """
        response = model.generate_content(prompt)
        return response.text.replace('```html', '').replace('```', '').strip()
    except Exception as e:
        return f"<div style='color:red;'>리포트 생성 오류: {str(e)}</div>"

# ==========================================
# 2. 디자인 및 초기 설정
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

st.markdown("""
<style>
    [data-testid="stWidgetLabel"] p { font-weight: 400 !important; font-size: 14px !important; color: #31333F !important; margin-bottom: 2px !important; }
    h2 { font-weight: 700 !important; margin-top: 25px !important; }
    input::placeholder { font-size: 0.85em !important; color: #888 !important; }
    [data-testid="stCheckbox"] label p { font-size: 18px !important; font-weight: 500 !important; color: #333 !important; }
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
    return f"{s}점", "#EF6C00"

def get_nice_grade(score):
    s = safe_int(score)
    if s >= 900: return "1등급", "#1E88E5"
    elif s >= 840: return "3등급", "#42A5F5"
    return f"{s}점", "#EF6C00"

# ==========================================
# 3. 사이드바 (확정 UI: 수동 저장/불러오기 탭)
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
s_modes = ["REPORT", "MATCHING", "LOAN_PLAN", "AI_PLAN"]
s_labels = ["📊 AI 기업분석리포트", "💡 AI 정책자금 매칭", "📝 기관별 융자/사업계획서", "📑 AI 사업계획서"]
for i in range(4):
    if st.sidebar.button(s_labels[i], key=f"side_{i}", use_container_width=True):
        st.session_state["view_mode"] = s_modes[i]; st.rerun()

# ==========================================
# 4. 메인 대시보드 상단 (확정 탭)
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
t_cols = st.columns(4)
for i in range(4):
    if t_cols[i].button(s_labels[i], key=f"t_{i}", use_container_width=True, type="primary"):
        st.session_state["view_mode"] = s_modes[i]; st.rerun()
st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

GUIDE_STR = "1억=10000으로 입력"

# ==========================================
# 5. 화면 분기 (입력 vs 리포트)
# ==========================================
if st.session_state["view_mode"] == "INPUT":
    # --- 1. 기업현황 (컨펌받은 최종 4층 레이아웃) ---
    st.header("1. 기업현황")
    c1_f1 = st.columns([2, 1, 1.5, 1.5])
    with c1_f1[0]: st.text_input("기업명", key="in_company_name")
    with c1_f1[1]: st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
    with c1_f1[2]: st.text_input("사업자번호", key="in_raw_biz_no", placeholder="000-00-00000")
    with c1_f1[3]: st.text_input("법인등록번호", key="in_raw_corp_no", placeholder="000000-0000000")
    
    c1_f2 = st.columns([1, 1, 1, 1])
    with c1_f2[0]: st.text_input("사업개시일", key="in_start_date", placeholder="YYYY.MM.DD")
    with c1_f2[1]: st.text_input("사업장 전화번호", key="in_biz_tel", placeholder="000-00-0000")
    with c1_f2[2]: st.text_input("이메일 주소", key="in_email_addr", placeholder="example@email.com")
    with c1_f2[3]: st.selectbox("현사업장 업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")
    
    c1_f3 = st.columns([1.2, 3, 0.9, 0.9])
    with c1_f3[0]: st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
    with c1_f3[1]: st.text_input("사업장 주소", key="in_biz_addr", placeholder="소재지를 입력하세요")
    with c1_f3[2]: st.number_input("보증금 (만원)", key="in_lease_deposit", step=1, placeholder=GUIDE_STR, value=None)
    with c1_f3[3]: st.number_input("월임대료 (만원)", key="in_lease_rent", step=1, placeholder=GUIDE_STR, value=None)
    
    c1_f4 = st.columns([1.2, 3, 1.8])
    with c1_f4[0]: st.radio("추가 사업장 여부", ["없음", "있음"], horizontal=True, key="in_has_extra_biz")
    with c1_f4[1]: st.text_input("추가사업장 정보입력", key="in_extra_biz_info", placeholder="사업장명/사업자등록번호")
    with c1_f4[2]: st.empty() 
    st.markdown("---")

    # --- 2. 대표자 정보 ---
    st.header("2. 대표자 정보")
    c2 = st.columns([1, 1, 1, 1])
    with c2[0]: st.text_input("대표자명", key="in_rep_name")
    with c2[1]: st.text_input("생년월일", key="in_rep_dob")
    with c2[2]: st.text_input("연락처", key="in_rep_phone")
    with c2[3]: st.selectbox("통신사", ["선택", "SKT", "KT", "LGU+", "알뜰폰"], key="in_rep_carrier")
    st.markdown("---")

    # --- 3. 대표자 신용정보 (컨펌 디자인) ---
    st.header("3. 대표자 신용정보")
    c3_col1, c3_col2, c3_col3 = st.columns([1.5, 1.3, 1.8])
    with c3_col1:
        l_r1 = st.columns(2)
        l_r1[0].radio("금융연체여부", ["없음", "있음"], horizontal=True, key="in_fin_delinquency")
        l_r1[1].radio("세금체납여부", ["없음", "있음"], horizontal=True, key="in_tax_delinquency")
        l_r2 = st.columns(2)
        s_kcb = l_r2[0].number_input("KCB 점수", key="in_kcb_score", step=1, value=None)
        s_nice = l_r2[1].number_input("NICE 점수", key="in_nice_score", step=1, value=None)
    with c3_col2:
        vk, vn = safe_int(s_kcb), safe_int(s_nice)
        status = "🟢 진행 원활" if vk > 700 else "🟡 진행 주의"
        st.markdown(f'<div class="summary-box-compact"><p style="font-weight:700;">신용상태요약</p><p style="font-size:1.45em; font-weight:800;">{status}</p></div>', unsafe_allow_html=True)
    with c3_col3:
        kg, kc = get_kcb_grade(vk); ng, nc = get_nice_grade(vn)
        res_c1, res_c2 = st.columns(2)
        with res_c1: st.markdown(f'<div class="score-result-box"><p class="result-title">KCB 결과</p><p style="font-size:1.8em; font-weight:800; color:{kc};">{vk}점</p><p>{kg}</p></div>', unsafe_allow_html=True)
        with res_c2: st.markdown(f'<div class="score-result-box"><p class="result-title">NICE 결과</p><p style="font-size:1.8em; font-weight:800; color:{nc};">{vn}점</p><p>{ng}</p></div>', unsafe_allow_html=True)
    st.markdown("---")

    # --- 4. 매출현황 ---
    st.header("4. 매출현황")
    exp_cols = st.columns(2)
    with exp_cols[0]: has_exp = st.radio("수출매출 여부", ["없음", "있음"], horizontal=True, key="in_export_revenue")
    with exp_cols[1]: plan_exp = st.radio("수출예정 여부", ["없음", "있음"], horizontal=True, key="in_planned_export")
    mc = st.columns(4)
    m_keys = [("금년 매출", "in_sales_cur"), ("24년 매출", "in_sales_24")]
    for i, (t, k) in enumerate(m_keys): mc[i].number_input(f"{t} (만원)", key=k, step=1, placeholder=GUIDE_STR, value=None)
    st.markdown("---")

    # --- 6. 보유 인증 ---
    st.header("6. 보유 인증")
    cert_list = ["중소기업확인서(소상공인확인서)", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
    for i in range(0, 8, 4):
        cols = st.columns(4)
        for j in range(4):
            if i+j < len(cert_list): cols[j].checkbox(cert_list[i+j], key=f"in_cert_{i+j}")
    st.markdown("---")

    # --- 8. 비즈니스 상세 정보 ---
    st.header("8. 비즈니스 상세 정보")
    st.text_area("핵심 아이템 및 비즈니스 모델 상세", key="in_item_desc", height=150, placeholder="제품의 기능과 시장 가치를 상세히 적어주세요.")
    st.markdown("---")

    # --- 9. 자금 계획 ---
    st.header("9. 자금 계획")
    c9 = st.columns([1, 2])
    with c9[0]:
        st.markdown('<p class="blue-bold-label-16">조달 필요 자금 (만원)</p>', unsafe_allow_html=True)
        st.number_input("조달금액", key="in_req_funds", label_visibility="collapsed", step=1, placeholder=GUIDE_STR, value=None)
    with c9[1]:
        st.markdown('<p style="font-size:14px;">상세 자금 집행 계획</p>', unsafe_allow_html=True)
        st.text_area("자금집행", key="in_fund_plan", label_visibility="collapsed")

else:
    # --- 리포트 출력 모드 ---
    if st.button("⬅️ 입력 화면으로 돌아가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    
    current_data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
    biz_name = current_data.get("in_company_name", "미입력")
    api_key = st.session_state["settings"].get("api_key", "")
    
    if not api_key: st.error("사이드바에서 API Key를 먼저 저장해 주세요.")
    elif not biz_name or biz_name == "미입력": st.warning("기업명을 입력하고 [저장하기] 탭에서 저장 후 진행하세요.")
    else:
        with st.status(f"🚀 {biz_name} 전문 분석 리포트 생성 중..."):
            res_html = generate_ai_report(api_key, current_data)
            components.html(res_html, height=1500, scrolling=True)
