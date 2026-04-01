import streamlit as st
import json
import os
import streamlit.components.v1 as components
import google.generativeai as genai

# ==========================================
# 0. 데이터 증발 방지 및 세션 초기화
# ==========================================
SETTINGS_FILE = "settings.json"
DATA_FILE = "companies_data.json"
GUIDE_STR = "1억=10000으로 입력"

# 모든 입력 필드 키 정의 (데이터 박제용)
INPUT_KEYS = [
    "in_company_name", "in_biz_type", "in_raw_biz_no", "in_raw_corp_no",
    "in_start_date", "in_biz_tel", "in_email_addr", "in_industry",
    "in_lease_status", "in_biz_addr", "in_lease_deposit", "in_lease_rent",
    "in_has_extra_biz", "in_extra_biz_info",
    "in_rep_name", "in_rep_dob", "in_rep_phone", "in_rep_carrier", "in_home_addr", "in_home_status", "in_real_estate",
    "in_edu_level", "in_rep_major", "in_rep_career_1", "in_rep_career_2",
    "in_fin_delinquency", "in_tax_delinquency", "in_kcb_score", "in_nice_score",
    "in_export_revenue", "in_planned_export",
    "in_sales_cur", "in_sales_25", "in_sales_24", "in_sales_23",
    "in_exp_cur", "in_exp_25", "in_exp_24", "in_exp_23",
    "in_debt_kosme", "in_debt_semas", "in_debt_kodit", "in_debt_kibo", "in_debt_foundation", "in_debt_corp_coll", "in_debt_rep_cred", "in_debt_rep_coll",
    "in_has_patent", "in_pat_cnt", "in_pat_desc", "in_has_gov", "in_gov_cnt", "in_gov_desc",
    "in_item_desc", "in_sales_route", "in_item_diff", "in_market_status", "in_process_desc", "in_target_cust", "in_revenue_model", "in_future_plan",
    "in_req_funds", "in_fund_plan"
]
CERT_KEYS = [f"in_cert_{i}" for i in range(8)]

# 세션 상태 초기화 (숫자형 필드 구분)
numeric_fields = ["deposit", "rent", "sales", "exp", "score", "cnt", "funds", "debt"]
for k in INPUT_KEYS + CERT_KEYS:
    if k not in st.session_state:
        if any(x in k for x in numeric_fields): st.session_state[k] = None
        elif k.startswith("in_cert_"): st.session_state[k] = False
        else: st.session_state[k] = ""

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

# ==========================================
# 1. 고도화된 AI 리포트 생성 엔진
# ==========================================
def generate_ai_report(api_key, data):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        # 전문 컨설턴트 톤 (함/있음 체) 및 8단계 구성 프롬프트
        prompt = f"""
        당신은 대한민국 최고의 경영 컨설턴트입니다. 아래 데이터를 기반으로 외부 시장 자료를 참고하여 '전문 기업분석리포트'를 HTML로 작성하세요.

        [기업 정보]
        기업명: {data.get('in_company_name')}, 업종: {data.get('in_industry')}, 아이템: {data.get('in_item_desc')}
        매출: 금년 {data.get('in_sales_cur')}만원, 전년 {data.get('in_sales_24')}만원

        [작성 지침]
        1. 말투: 반드시 '있음', '함', '임' 체로 간결하게 마무리할 것. (~습니다 금지)
        2. 구성: 1.기업현황분석 2.SWOT분석 3.시장현황 4.경쟁사비교 5.핵심경쟁력 6.자금사용계획 7.매출전망(12개월 그래프 포함) 8.성장비전 및 코멘트.
        3. 시각화: 섹션별 배경색 박스, 정갈한 Table, HTML/CSS로 구현한 세련된 매출 막대 그래프 포함.
        4. 인쇄 최적화: 카테고리별로 <div style="page-break-before: always;"></div>를 삽입하여 페이지를 분리할 것.
        5. 분석: AI의 지식을 동원해 해당 산업군의 트렌드와 경쟁 우위 전략을 알차게 담을 것.
        """
        response = model.generate_content(prompt)
        return response.text.replace('```html', '').replace('```', '').strip()
    except Exception as e:
        return f"<div style='color:red;'>리포트 생성 중 오류: {str(e)}</div>"

# ==========================================
# 2. 디자인 커스텀 (CSS)
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

st.markdown(f"""
<style>
    /* 파란색 선 제거 및 헤더 정렬 */
    h2 {{ font-weight: 700 !important; margin-top: 30px !important; border-left: none !important; padding-left: 0 !important; color: #1A237E !important; }}
    [data-testid="stWidgetLabel"] p {{ font-weight: 400 !important; font-size: 14px !important; }}
    input::placeholder {{ font-size: 0.85em !important; color: #aaa !important; }}
    
    /* 6번 인증서 체크박스 폰트 크기 증폭 */
    [data-testid="stCheckbox"] label p {{ font-size: 18px !important; font-weight: 500 !important; color: #333 !important; }}
    
    /* 3번 신용정보 결과 박스 */
    .summary-box-compact {{ background-color: #E8F5E9; padding: 15px; border-radius: 10px; height: 145px; border: 1px solid #ddd; text-align: center; display: flex; flex-direction: column; justify-content: center; }}
    .score-result-box {{ background-color: #F1F8E9; padding: 15px; border-radius: 10px; height: 145px; border: 1px solid #C8E6C9; text-align: center; display: flex; flex-direction: column; justify-content: center; }}
    .result-title {{ font-size: 18px !important; font-weight: 700 !important; color: #2E7D32; margin-bottom: 5px !important; }}
    .blue-bold-label-16 {{ color: #1E88E5 !important; font-size: 16px !important; font-weight: 700 !important; }}
</style>
""", unsafe_allow_html=True)

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
if "settings" not in st.session_state: st.session_state["settings"] = load_json(SETTINGS_FILE, {"api_key": ""})
if "company_list" not in st.session_state: st.session_state["company_list"] = load_json(DATA_FILE, {})

def get_grade(score, type="KCB"):
    s = (score or 0)
    if type == "KCB":
        if s >= 942: return "1등급", "#43A047"
        elif s >= 832: return "3등급", "#66BB6A"
        return f"{s}점", "#EF6C00"
    else:
        if s >= 900: return "1등급", "#1E88E5"
        elif s >= 840: return "3등급", "#42A5F5"
        return f"{s}점", "#EF6C00"

# ==========================================
# 3. 사이드바 (업체 관리 및 리포트 탭)
# ==========================================
st.sidebar.header("⚙️ AI 엔진 설정")
saved_key = st.session_state["settings"].get("api_key", "")
if saved_key:
    st.sidebar.success("✅ API Key 저장됨")
    if st.sidebar.button("🔄 Key 변경"):
        st.session_state["settings"]["api_key"] = ""; st.rerun()
else:
    new_key = st.sidebar.text_input("Gemini API Key", type="password")
    if st.sidebar.button("💾 영구 저장"):
        save_json(SETTINGS_FILE, {"api_key": new_key}); st.session_state["settings"]["api_key"] = new_key; st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("📁 업체 관리")
t_s, t_l = st.sidebar.tabs(["💾 저장하기", "📂 불러오기"])
with t_s:
    if st.button("현재 정보 저장", use_container_width=True):
        name = st.session_state.in_company_name.strip()
        if name:
            st.session_state["company_list"][name] = {k: st.session_state[k] for k in INPUT_KEYS + CERT_KEYS}
            save_json(DATA_FILE, st.session_state["company_list"])
            st.success(f"'{name}' 저장 완료!")
        else: st.error("기업명을 입력하세요.")
with t_l:
    if st.session_state["company_list"]:
        target = st.selectbox("업체 선택", list(st.session_state["company_list"].keys()))
        if st.button("데이터 불러오기", use_container_width=True):
            for k, v in st.session_state["company_list"][target].items(): st.session_state[k] = v
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🚀 리포트 생성")
s_modes = ["REPORT", "MATCHING", "LOAN_PLAN", "AI_PLAN"]
s_labels = ["📊 AI 기업분석리포트 시작", "💡 AI 정책자금 매칭", "📝 융자/사업계획서", "📑 AI 사업계획서"]
for i in range(4):
    if st.sidebar.button(s_labels[i], key=f"side_{i}", use_container_width=True):
        st.session_state["view_mode"] = s_modes[i]; st.rerun()

# ==========================================
# 4. 메인 화면 구성
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
t_cols = st.columns(4)
for i in range(4):
    if t_cols[i].button(s_labels[i], key=f"top_{i}", use_container_width=True, type="primary"):
        st.session_state["view_mode"] = s_modes[i]; st.rerun()
st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

if st.session_state["view_mode"] == "INPUT":
    # --- 1. 기업현황 (4층 구조) ---
    st.header("1. 기업현황")
    c1_1 = st.columns([2, 1, 1.5, 1.5])
    c1_1[0].text_input("기업명", key="in_company_name")
    c1_1[1].radio("사업자유형", ["개인", "법인"], key="in_biz_type", horizontal=True)
    c1_1[2].text_input("사업자번호", key="in_raw_biz_no", placeholder="000-00-00000")
    c1_1[3].text_input("법인등록번호", key="in_raw_corp_no", placeholder="000000-0000000")
    
    c1_2 = st.columns([1, 1, 1, 1])
    c1_2[0].text_input("사업개시일", key="in_start_date", placeholder="YYYY.MM.DD")
    c1_2[1].text_input("사업장 전화번호", key="in_biz_tel", placeholder="000-00-0000")
    c1_2[2].text_input("이메일 주소", key="in_email_addr", placeholder="example@email.com")
    c1_2[3].selectbox("현사업장 업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")
    
    c1_3 = st.columns([1.2, 3, 0.9, 0.9])
    c1_3[0].radio("사업장 임대여부", ["자가", "임대"], key="in_lease_status", horizontal=True)
    c1_3[1].text_input("사업장 주소", key="in_biz_addr", placeholder="소재지를 입력하세요")
    c1_3[2].number_input("보증금(만원)", key="in_lease_deposit", placeholder=GUIDE_STR, value=st.session_state.in_lease_deposit)
    c1_3[3].number_input("월임대료(만원)", key="in_lease_rent", placeholder=GUIDE_STR, value=st.session_state.in_lease_rent)
    
    c1_4 = st.columns([1.2, 3, 1.8])
    c1_4[0].radio("추가 사업장 여부", ["없음", "있음"], key="in_has_extra_biz", horizontal=True)
    c1_4[1].text_input("추가사업장 정보입력", key="in_extra_biz_info", placeholder="사업장명/사업자등록번호")
    st.markdown("---")

    # --- 2. 대표자 정보 (복구) ---
    st.header("2. 대표자 정보")
    r2c1 = st.columns([1, 1, 1, 1])
    r2c1[0].text_input("대표자명", key="in_rep_name")
    r2c1[1].text_input("생년월일", key="in_rep_dob", placeholder="YYYY.MM.DD")
    r2c1[2].text_input("연락처", key="in_rep_phone")
    r2c1[3].selectbox("통신사", ["선택", "SKT", "KT", "LGU+", "알뜰폰"], key="in_rep_carrier")
    r2c2 = st.columns([2, 1, 1])
    r2c2[0].text_input("거주지 주소", key="in_home_addr")
    r2c2[1].radio("거주지 상태", ["자가", "임대"], key="in_home_status", horizontal=True)
    r2c2[2].multiselect("부동산 보유", ["아파트", "빌라", "토지", "공장"], key="in_real_estate")
    r2c3 = st.columns([1, 1, 2, 2])
    r2c3[0].selectbox("학력", ["선택", "고졸", "대졸", "석사", "박사"], key="in_edu_level")
    r2c3[1].text_input("전공", key="in_rep_major")
    r2c3[2].text_input("경력 1", key="in_rep_career_1")
    r2c3[3].text_input("경력 2", key="in_rep_career_2")
    st.markdown("---")

    # --- 3. 대표자 신용정보 (박스 디자인 복구) ---
    st.header("3. 대표자 신용정보")
    cc1, cc2, cc3 = st.columns([1.5, 1.3, 1.8])
    with cc1:
        cr1 = st.columns(2)
        cr1[0].radio("금융연체", ["없음", "있음"], key="in_fin_delinquency", horizontal=True)
        cr1[1].radio("세금체납", ["없음", "있음"], key="in_tax_delinquency", horizontal=True)
        cr2 = st.columns(2)
        sk = cr2[0].number_input("KCB 점수", key="in_kcb_score", value=st.session_state.in_kcb_score)
        sn = cr2[1].number_input("NICE 점수", key="in_nice_score", value=st.session_state.in_nice_score)
    with cc2:
        vk = (sk or 0)
        status = "🟢 진행 원활" if vk > 700 else "🟡 진행 주의"
        st.markdown(f'<div class="summary-box-compact"><p style="font-weight:700;">신용요약</p><h3>{status}</h3><p>종합 분석 결과</p></div>', unsafe_allow_html=True)
    with cc3:
        kg, kc = get_grade(sk, "KCB"); ng, nc = get_grade(sn, "NICE")
        res1, res2 = st.columns(2)
        res1.markdown(f'<div class="score-result-box"><p class="result-title">KCB 결과</p><h2 style="color:{kc}; margin:0;">{sk or 0}점</h2><p>{kg}</p></div>', unsafe_allow_html=True)
        res2.markdown(f'<div class="score-result-box"><p class="result-title">NICE 결과</p><h2 style="color:{nc}; margin:0;">{sn or 0}점</h2><p>{ng}</p></div>', unsafe_allow_html=True)
    st.markdown("---")

    # --- 4. 매출 및 수출현황 (복구) ---
    st.header("4. 매출 및 수출현황")
    ec = st.columns(2)
    with ec[0]: has_exp = st.radio("수출매출 여부", ["없음", "있음"], key="in_export_revenue", horizontal=True)
    with ec[1]: plan_exp = st.radio("수출예정 여부", ["없음", "있음"], key="in_planned_export", horizontal=True)
    mcols = st.columns(4)
    mcols[0].number_input("금년 매출", key="in_sales_cur", placeholder=GUIDE_STR, value=st.session_state.in_sales_cur)
    mcols[1].number_input("25년 매출", key="in_sales_25", placeholder=GUIDE_STR, value=st.session_state.in_sales_25)
    mcols[2].number_input("24년 매출", key="in_sales_24", placeholder=GUIDE_STR, value=st.session_state.in_sales_24)
    mcols[3].number_input("23년 매출", key="in_sales_23", placeholder=GUIDE_STR, value=st.session_state.in_sales_23)
    if has_exp == "있음":
        st.write("**[수출 상세역사 (만원)]**")
        excols = st.columns(4)
        excols[0].number_input("금년 수출", key="in_exp_cur", placeholder=GUIDE_STR, value=st.session_state.in_exp_cur)
        excols[1].number_input("25년 수출", key="in_exp_25", placeholder=GUIDE_STR, value=st.session_state.in_exp_25)
        excols[2].number_input("24년 수출", key="in_exp_24", placeholder=GUIDE_STR, value=st.session_state.in_exp_24)
        excols[3].number_input("23년 수출", key="in_exp_23", placeholder=GUIDE_STR, value=st.session_state.in_exp_23)
    st.markdown("---")

    # --- 6. 보유 인증 (폰트 확대) ---
    st.header("6. 보유 인증")
    clist = ["중소기업확인서(소상공인확인서)", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
    for i in range(0, 8, 4):
        cols = st.columns(4)
        for j in range(4): cols[j].checkbox(clist[i+j], key=f"in_cert_{i+j}")
    st.markdown("---")

    # --- 8. 비즈니스 상세 정보 (8종 복구) ---
    st.header("8. 비즈니스 상세 정보")
    b_rows = [("핵심 아이템", "in_item_desc", "판매 루트", "in_sales_route"),
              ("경쟁력/차별성", "in_item_diff", "시장 현황", "in_market_status"),
              ("생산 공정도", "in_process_desc", "타겟 고객", "in_target_cust"),
              ("수익 모델", "in_revenue_model", "미래 계획", "in_future_plan")]
    for labels in b_rows:
        cols = st.columns(2)
        cols[0].text_area(labels[0], key=labels[1], height=100)
        cols[1].text_area(labels[2], key=labels[3], height=100)
    st.markdown("---")

    # --- 9. 자금 계획 ---
    st.header("9. 자금 계획")
    c9 = st.columns([1, 2])
    with c9[0]:
        st.markdown('<p class="blue-bold-label-16">이번 조달 필요 자금 (만원)</p>', unsafe_allow_html=True)
        st.number_input("조달금액", key="in_req_funds", label_visibility="collapsed", placeholder=GUIDE_STR, value=st.session_state.in_req_funds)
    with c9[1]:
        st.text_area("상세 자금 집행 계획", key="in_fund_plan", placeholder="상세 용도를 기재해 주세요")

else:
    # --- 리포트 출력 모드 (데이터 즉시 인식) ---
    if st.button("⬅️ 입력 화면으로 돌아가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    
    api_key = st.session_state["settings"].get("api_key", "")
    current_data = {k: st.session_state[k] for k in INPUT_KEYS + CERT_KEYS}
    biz_name = st.session_state.in_company_name.strip()
    
    if not api_key: st.error("API Key를 저장하세요.")
    elif not biz_name: st.warning("기업명을 먼저 입력해 주세요.")
    else:
        with st.status(f"🚀 {biz_name} 리포트 분석 및 생성 중..."):
            res_html = generate_ai_report(api_key, current_data)
            components.html(res_html, height=1500, scrolling=True)
