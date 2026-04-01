import streamlit as st
import json
import os
import streamlit.components.v1 as components
import google.generativeai as genai

# ==========================================
# 0. 데이터 유실 원천 차단 - 세션 상태 강제 초기화
# ==========================================
SETTINGS_FILE = "settings.json"
DATA_FILE = "companies_data.json"
GUIDE_STR = "1억=10000으로 입력"

# 1~9번 전체 섹션 필드 정의
INPUT_FIELDS = [
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

# 숫자형 필드 구분 (TypeError 방지)
numeric_keys = ["cnt", "score", "deposit", "rent", "sales", "exp", "funds", "debt"]

for k in INPUT_FIELDS + CERT_KEYS:
    if k not in st.session_state:
        if any(x in k for x in numeric_keys): st.session_state[k] = None
        elif k.startswith("in_cert_"): st.session_state[k] = False
        else: st.session_state[k] = ""

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except: return default
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ==========================================
# 1. 고도화된 AI 리포트 엔진 (8종 항목 구성)
# ==========================================
def generate_ai_report(api_key, data):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"""
        당신은 최고의 경영 컨설턴트입니다. 아래 정보를 바탕으로 전문 '기업분석리포트'를 HTML로 작성하세요.
        [데이터] 기업명: {data.get('in_company_name')}, 업종: {data.get('in_industry')}, 주요아이템: {data.get('in_item_desc')}
        [지침]
        1. 말투: 반드시 '있음', '함', '임' 체로 간결하고 전문적이게 마무리할 것.
        2. 구성: 1.기업현황분석 2.SWOT분석 3.시장현황 4.경쟁력분석 5.핵심경쟁력 6.자금사용계획 7.매출전망(12개월 그래프) 8.성장비전 및 총평.
        3. 페이지분할: 카테고리별로 <div style="page-break-before: always;"></div> 필수 삽입.
        """
        response = model.generate_content(prompt)
        return response.text.replace('```html', '').replace('```', '').strip()
    except Exception as e:
        return f"<div style='color:red;'>리포트 생성 오류: {str(e)}</div>"

# ==========================================
# 2. 디자인 커스텀 (CSS)
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")
st.markdown(f"""
<style>
    h2 {{ font-weight: 700 !important; margin-top: 30px !important; color: #1A237E !important; border: none !important; }}
    [data-testid="stWidgetLabel"] p {{ font-size: 14px !important; font-weight: 400 !important; }}
    input::placeholder {{ font-size: 0.85em !important; color: #aaa !important; }}
    
    /* 6번 인증서 체크박스 확대 */
    [data-testid="stCheckbox"] label p {{ font-size: 18px !important; font-weight: 500 !important; color: #333 !important; }}
    
    /* 3번 신용 등급 박스 - 제목 포함 */
    .score-box {{ 
        background-color: #F1F8E9; padding: 15px; border-radius: 10px; border: 1px solid #C8E6C9; 
        text-align: center; height: 160px; display: flex; flex-direction: column; justify-content: center;
    }}
    .box-label {{ font-size: 16px !important; font-weight: 700 !important; color: #2E7D32; margin-bottom: 8px; }}
    .blue-bold-label-16 {{ color: #1E88E5 !important; font-size: 16px !important; font-weight: 700 !important; }}
</style>
""", unsafe_allow_html=True)

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
if "settings" not in st.session_state: st.session_state["settings"] = load_json(SETTINGS_FILE, {"api_key": ""})
if "company_list" not in st.session_state: st.session_state["company_list"] = load_json(DATA_FILE, {})

# [이미지 표 기준 등급 산출 로직]
def get_kcb_grade(s):
    s = s or 0
    if s >= 942: return "1등급", "#43A047"
    if s >= 891: return "2등급", "#66BB6A" # 910점은 2등급
    if s >= 832: return "3등급", "#8BC34A"
    if s >= 768: return "4등급", "#CDDC39"
    if s >= 698: return "5등급", "#FFEB3B"
    if s >= 630: return "6등급", "#FFC107"
    return "7등급이하", "#F44336"

def get_nice_grade(s):
    s = s or 0
    if s >= 900: return "1등급", "#1E88E5"
    if s >= 870: return "2등급", "#2196F3"
    if s >= 840: return "3등급", "#42A5F5"
    if s >= 805: return "4등급", "#64B5F6"
    return "5등급이하", "#FFC107"

# ==========================================
# 3. 사이드바 (업체 관리 및 리포트 탭 복구)
# ==========================================
st.sidebar.header("⚙️ AI 엔진 설정")
api_key = st.session_state["settings"].get("api_key", "")
if api_key:
    st.sidebar.success("✅ API Key 연결됨")
    if st.sidebar.button("🔄 Key 변경"): st.session_state["settings"]["api_key"] = ""; st.rerun()
else:
    new_key = st.sidebar.text_input("API Key 입력", type="password")
    if st.sidebar.button("💾 영구 저장"):
        save_json(SETTINGS_FILE, {"api_key": new_key}); st.session_state["settings"]["api_key"] = new_key; st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("📁 업체 관리")
t_s, t_l = st.sidebar.tabs(["💾 저장", "📂 불러오기"])
with t_s:
    if st.button("현재 정보 파일 저장", use_container_width=True):
        name = st.session_state.in_company_name.strip()
        if name:
            st.session_state["company_list"][name] = {k: st.session_state[k] for k in INPUT_FIELDS + CERT_KEYS}
            save_json(DATA_FILE, st.session_state["company_list"]); st.success("저장 완료")
        else: st.error("기업명을 입력하세요.")
with t_l:
    if st.session_state["company_list"]:
        target = st.selectbox("불러오기 선택", list(st.session_state["company_list"].keys()))
        if st.button("데이터 불러오기", use_container_width=True):
            for k, v in st.session_state["company_list"][target].items(): st.session_state[k] = v
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🚀 리포트 생성")
s_modes = ["REPORT", "MATCHING", "LOAN_PLAN", "AI_PLAN"]
s_labels = ["📊 AI 기업분석리포트", "💡 AI 정책자금 매칭", "📝 융자/사업계획서", "📑 AI 사업계획서"]
for i in range(4):
    if st.sidebar.button(s_labels[i], key=f"side_nav_{i}", use_container_width=True):
        st.session_state["view_mode"] = s_modes[i]; st.rerun()

# ==========================================
# 4. 메인 대시보드 - 상단 탭 복구
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
t_cols = st.columns(4)
for i in range(4):
    if t_cols[i].button(s_labels[i], key=f"top_nav_{i}", use_container_width=True, type="primary"):
        st.session_state["view_mode"] = s_modes[i]; st.rerun()
st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

# ==========================================
# 5. 화면 분기 (입력 모드 vs 리포트 모드)
# ==========================================
if st.session_state["view_mode"] == "INPUT":
    # --- 1. 기업현황 (4층 구조) ---
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
    c3[1].text_input("사업장 주소", key="in_biz_addr", placeholder="소재지를 입력하세요")
    c3[2].number_input("보증금(만원)", key="in_lease_deposit", placeholder=GUIDE_STR, value=st.session_state.in_lease_deposit)
    c3[3].number_input("월임대료(만원)", key="in_lease_rent", placeholder=GUIDE_STR, value=st.session_state.in_lease_rent)
    
    c4 = st.columns([1.2, 3, 1.8])
    c4[0].radio("추가 사업장 여부", ["없음", "있음"], key="in_has_extra_biz", horizontal=True)
    c4[1].text_input("추가사업장 정보입력", key="in_extra_biz_info")
    st.markdown("---")

    # --- 2. 대표자 정보 ---
    st.header("2. 대표자 정보")
    r2c1 = st.columns([1, 1, 1, 1])
    r2c1[0].text_input("대표자명", key="in_rep_name")
    r2c1[1].text_input("생년월일", key="in_rep_dob", placeholder="YYYY.MM.DD")
    r2c1[2].text_input("연락처", key="in_rep_phone")
    r2c1[3].selectbox("통신사", ["선택", "SKT", "KT", "LGU+", "알뜰폰"], key="in_rep_carrier")
    st.markdown("---")

    # --- 3. 대표자 신용정보 (제목 포함 박스 복구) ---
    st.header("3. 대표자 신용정보")
    cc1, cc2, cc3 = st.columns([1.5, 1.3, 1.8])
    with cc1:
        cr1 = st.columns(2)
        cr1[0].radio("금융연체여부", ["없음", "있음"], key="in_fin_delinquency", horizontal=True)
        cr1[1].radio("세금체납여부", ["없음", "있음"], key="in_tax_delinquency", horizontal=True)
        cr2 = st.columns(2)
        sk = cr2[0].number_input("KCB 점수", key="in_kcb_score", value=st.session_state.in_kcb_score)
        sn = cr2[1].number_input("NICE 점수", key="in_nice_score", value=st.session_state.in_nice_score)
    with cc2:
        v = (sk or 0)
        status = "🟢 진행 원활" if v > 700 else "🟡 진행 주의"
        st.markdown(f'<div class="score-box"><p class="box-label">신용요약</p><h2 style="margin:0;">{status}</h2><p style="margin-top:5px; font-size:12px; color:#666;">종합 분석 결과</p></div>', unsafe_allow_html=True)
    with cc3:
        kg, kc = get_kcb_grade(sk); ng, nc = get_nice_grade(sn)
        res1, res2 = st.columns(2)
        res1.markdown(f'<div class="score-box"><p class="box-label">KCB 결과</p><h2 style="color:{kc}; margin:0;">{sk or 0}점</h2><p>{kg}</p></div>', unsafe_allow_html=True)
        res2.markdown(f'<div class="score-box"><p class="box-label">NICE 결과</p><h2 style="color:{nc}; margin:0;">{sn or 0}점</h2><p>{ng}</p></div>', unsafe_allow_html=True)
    st.markdown("---")

    # --- 4. 매출현황 ---
    st.header("4. 매출현황")
    ec = st.columns(2)
    with ec[0]: has_exp = st.radio("수출매출 여부", ["없음", "있음"], key="in_export_revenue", horizontal=True)
    with ec[1]: plan_exp = st.radio("수출예정 여부", ["없음", "있음"], key="in_planned_export", horizontal=True)
    m_cols = st.columns(4)
    m_cols[0].number_input("금년 매출(만원)", key="in_sales_cur", placeholder=GUIDE_STR)
    m_cols[1].number_input("25년 매출(만원)", key="in_sales_25", placeholder=GUIDE_STR)
    m_cols[2].number_input("24년 매출(만원)", key="in_sales_24", placeholder=GUIDE_STR)
    m_cols[3].number_input("23년 매출(만원)", key="in_sales_23", placeholder=GUIDE_STR)
    if has_exp == "있음":
        st.write("**[수출부문 매출현황]**")
        ex_cols = st.columns(4)
        ex_cols[0].number_input("금년 수출액", key="in_exp_cur", placeholder=GUIDE_STR)
        ex_cols[1].number_input("25년 수출액", key="in_exp_25", placeholder=GUIDE_STR)
        ex_cols[2].number_input("24년 수출액", key="in_exp_24", placeholder=GUIDE_STR)
        ex_cols[3].number_input("23년 수출액", key="in_exp_23", placeholder=GUIDE_STR)
    st.markdown("---")

    # --- 5. 부채현황 ---
    st.header("5. 부채현황")
    debt_lbls = [("중진공", "in_debt_kosme"), ("소진공", "in_debt_semas"), ("신보", "in_debt_kodit"), ("기보", "in_debt_kibo"), ("재단", "in_debt_foundation"), ("회사담보", "in_debt_corp_coll"), ("대표신용", "in_debt_rep_cred"), ("대표담보", "in_debt_rep_coll")]
    for r in range(0, 8, 4):
        cols = st.columns(4)
        for j in range(4): cols[j].number_input(f"{debt_lbls[r+j][0]} (만원)", key=debt_lbls[r+j][1], placeholder=GUIDE_STR, value=st.session_state[debt_lbls[r+j][1]])
    st.markdown("---")

    # --- 6. 보유 인증 ---
    st.header("6. 보유 인증")
    clist = ["중소기업확인서(소상공인확인서)", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
    for i in range(0, 8, 4):
        cols = st.columns(4)
        for j in range(4): cols[j].checkbox(clist[i+j], key=f"in_cert_{i+j}")
    st.markdown("---")

    # --- 7. 특허 및 정부지원 ---
    st.header("7. 특허 및 정부지원")
    c7 = st.columns(2)
    with c7[0]:
        st.radio("특허 보유 여부", ["없음", "있음"], key="in_has_patent", horizontal=True)
        st.number_input("보유 건수", key="in_pat_cnt", value=st.session_state.in_pat_cnt)
        st.text_area("특허 상세 내용", key="in_pat_desc")
    with c7[1]:
        st.radio("정부지원 수혜이력", ["없음", "있음"], key="in_has_gov", horizontal=True)
        st.number_input("수혜 건수", key="in_gov_cnt", value=st.session_state.in_gov_cnt)
        st.text_area("수혜 사업명 상세", key="in_gov_desc")
    st.markdown("---")

    # --- 8. 비즈니스 상세 정보 (8종) ---
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
    # --- 리포트 화면 모드 ---
    if st.button("⬅️ 입력 화면으로 돌아가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    current_data = {k: st.session_state[k] for k in INPUT_FIELDS + CERT_KEYS}
    biz_name = st.session_state.in_company_name.strip()
    if not biz_name: st.warning("기업명을 입력하세요."); st.stop()
    with st.status(f"🚀 {biz_name} 리포트 분석 중..."):
        report_html = generate_ai_report(api_key, current_data)
        components.html(report_html, height=1500, scrolling=True)
