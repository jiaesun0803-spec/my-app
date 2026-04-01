import streamlit as st
import json
import os
import time
import streamlit.components.v1 as components
import google.generativeai as genai

# ==========================================
# 0. 데이터 유실 방지 - 세션 상태 강제 초기화
# ==========================================
SETTINGS_FILE = "settings.json"
DATA_FILE = "companies_data.json"

# 모든 입력 필드 키 리스트 (이 키들은 화면 전환 시에도 보존됨)
input_keys = [
    "in_company_name", "in_biz_type", "in_raw_biz_no", "in_raw_corp_no",
    "in_start_date", "in_biz_tel", "in_email_addr", "in_industry",
    "in_lease_status", "in_biz_addr", "in_lease_deposit", "in_lease_rent",
    "in_has_extra_biz", "in_extra_biz_info", "in_rep_name", "in_rep_dob",
    "in_rep_phone", "in_rep_carrier", "in_home_addr", "in_home_status",
    "in_real_estate", "in_edu_level", "in_rep_major", "in_rep_career_1",
    "in_rep_career_2", "in_fin_delinquency", "in_tax_delinquency",
    "in_kcb_score", "in_nice_score", "in_export_revenue", "in_planned_export",
    "in_sales_cur", "in_sales_24", "in_item_desc", "in_req_funds", "in_fund_plan"
]

# 앱 시작 시 메모리 공간 선점 (데이터 증발 방지의 핵심)
for key in input_keys:
    if key not in st.session_state:
        if any(x in key for x in ["score", "deposit", "rent", "sales", "funds"]):
            st.session_state[key] = None
        else:
            st.session_state[key] = ""

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
# 1. AI 리포트 생성 엔진 (8단계 구성 및 '있음' 말투)
# ==========================================
def generate_ai_report(api_key, data):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        # 대표님이 요청하신 8가지 항목 구성
        prompt = f"""
        당신은 중소기업 컨설턴트입니다. 다음 데이터를 바탕으로 전문 '기업분석리포트'를 HTML로 작성하세요.
        [데이터] 기업명: {data.get('in_company_name')}, 업종: {data.get('in_industry')}, 주요아이템: {data.get('in_item_desc')}
        
        [작성 지침]
        1. 말투: 반드시 '있음', '함', '임' 체로 간결하게 작성.
        2. 구성: 1.기업현황분석 2.SWOT분석 3.시장현황 4.경쟁사비교 5.핵심경쟁력 6.자금사용계획 7.매출전망(그래프포함) 8.성장비전 및 코멘트.
        3. 페이지분리: 각 대항목 시작 전 <div style="page-break-before: always;"></div> 삽입.
        4. 디자인: Navy와 Gray톤의 정갈한 표와 박스 사용.
        """
        response = model.generate_content(prompt)
        return response.text.replace('```html', '').replace('```', '').strip()
    except Exception as e:
        return f"<div style='color:red;'>리포트 생성 중 오류: {str(e)}</div>"

# ==========================================
# 2. 디자인 및 초기 세션 설정
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

st.markdown("""
<style>
    [data-testid="stWidgetLabel"] p { font-weight: 400 !important; font-size: 14px !important; color: #31333F !important; }
    h2 { font-weight: 700 !important; margin-top: 25px !important; color: #1A237E; border: none !important; }
    input::placeholder { font-size: 0.85em !important; color: #aaa !important; }
    .summary-box-compact { background-color: #E8F5E9; padding: 12px; border-radius: 10px; height: 145px; border: 1px solid #ddd; text-align: center; display: flex; flex-direction: column; justify-content: center; }
    .score-result-box { background-color: #F1F8E9; padding: 12px; border-radius: 10px; height: 145px; border: 1px solid #C8E6C9; text-align: center; display: flex; flex-direction: column; justify-content: center; }
</style>
""", unsafe_allow_html=True)

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
if "settings" not in st.session_state: st.session_state["settings"] = load_json(SETTINGS_FILE, {"api_key": ""})
if "company_list" not in st.session_state: st.session_state["company_list"] = load_json(DATA_FILE, {})

# ==========================================
# 3. 사이드바 (API 및 업체 관리)
# ==========================================
st.sidebar.header("⚙️ AI 엔진 설정")
api_key = st.session_state["settings"].get("api_key", "")
if api_key:
    st.sidebar.success("✅ API Key 연결됨")
    if st.sidebar.button("🔄 API Key 변경"):
        st.session_state["settings"]["api_key"] = ""; st.rerun()
else:
    new_key = st.sidebar.text_input("Gemini API Key 입력", type="password")
    if st.sidebar.button("💾 영구 저장"):
        save_json(SETTINGS_FILE, {"api_key": new_key}); st.session_state["settings"]["api_key"] = new_key; st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("📁 업체 관리")
tab_save, tab_load = st.sidebar.tabs(["💾 저장하기", "📂 불러오기"])

with tab_save:
    if st.button("현재 정보 저장", use_container_width=True):
        c_name = st.session_state.in_company_name.strip()
        if c_name:
            st.session_state["company_list"][c_name] = {k: st.session_state[k] for k in input_keys}
            save_json(DATA_FILE, st.session_state["company_list"])
            st.success(f"'{c_name}' 저장 완료!")
        else: st.error("기업명을 입력하세요.")

with tab_load:
    if st.session_state["company_list"]:
        target = st.selectbox("업체 선택", options=list(st.session_state["company_list"].keys()))
        if st.button("데이터 불러오기", use_container_width=True):
            for k, v in st.session_state["company_list"][target].items():
                st.session_state[k] = v
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🚀 리포트 생성")
s_modes = ["REPORT", "MATCHING", "LOAN_PLAN", "AI_PLAN"]
s_labels = ["📊 AI 기업분석리포트", "💡 AI 정책자금 매칭", "📝 기관별 융자/사업계획서", "📑 AI 사업계획서"]
for i in range(4):
    if st.sidebar.button(s_labels[i], key=f"side_{i}", use_container_width=True):
        st.session_state["view_mode"] = s_modes[i]; st.rerun()

# ==========================================
# 4. 메인 화면 구성
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
t_cols = st.columns(4)
for i in range(4):
    if t_cols[i].button(s_labels[i], key=f"t_{i}", use_container_width=True, type="primary"):
        st.session_state["view_mode"] = s_modes[i]; st.rerun()
st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

GUIDE_STR = "1억=10000으로 입력"

if st.session_state["view_mode"] == "INPUT":
    # --- 1. 기업현황 (레이아웃 최종 정렬) ---
    st.header("1. 기업현황")
    c1_f1 = st.columns([2, 1, 1.5, 1.5])
    c1_f1[0].text_input("기업명", key="in_company_name")
    c1_f1[1].radio("사업자유형", ["개인", "법인"], key="in_biz_type", horizontal=True)
    c1_f1[2].text_input("사업자번호", key="in_raw_biz_no", placeholder="000-00-00000")
    c1_f1[3].text_input("법인등록번호", key="in_raw_corp_no", placeholder="000000-0000000")
    
    c1_f2 = st.columns([1, 1, 1, 1])
    c1_f2[0].text_input("사업개시일", key="in_start_date", placeholder="YYYY.MM.DD")
    c1_f2[1].text_input("사업장 전화번호", key="in_biz_tel", placeholder="000-00-0000")
    c1_f2[2].text_input("이메일 주소", key="in_email_addr", placeholder="example@email.com")
    c1_f2[3].selectbox("현사업장 업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")
    
    c1_f3 = st.columns([1.2, 3, 0.9, 0.9])
    c1_f3[0].radio("사업장 임대여부", ["자가", "임대"], key="in_lease_status", horizontal=True)
    c1_f3[1].text_input("사업장 주소", key="in_biz_addr")
    c1_f3[2].number_input("보증금 (만원)", key="in_lease_deposit", placeholder=GUIDE_STR)
    c1_f3[3].number_input("월임대료 (만원)", key="in_lease_rent", placeholder=GUIDE_STR)
    
    c1_f4 = st.columns([1.2, 3, 1.8])
    c1_f4[0].radio("추가 사업장 여부", ["없음", "있음"], key="in_has_extra_biz", horizontal=True)
    c1_f4[1].text_input("추가사업장 정보입력", key="in_extra_biz_info")
    
    st.markdown("---")
    st.header("8. 비즈니스 상세 정보")
    st.text_area("핵심 아이템 및 비즈니스 모델 상세", key="in_item_desc", height=150)

    st.markdown("---")
    st.header("9. 자금 계획")
    c9 = st.columns([1, 2])
    c9[0].number_input("조달 필요 자금 (만원)", key="in_req_funds", placeholder=GUIDE_STR)
    c9[1].text_area("상세 자금 집행 계획", key="in_fund_plan")

else:
    # --- 리포트 출력 모드 ---
    if st.button("⬅️ 입력 화면으로 돌아가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    
    # [핵심 수동 데이터 펌핑] 현재 세션에 있는 모든 값을 취합
    current_data = {k: st.session_state[k] for k in input_keys}
    biz_name = str(st.session_state.in_company_name).strip()
    
    if not api_key: st.error("사이드바에서 API Key를 먼저 저장해 주세요.")
    elif not biz_name or biz_name == "": 
        st.warning("⚠️ 기업명을 입력하고 [저장하기] 탭에서 저장 후 진행하세요.")
    else:
        with st.status(f"🚀 {biz_name} 전문 기업분석리포트 생성 중..."):
            res_html = generate_ai_report(api_key, current_data)
            components.html(res_html, height=1500, scrolling=True)
