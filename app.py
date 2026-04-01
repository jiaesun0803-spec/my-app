import streamlit as st
import json
import os
import time
import streamlit.components.v1 as components

# [엔진 연결]
import engine_analysis
import engine_matching
import engine_loan
import engine_ai_plan

# ==========================================
# 0. 파일 데이터 관리 및 자동 저장 로직
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

def auto_save():
    """입력 즉시 파일에 자동 저장"""
    current_data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
    c_name = st.session_state.get("in_company_name", "").strip()
    if c_name:
        st.session_state["company_list"][c_name] = current_data
        save_companies(st.session_state["company_list"])

# ==========================================
# 1. 초기 설정 및 디자인 커스텀
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

st.markdown("""
<style>
    [data-testid="stWidgetLabel"] p { font-weight: 400 !important; font-size: 14px !important; color: #31333F !important; margin-bottom: 2px !important; }
    h2 { font-weight: 700 !important; margin-top: 25px !important; }
    input::placeholder { font-size: 0.85em !important; color: #888 !important; }
    input::-webkit-outer-spin-button, input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    div[data-testid="stHorizontalRadio"] div[role="radiogroup"] > label { min-width: 85px !important; margin-right: 0px !important; }
    .summary-box-compact { background-color: #E8F5E9; padding: 12px; border-radius: 10px; height: 145px; border: 1px solid #ddd; text-align: center; display: flex; flex-direction: column; justify-content: center; margin-top: 25px; }
    .score-result-box { background-color: #F1F8E9; padding: 12px; border-radius: 10px; height: 145px; border: 1px solid #C8E6C9; text-align: center; display: flex; flex-direction: column; justify-content: center; margin-top: 25px; }
    .result-title { font-size: 18px !important; font-weight: 700 !important; color: #2E7D32; margin-bottom: 5px !important; }
    [data-testid="stCheckbox"] label p { font-size: 16px !important; font-weight: 450 !important; }
    .blue-bold-label-16 { color: #1E88E5 !important; font-size: 16px !important; font-weight: 700 !important; display: inline-block; margin-bottom: 12px !important; }
    input::placeholder, textarea::placeholder { color: #aaa !important; font-size: 0.85em !important; }
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
# 2. 사이드바 (API Key 영구 저장 및 업체 불러오기)
# ==========================================
st.sidebar.header("⚙️ AI 엔진 설정")
saved_key = st.session_state["settings"].get("api_key", "")

if saved_key and not st.session_state["edit_api_key"]:
    st.sidebar.success("✅ API Key 영구 저장됨")
    if st.sidebar.button("🔄 API Key 변경"):
        st.session_state["edit_api_key"] = True
        st.rerun()
else:
    new_key = st.sidebar.text_input("Gemini API Key 입력", value=saved_key, type="password")
    if st.sidebar.button("💾 영구 저장"):
        save_settings(new_key)
        st.session_state["settings"]["api_key"] = new_key
        st.session_state["edit_api_key"] = False
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("📁 저장된 업체 불러오기")
if st.session_state["company_list"]:
    target = st.sidebar.selectbox("업체 선택", options=["목록 선택"] + list(st.session_state["company_list"].keys()))
    if st.sidebar.button("📂 데이터 불러오기", use_container_width=True):
        if target != "목록 선택":
            loaded = st.session_state["company_list"][target]
            for k, v in loaded.items(): st.session_state[k] = v
            st.rerun()
else:
    st.sidebar.write("저장된 업체가 없습니다.")

st.sidebar.markdown("---")
st.sidebar.header("🚀 리포트 생성")
if st.sidebar.button("📊 AI 기업분석리포트", use_container_width=True): st.session_state["view_mode"] = "REPORT"; st.rerun()
if st.sidebar.button("💡 AI 정책자금 매칭", use_container_width=True): st.session_state["view_mode"] = "MATCHING"; st.rerun()
if st.sidebar.button("📝 기관별 융자/사업계획서", use_container_width=True): st.session_state["view_mode"] = "LOAN_PLAN"; st.rerun()
if st.sidebar.button("📑 AI 사업계획서", use_container_width=True): st.session_state["view_mode"] = "AI_PLAN"; st.rerun()

# ==========================================
# 3. 메인 대시보드 상단 (고정 탭)
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
t_cols = st.columns(4)
v_modes = ["REPORT", "MATCHING", "LOAN_PLAN", "AI_PLAN"]
v_labels = ["📊 AI 기업분석리포트", "💡 AI 정책자금 매칭", "📝 기관별 융자/사업계획서", "📑 AI 사업계획서"]

for i in range(4):
    if t_cols[i].button(v_labels[i], key=f"tab_{i}", use_container_width=True, type="primary"):
        st.session_state["view_mode"] = v_modes[i]; st.rerun()
st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

GUIDE_STR = "1억=10000으로 입력"

# ==========================================
# 4. 화면 분기 (입력 vs 리포트)
# ==========================================
if st.session_state["view_mode"] == "INPUT":
    # --- 1. 기업현황 (요청하신 4층 구조 적용) ---
    st.header("1. 기업현황")
    
    # 1층 - 기업명, 사업자유형, 사업자번호, 법인등록번호
    c1_f1 = st.columns([2, 1, 1.5, 1.5])
    with c1_f1[0]: st.text_input("기업명", key="in_company_name", placeholder="업체명을 입력하세요", on_change=auto_save)
    with c1_f1[1]: st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type", on_change=auto_save)
    with c1_f1[2]: st.text_input("사업자번호", key="in_raw_biz_no", placeholder="000-00-00000", on_change=auto_save)
    with c1_f1[3]: st.text_input("법인등록번호", key="in_raw_corp_no", placeholder="000000-0000000", on_change=auto_save)
    
    # 2층 - 사업개시일, 사업장 전화번호, 이메일주소
    c1_f2 = st.columns([1, 1, 1])
    with c1_f2[0]: st.text_input("사업개시일", key="in_start_date", placeholder="YYYY.MM.DD", on_change=auto_save)
    with c1_f2[1]: st.text_input("사업장 전화번호", key="in_biz_tel", placeholder="000-00-0000", on_change=auto_save)
    with c1_f2[2]: st.text_input("이메일 주소", key="in_email_addr", placeholder="example@email.com", on_change=auto_save)
    
    # 3층 - 사업장주소, 사업장 임대여부, 보증금, 월임대료
    c1_f3 = st.columns([2, 1, 1, 1])
    with c1_f3[0]: st.text_input("사업장 주소", key="in_biz_addr", placeholder="소재지를 입력하세요", on_change=auto_save)
    with c1_f3[1]: st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status", on_change=auto_save)
    with c1_f3[2]: st.number_input("보증금 (만원)", key="in_lease_deposit", step=1, placeholder=GUIDE_STR, value=None, on_change=auto_save)
    with c1_f3[3]: st.number_input("월임대료 (만원)", key="in_lease_rent", step=1, placeholder=GUIDE_STR, value=None, on_change=auto_save)
    
    # 4층 - 업종, 추가사업장 여부, 추가사업장 정보입력
    c1_f4 = st.columns([1, 1, 2])
    with c1_f4[0]: st.selectbox("업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry", on_change=auto_save)
    with c1_f4[1]: st.radio("추가 사업장 여부", ["없음", "있음"], horizontal=True, key="in_has_extra_biz", on_change=auto_save)
    with c1_f4[2]: st.text_input("추가사업장 정보입력", key="in_extra_biz_info", placeholder="사업장명/사업자등록번호", on_change=auto_save)
    
    st.markdown("---")

    # --- 2. 대표자 정보 ---
    st.header("2. 대표자 정보")
    c2r1 = st.columns([1, 1, 1, 1])
    with c2r1[0]: st.text_input("대표자명", key="in_rep_name", placeholder="성명 입력", on_change=auto_save)
    with c2r1[1]: st.text_input("생년월일", key="in_rep_dob", placeholder="YYYY.MM.DD", on_change=auto_save)
    with c2r1[2]: st.text_input("연락처", key="in_rep_phone", placeholder="010-0000-0000", on_change=auto_save)
    with c2r1[3]: st.selectbox("통신사", ["선택", "SKT", "KT", "LGU+", "알뜰폰"], key="in_rep_carrier", on_change=auto_save)
    c2r2 = st.columns([2, 1, 1]) 
    with c2r2[0]: st.text_input("거주지 주소", key="in_home_addr", placeholder="거주지 주소", on_change=auto_save)
    with c2r2[1]: st.radio("거주지 상태", ["자가", "임대"], horizontal=True, key="in_home_status", on_change=auto_save)
    with c2r2[2]: st.multiselect("부동산 보유현황", ["아파트", "빌라", "토지", "공장", "임야"], key="in_real_estate", on_change=auto_save)
    c2r3 = st.columns([0.8, 0.8, 1.2, 1.2]) 
    with c2r3[0]: st.selectbox("최종학력", ["선택", "중졸", "고졸", "대졸", "석사", "박사"], key="in_edu_level", on_change=auto_save)
    with c2r3[1]: st.text_input("전공", key="in_rep_major", placeholder="전공명", on_change=auto_save)
    with c2r3[2]: st.text_input("경력사항 1", key="in_rep_career_1", placeholder="주요 경력", on_change=auto_save)
    with c2r3[3]: st.text_input("경력사항 2", key="in_rep_career_2", placeholder="기타 경력", on_change=auto_save)
    st.markdown("---")

    # --- 3. 대표자 신용정보 ---
    st.header("3. 대표자 신용정보")
    c3_col1, c3_col2, c3_col3 = st.columns([1.5, 1.3, 1.8])
    with c3_col1:
        l_r1_c1, l_r1_c2 = st.columns(2)
        with l_r1_c1: st.radio("금융연체여부", ["없음", "있음"], horizontal=True, key="in_fin_delinquency", on_change=auto_save)
        with l_r1_c2: st.radio("세금체납여부", ["없음", "있음"], horizontal=True, key="in_tax_delinquency", on_change=auto_save)
        st.markdown("<div style='margin-top:25px;'></div>", unsafe_allow_html=True)
        l_r2_c1, l_r2_c2 = st.columns(2)
        with l_r2_c1: s_kcb = st.number_input("KCB 점수", key="in_kcb_score", step=1, value=None, on_change=auto_save)
        with l_r2_c2: s_nice = st.number_input("NICE 점수", key="in_nice_score", step=1, value=None, on_change=auto_save)
    with c3_col2:
        vk, vn = safe_int(s_kcb), safe_int(s_nice)
        status, color, text = ("🟢 진행 원활", "#E8F5E9", "양호한 신용 상태") if vk > 700 else ("🟡 진행 주의", "#FFF3E0", "신용 보완 권장")
        st.markdown(f'<div class="summary-box-compact"><p style="font-weight:700;">신용상태요약</p><p style="font-size:1.45em; font-weight:800;">{status}</p><p>{text}</p></div>', unsafe_allow_html=True)
    with c3_col3:
        res_c1, res_c2 = st.columns(2)
        kg, kc = get_kcb_grade(vk); ng, nc = get_nice_grade(vn)
        with res_c1: st.markdown(f'<div class="score-result-box"><p class="result-title">KCB 결과</p><p style="font-size:1.8em; font-weight:800; color:{kc};">{vk}점</p><p>{kg}</p></div>', unsafe_allow_html=True)
        with res_c2: st.markdown(f'<div class="score-result-box"><p class="result-title">NICE 결과</p><p style="font-size:1.8em; font-weight:800; color:{nc};">{vn}점</p><p>{ng}</p></div>', unsafe_allow_html=True)
    st.markdown("---")

    # --- 4. 매출현황 ---
    st.header("4. 매출현황")
    exp_c1, exp_c2 = st.columns(2)
    with exp_c1: st.radio("수출매출 여부", ["없음", "있음"], horizontal=True, key="in_export_revenue", on_change=auto_save)
    with exp_c2: st.radio("수출예정 여부", ["없음", "있음"], horizontal=True, key="in_planned_export", on_change=auto_save)
    mc = st.columns(4)
    m_keys = [("금년 매출", "in_sales_cur"), ("25년 매출", "in_sales_25"), ("24년 매출", "in_sales_24"), ("23년 매출", "in_sales_23")]
    for i, (t, k) in enumerate(m_keys): mc[i].number_input(f"{t} (만원)", key=k, step=1, placeholder=GUIDE_STR, value=None, on_change=auto_save)
    st.markdown("---")

    # --- 5. 부채현황 ---
    st.header("5. 부채현황")
    debt_items = [("중진공", "in_debt_kosme"), ("소진공", "in_debt_semas"), ("신보", "in_debt_kodit"), ("기보", "in_debt_kibo"), ("재단", "in_debt_foundation"), ("회사담보", "in_debt_corp_coll"), ("대표신용", "in_debt_rep_cred"), ("대표담보", "in_debt_rep_coll")]
    for r in range(0, 8, 4):
        cols = st.columns(4)
        for i in range(4): cols[i].number_input(f"{debt_items[r+i][0]} (만원)", key=debt_items[r+i][1], step=1, placeholder=GUIDE_STR, value=None, on_change=auto_save)
    st.markdown("---")

    # --- 6. 보유 인증 ---
    st.header("6. 보유 인증")
    cert_list = ["중소기업확인서", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
    for i in range(0, 8, 4):
        cols = st.columns(4)
        for j in range(4):
            if i+j < len(cert_list): cols[j].checkbox(cert_list[i+j], key=f"in_cert_{i+j}", on_change=auto_save)
    st.markdown("---")

    # --- 7. 특허 및 정부지원 ---
    st.header("7. 특허 및 정부지원")
    c7 = st.columns(2)
    with c7[0]:
        st.radio("특허 보유 여부", ["없음", "있음"], horizontal=True, key="in_has_patent", on_change=auto_save)
        st.number_input("보유 건수", key="in_pat_cnt", step=1, value=None, on_change=auto_save)
        st.text_area("특허 상세 내용", key="in_pat_desc", placeholder="특허 명칭 및 내용", on_change=auto_save)
    with c7[1]:
        st.radio("정부지원 수혜이력", ["없음", "있음"], horizontal=True, key="in_has_gov", on_change=auto_save)
        st.number_input("수혜 건수", key="in_gov_cnt", step=1, value=None, on_change=auto_save)
        st.text_area("수혜 사업명 상세", key="in_gov_desc", placeholder="과거 선정 사업명", on_change=auto_save)
    st.markdown("---")

    # --- 8. 비즈니스 상세 정보 ---
    st.header("8. 비즈니스 상세 정보")
    r8_1 = st.columns(2)
    with r8_1[0]: st.text_area("핵심 아이템", key="in_item_desc", height=100, on_change=auto_save)
    with r8_1[1]: st.text_area("판매 루트(유통망)", key="in_sales_route", height=100, on_change=auto_save)
    r8_2 = st.columns(2)
    with r8_2[0]: st.text_area("경쟁력 및 차별성", key="in_item_diff", height=100, on_change=auto_save)
    with r8_2[1]: st.text_area("시장 현황", key="in_market_status", height=100, on_change=auto_save)
    st.markdown("---")

    # --- 9. 자금 계획 ---
    st.header("9. 자금 계획")
    c9 = st.columns([1, 2])
    with c9[0]:
        st.markdown('<p class="blue-bold-label-16">이번 조달 필요 자금 (만원)</p>', unsafe_allow_html=True)
        st.number_input("조달금액", key="in_req_funds", label_visibility="collapsed", step=1, placeholder=GUIDE_STR, value=None, on_change=auto_save)
    with c9[1]:
        st.markdown('<p style="font-size:14px;">상세 자금 집행 계획</p>', unsafe_allow_html=True)
        st.text_area("자금집행", key="in_fund_plan", placeholder="예: 연구인력 채용(40%) 등", label_visibility="collapsed", on_change=auto_save)

else:
    # --- 리포트 출력 모드 ---
    if st.button("⬅️ 입력 화면으로 돌아가기"):
        st.session_state["view_mode"] = "INPUT"; st.rerun()

    current_data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
    mode = st.session_state["view_mode"]
    biz_name = current_data.get("in_company_name", "미입력")
    
    final_api_key = st.session_state["settings"].get("api_key", "")

    if not final_api_key:
        st.error("사이드바에서 API Key를 먼저 저장해 주세요.")
    elif not current_data.get("in_company_name"):
        st.warning("분석할 기업 정보가 없습니다. 입력화면에서 정보를 먼저 작성해 주세요.")
    else:
        with st.status(f"🚀 {biz_name} AI 분석 중..."):
            try:
                if mode == "REPORT": res_html = engine_analysis.run_report(final_api_key, current_data)
                elif mode == "MATCHING": res_html = engine_matching.run_report(final_api_key, current_data)
                elif mode == "LOAN_PLAN": res_html = engine_loan.run_report(final_api_key, current_data)
                elif mode == "AI_PLAN": res_html = engine_ai_plan.run_report(final_api_key, current_data)
                components.html(res_html, height=1200, scrolling=True)
            except Exception as e:
                st.error(f"오류 발생: {e}")
