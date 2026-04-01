import streamlit as st
import json
import os
import streamlit.components.v1 as components
import google.generativeai as genai

# ==========================================
# 0. 데이터 유실 원천 차단 - 세션 강제 초기화
# ==========================================
SETTINGS_FILE = "settings.json"
DATA_FILE = "companies_data.json"
GUIDE_STR = "1억=10000으로 입력"

# 보존해야 할 모든 필드 정의
INPUT_FIELDS = [
    "in_company_name", "in_biz_type", "in_raw_biz_no", "in_raw_corp_no",
    "in_start_date", "in_biz_tel", "in_email_addr", "in_industry",
    "in_lease_status", "in_biz_addr", "in_lease_deposit", "in_lease_rent",
    "in_has_extra_biz", "in_extra_biz_info", "in_rep_name", "in_rep_major",
    "in_sales_cur", "in_sales_24", "in_req_funds", "in_fund_plan", "in_item_desc"
]
CERT_KEYS = [f"in_cert_{i}" for i in range(8)]

# [데이터 박제 로직] 앱 실행 시 모든 키를 미리 확보하여 화면 전환 시 휘발 방지
for k in INPUT_FIELDS + CERT_KEYS:
    if k not in st.session_state:
        if any(x in k for x in ["deposit", "rent", "sales", "funds"]): st.session_state[k] = None
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
# 1. 고도화된 AI 리포트 엔진 (8종 항목 & '있음' 말투)
# ==========================================
def generate_ai_report(api_key, data):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        prompt = f"""
        당신은 기업 컨설턴트입니다. 다음 정보를 바탕으로 전문적인 'AI 기업분석리포트'를 HTML로 작성하세요.
        
        [기업 정보]
        기업명: {data.get('in_company_name')}, 업종: {data.get('in_industry')}, 주요아이템: {data.get('in_item_desc')}
        매출: 금년 {data.get('in_sales_cur')}만원, 전년 {data.get('in_sales_24')}만원
        
        [작성 지침]
        1. 말투: 반드시 '있음', '함', '임' 체로 간결하게 작성할 것.
        2. 구성: 1.기업현황분석 2.SWOT분석 3.시장현황 4.경쟁사분석 5.핵심경쟁력 6.자금사용계획 7.매출전망(그래프포함) 8.성장비전 및 코멘트.
        3. 페이지분리: 각 대항목마다 <div style="page-break-before: always;"></div> 삽입.
        4. 시각화: Navy/Gray 톤의 세련된 디자인 및 HTML 그래프 포함.
        """
        response = model.generate_content(prompt)
        return response.text.replace('```html', '').replace('```', '').strip()
    except Exception as e:
        return f"<div style='color:red;'>리포트 생성 오류: {str(e)}</div>"

# ==========================================
# 2. UI 레이아웃 및 사이드바
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")
st.markdown("""
<style>
    h2 { font-weight: 700 !important; color: #1A237E !important; border: none !important; }
    [data-testid="stWidgetLabel"] p { font-size: 14px !important; }
    input::placeholder { font-size: 0.85em !important; color: #aaa !important; }
</style>
""", unsafe_allow_html=True)

if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
if "settings" not in st.session_state: st.session_state["settings"] = load_json(SETTINGS_FILE, {"api_key": ""})
if "company_list" not in st.session_state: st.session_state["company_list"] = load_json(DATA_FILE, {})

# [사이드바 - API 설정]
st.sidebar.header("⚙️ AI 엔진 설정")
api_key = st.session_state["settings"].get("api_key", "")
if api_key:
    st.sidebar.success("✅ API Key 연결됨")
    if st.sidebar.button("🔄 Key 변경"): st.session_state["settings"]["api_key"] = ""; st.rerun()
else:
    new_key = st.sidebar.text_input("Gemini API Key", type="password")
    if st.sidebar.button("💾 영구 저장"):
        save_json(SETTINGS_FILE, {"api_key": new_key}); st.session_state["settings"]["api_key"] = new_key; st.rerun()

# [사이드바 - 업체 관리 (저장/불러오기)]
st.sidebar.markdown("---")
st.sidebar.header("📁 업체 관리")
t_s, t_l = st.sidebar.tabs(["💾 저장하기", "📂 불러오기"])
with t_s:
    if st.button("현재 정보 파일 저장", use_container_width=True):
        c_name = st.session_state.in_company_name.strip()
        if c_name:
            st.session_state["company_list"][c_name] = {k: st.session_state[k] for k in INPUT_FIELDS + CERT_KEYS}
            save_json(DATA_FILE, st.session_state["company_list"])
            st.success(f"'{c_name}' 저장 완료!")
        else: st.error("기업명을 먼저 입력하세요.")

with t_l:
    if st.session_state["company_list"]:
        target = st.selectbox("업체 선택", options=list(st.session_state["company_list"].keys()))
        if st.button("데이터 불러오기", use_container_width=True):
            for k, v in st.session_state["company_list"][target].items(): st.session_state[k] = v
            st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("📊 AI 기업분석리포트 시작", use_container_width=True):
    # [핵심] 리포트 생성 전 현재 세션의 기업명을 최종 확인
    if st.session_state.in_company_name:
        st.session_state["view_mode"] = "REPORT"; st.rerun()
    else: st.sidebar.warning("기업명을 입력하고 [저장하기] 버튼을 눌러주세요.")

# ==========================================
# 3. 메인 대시보드 화면
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
t_cols = st.columns(4)
btns = ["📊 AI 기업분석리포트", "💡 AI 정책자금 매칭", "📝 융자/사업계획서", "📑 AI 사업계획서"]
for i, b in enumerate(btns):
    if t_cols[i].button(b, key=f"t_{i}", use_container_width=True, type="primary"):
        if st.session_state.in_company_name:
            st.session_state["view_mode"] = "REPORT"; st.rerun()
        else: st.error("기업명을 입력하세요.")

st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

if st.session_state["view_mode"] == "INPUT":
    # 1. 기업현황 (최종 정렬 구조)
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
    c3[2].number_input("보증금(만원)", key="in_lease_deposit", placeholder=GUIDE_STR)
    c3[3].number_input("월임대료(만원)", key="in_lease_rent", placeholder=GUIDE_STR)
    
    c4 = st.columns([1.2, 3, 1.8])
    c4[0].radio("추가 사업장 여부", ["없음", "있음"], key="in_has_extra_biz", horizontal=True)
    c4[1].text_input("추가사업장 정보입력", key="in_extra_biz_info")
    
    st.markdown("---")
    st.header("8. 비즈니스 상세 정보")
    st.text_area("핵심 아이템 및 비즈니스 모델 상세", key="in_item_desc", height=150)

    st.markdown("---")
    st.header("9. 자금 계획")
    c9 = st.columns([1, 2])
    c9[0].number_input("조달 필요 금액(만원)", key="in_req_funds", placeholder=GUIDE_STR)
    c9[1].text_area("상세 자금 집행 계획", key="in_fund_plan")

else:
    # ------------------------------------------
    # 리포트 출력 모드 (데이터 강제 동기화 후 생성)
    # ------------------------------------------
    if st.button("⬅️ 입력 화면으로 돌아가기"): st.session_state["view_mode"] = "INPUT"; st.rerun()
    
    # [핵심] 화면에는 없지만 메모리에 저장된 데이터들을 딕셔너리로 취합
    final_data = {k: st.session_state[k] for k in INPUT_FIELDS + CERT_KEYS}
    biz_name = str(st.session_state.in_company_name).strip()
    
    if not api_key: st.error("사이드바에서 API Key를 먼저 저장해 주세요.")
    elif not biz_name: 
        st.warning("⚠️ 기업 정보가 유실되었습니다. 입력 화면에서 다시 한 번 [저장하기]를 눌러주세요.")
    else:
        with st.status(f"🚀 {biz_name} 리포트 정밀 분석 및 생성 중..."):
            report_html = generate_ai_report(api_key, final_data)
            components.html(report_html, height=1500, scrolling=True)
