import streamlit as st
import json
import os
import streamlit.components.v1 as components
import google.generativeai as genai

# ==========================================
# 0. 초기 설정 및 데이터 철통 보존 로직
# ==========================================
SETTINGS_FILE = "settings.json"
DATA_FILE = "companies_data.json"
GUIDE_STR = "1억=10000으로 입력"

# [데이터 증발 방지] 모든 입력 필드 키 리스트
INPUT_KEYS = [
    "in_company_name", "in_biz_type", "in_raw_biz_no", "in_raw_corp_no",
    "in_start_date", "in_biz_tel", "in_email_addr", "in_industry",
    "in_lease_status", "in_biz_addr", "in_lease_deposit", "in_lease_rent",
    "in_has_extra_biz", "in_extra_biz_info", "in_rep_name", "in_rep_major",
    "in_sales_cur", "in_sales_24", "in_req_funds", "in_fund_plan",
    "in_item_desc", "in_pat_desc", "in_gov_desc", "in_kcb_score", "in_nice_score"
]
CERT_KEYS = [f"in_cert_{i}" for i in range(8)]

# 세션 상태 초기화 (절대 지워지지 않도록 앱 최상단 배치)
for k in INPUT_KEYS:
    if k not in st.session_state:
        st.session_state[k] = None if any(x in k for x in ["deposit", "rent", "sales", "funds", "score"]) else ""
for ck in CERT_KEYS:
    if ck not in st.session_state: st.session_state[ck] = False

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

# ==========================================
# 1. 고도화된 AI 기업분석 리포트 엔진 (테스트 완료)
# ==========================================
def generate_ai_report(api_key, data):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        # 8대 항목 및 전문 톤 프롬프트
        prompt = f"""
        당신은 대한민국 최고의 기업 컨설턴트입니다. 다음 정보를 기반으로 외부 시장 분석을 결합한 전문 '기업분석리포트'를 HTML로 작성하세요.

        [기업 기초 데이터]
        - 기업명: {data.get('in_company_name')}
        - 업종: {data.get('in_industry')}
        - 주요아이템: {data.get('in_item_desc')}
        - 매출(금년): {data.get('in_sales_cur')}만원 / (전년): {data.get('in_sales_24')}만원
        - 필요자금: {data.get('in_req_funds')}만원 ({data.get('in_fund_plan')})

        [작성 지침]
        1. 말투: 반드시 '있음', '함', '임' 체로 간결하고 단호하게 작성할 것. (~습니다 금지)
        2. 분량: 각 항목을 알차게 구성하며 압축하지 말 것. AI가 아는 산업 트렌드를 최대한 동원할 것.
        3. 레이아웃: 섹션마다 배경색 박스, 정갈한 Table, 강조 폰트 사용.
        4. 페이지 분할: 카테고리가 바뀔 때 <div style="page-break-before: always;"></div> 필수 삽입.
        5. 시각화: 매출 전망 부분에 HTML/CSS로 막대 그래프 혹은 화려한 표를 구현할 것.

        [리포트 순서]
        1. 기업현황분석 (표 형식)
        2. SWOT 분석 (강점, 약점, 기회, 위협 상세 기술)
        3. 시장현황 (글로벌/국내 트렌드 및 시장 규모 추정)
        4. 경쟁력 분석 및 주요 경쟁사 비교
        5. 핵심 경쟁력 분석 (3가지 강점 도출)
        6. 필요자금 및 상세 자금사용계획
        7. 매출전망 (1년 월별 전망 그래프 + 4단계 성장전망)
        8. 성장비전 (단/중/장기 비전 제시)
        ※ 컨설턴트 최종 코멘트

        디자인 컨셉: Navy(#1A237E) 포인트, 정갈한 Gray 톤, 문서형 레이아웃.
        """
        response = model.generate_content(prompt)
        return response.text.replace('```html', '').replace('```', '').strip()
    except Exception as e:
        return f"<div style='color:red;'>오류 발생: {str(e)}</div>"

# ==========================================
# 2. UI/디자인 설정
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

st.markdown("""
<style>
    [data-testid="stWidgetLabel"] p { font-weight: 400 !important; font-size: 14px !important; color: #31333F !important; }
    h2 { font-weight: 700 !important; margin-top: 25px !important; color: #1A237E; }
    .summary-box { background-color: #E8F5E9; padding: 15px; border-radius: 10px; border: 1px solid #ddd; text-align: center; }
    .score-box { background-color: #F1F8E9; padding: 15px; border-radius: 10px; border: 1px solid #C8E6C9; text-align: center; }
    [data-testid="stCheckbox"] label p { font-size: 18px !important; font-weight: 500; }
</style>
""", unsafe_allow_html=True)

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
if "settings" not in st.session_state: st.session_state["settings"] = load_json(SETTINGS_FILE, {"api_key": ""})
if "company_list" not in st.session_state: st.session_state["company_list"] = load_json(DATA_FILE, {})

# ==========================================
# 3. 사이드바 구성
# ==========================================
st.sidebar.header("⚙️ AI 엔진 설정")
api_key = st.session_state["settings"].get("api_key", "")
if api_key:
    st.sidebar.success("✅ API Key 연결됨")
    if st.sidebar.button("🔄 Key 변경"):
        st.session_state["settings"]["api_key"] = ""
        st.rerun()
else:
    new_key = st.sidebar.text_input("Gemini API Key", type="password")
    if st.sidebar.button("💾 영구 저장"):
        save_json(SETTINGS_FILE, {"api_key": new_key})
        st.session_state["settings"]["api_key"] = new_key
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("📁 업체 관리")
tab_s, tab_l = st.sidebar.tabs(["💾 저장", "📂 불러오기"])
with tab_s:
    if st.button("현재 정보 파일 저장", use_container_width=True):
        name = st.session_state.in_company_name
        if name:
            st.session_state["company_list"][name] = {k: st.session_state[k] for k in INPUT_KEYS + CERT_KEYS}
            save_json(DATA_FILE, st.session_state["company_list"])
            st.success("저장 완료")
        else: st.error("기업명 필수")
with tab_l:
    if st.session_state["company_list"]:
        target = st.selectbox("업체 선택", list(st.session_state["company_list"].keys()))
        if st.button("데이터 불러오기", use_container_width=True):
            for k, v in st.session_state["company_list"][target].items(): st.session_state[k] = v
            st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("📊 AI 기업분석리포트 시작", use_container_width=True):
    if st.session_state.in_company_name:
        st.session_state["view_mode"] = "REPORT"; st.rerun()
    else: st.sidebar.warning("기업명을 먼저 입력하세요.")

# ==========================================
# 4. 메인 화면 - 입력 모드 (4층 구조)
# ==========================================
st.title("📊 AI 컨설팅 대시보드")

if st.session_state["view_mode"] == "INPUT":
    # 1. 기업현황 (요청하신 4층 레이아웃)
    st.header("1. 기업현황")
    c1 = st.columns([2, 1, 1.5, 1.5])
    c1[0].text_input("기업명", key="in_company_name")
    c1[1].radio("사업자유형", ["개인", "법인"], key="in_biz_type", horizontal=True)
    c1[2].text_input("사업자번호", key="in_raw_biz_no", placeholder="000-00-00000")
    c1[3].text_input("법인등록번호", key="in_raw_corp_no", placeholder="000000-0000000")
    
    c2 = st.columns([1, 1, 1, 1])
    c2[0].text_input("사업개시일", key="in_start_date", placeholder="YYYY.MM.DD")
    c2[1].text_input("사업장 전화번호", key="in_biz_tel", placeholder="000-00-0000")
    c2[2].text_input("이메일 주소", key="in_email_addr", placeholder="example@email.com")
    c2[3].selectbox("현사업장 업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")
    
    c3 = st.columns([1.2, 3, 0.9, 0.9])
    c3[0].radio("사업장 임대여부", ["자가", "임대"], key="in_lease_status", horizontal=True)
    c3[1].text_input("사업장 주소", key="in_biz_addr", placeholder="소재지를 입력하세요")
    c3[2].number_input("보증금(만원)", key="in_lease_deposit", placeholder=GUIDE_STR, value=st.session_state.in_lease_deposit)
    c3[3].number_input("월임대료(만원)", key="in_lease_rent", placeholder=GUIDE_STR, value=st.session_state.in_lease_rent)
    
    c4 = st.columns([1.2, 3, 1.8])
    c4[0].radio("추가 사업장 여부", ["없음", "있음"], key="in_has_extra_biz", horizontal=True)
    c4[1].text_input("추가사업장 정보입력", key="in_extra_biz_info", placeholder="주소와 동일한 너비 적용")
    c4[2].empty()

    # 2. 대표자 및 신용
    st.markdown("---")
    st.header("2. 대표자 정보")
    cr1 = st.columns([1, 1, 2.5])
    cr1[0].text_input("대표자명", key="in_rep_name")
    cr1[1].text_input("전공", key="in_rep_major")
    
    st.header("3. 대표자 신용정보")
    cc = st.columns([1, 1, 1.5])
    sk = cc[0].number_input("KCB 점수", key="in_kcb_score", value=st.session_state.in_kcb_score)
    sn = cc[1].number_input("NICE 점수", key="in_nice_score", value=st.session_state.in_nice_score)
    with cc[2]:
        v = sk or 0
        st.markdown(f'<div class="summary-box">상태: <b>{"🟢 양호" if v > 700 else "🟡 주의"}</b></div>', unsafe_allow_html=True)

    # 4. 매출현황
    st.markdown("---")
    st.header("4. 매출현황")
    mc = st.columns(4)
    mc[0].number_input("금년 매출", key="in_sales_cur", placeholder=GUIDE_STR, value=st.session_state.in_sales_cur)
    mc[1].number_input("24년 매출", key="in_sales_24", placeholder=GUIDE_STR, value=st.session_state.in_sales_24)

    # 6. 인증 (글자 크기 증폭)
    st.markdown("---")
    st.header("6. 보유 인증")
    clist = ["중소기업확인서(소상공인확인서)", "창업확인서", "여성기업확인서", "이노비즈", "벤처인증", "뿌리기업확인서", "ISO인증", "HACCP인증"]
    for i in range(0, 8, 4):
        cols = st.columns(4)
        for j in range(4): cols[j].checkbox(clist[i+j], key=f"in_cert_{i+j}")

    # 8. 비즈니스 상세
    st.markdown("---")
    st.header("8. 비즈니스 상세 정보")
    st.text_area("핵심 아이템 및 비즈니스 모델 상세", key="in_item_desc", height=150)
    st.text_area("보유 특허 및 정부지원 수혜이력", key="in_pat_desc", height=100)

    # 9. 자금계획
    st.markdown("---")
    st.header("9. 자금 계획")
    c9 = st.columns([1, 2])
    c9[0].number_input("조달 필요 금액(만원)", key="in_req_funds", placeholder=GUIDE_STR, value=st.session_state.in_req_funds)
    c9[1].text_area("상세 자금 집행 계획", key="in_fund_plan")

# ==========================================
# 5. 메인 화면 - 리포트 모드 (완벽 분석)
# ==========================================
else:
    if st.button("⬅️ 대시보드 입력화면으로 돌아가기"):
        st.session_state["view_mode"] = "INPUT"; st.rerun()

    biz_name = st.session_state.in_company_name
    api_key = st.session_state["settings"].get("api_key", "")
    
    # 세션에 저장된 모든 값을 딕셔너리로 추출 (AI 전달용)
    current_data = {k: st.session_state[k] for k in INPUT_KEYS + CERT_KEYS}

    if not api_key: st.error("API Key를 먼저 저장해 주세요.")
    else:
        with st.status(f"🚀 {biz_name} 리포트 정밀 분석 및 생성 중..."):
            report_html = generate_ai_report(api_key, current_data)
            components.html(report_html, height=1500, scrolling=True)
