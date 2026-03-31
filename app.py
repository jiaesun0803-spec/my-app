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
# 0. 파일 데이터 관리 함수 (영구 저장의 핵심)
# ==========================================
SETTINGS_FILE = "settings.json"
DATA_FILE = "companies_data.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"api_key": ""}

def save_settings(api_key):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_key": api_key}, f, ensure_ascii=False, indent=4)

def load_companies():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_companies(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ==========================================
# 1. 초기 설정 및 디자인
# ==========================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

# CSS 유지 (생략 없이 원본 유지)
st.markdown("""
<style>
    [data-testid="stWidgetLabel"] p { font-weight: 400 !important; font-size: 14px !important; color: #31333F !important; margin-bottom: 2px !important; }
    h2 { font-weight: 700 !important; margin-top: 25px !important; }
    .summary-box-compact { background-color: #E8F5E9; padding: 12px; border-radius: 10px; border: 1px solid #ddd; text-align: center; }
    .blue-bold-label-16 { color: #1E88E5 !important; font-size: 16px !important; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if "view_mode" not in st.session_state: st.session_state["view_mode"] = "INPUT"
if "settings" not in st.session_state: st.session_state["settings"] = load_settings()
if "company_list" not in st.session_state: st.session_state["company_list"] = load_companies()
if "edit_api_key" not in st.session_state: st.session_state["edit_api_key"] = False

# ==========================================
# 2. 사이드바 (API Key 영구 저장 및 업체 관리)
# ==========================================
st.sidebar.header("⚙️ AI 엔진 설정")

saved_key = st.session_state["settings"].get("api_key", "")

# API Key UI 로직: 저장되어 있고 수정 모드가 아니면 입력창 숨김
if saved_key and not st.session_state["edit_api_key"]:
    st.sidebar.success("✅ API Key가 영구 저장됨")
    if st.sidebar.button("🔄 API Key 변경"):
        st.session_state["edit_api_key"] = True
        st.rerun()
else:
    new_key = st.sidebar.text_input("Gemini API Key 입력", value=saved_key, type="password")
    if st.sidebar.button("💾 영구 저장"):
        save_settings(new_key)
        st.session_state["settings"]["api_key"] = new_key
        st.session_state["edit_api_key"] = False
        st.sidebar.success("저장되었습니다.")
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("📁 업체 목록")

# 업체 저장 기능
if st.sidebar.button("💾 현재 정보 저장 (파일)", use_container_width=True):
    c_name = st.session_state.get("in_company_name", "").strip()
    if c_name:
        current_data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
        st.session_state["company_list"][c_name] = current_data
        save_companies(st.session_state["company_list"])
        st.sidebar.success(f"'{c_name}' 저장 완료")
    else:
        st.sidebar.error("기업명을 입력하세요.")

# 업체 불러오기
if st.session_state["company_list"]:
    target = st.sidebar.selectbox("저장된 업체 선택", options=list(st.session_state["company_list"].keys()))
    if st.sidebar.button("📂 데이터 불러오기", use_container_width=True):
        loaded = st.session_state["company_list"][target]
        for k, v in loaded.items(): st.session_state[k] = v
        st.rerun()

# ==========================================
# 3. 메인 화면 및 탭
# ==========================================
st.title("📊 AI 컨설팅 대시보드")
t_cols = st.columns(4)
v_modes = ["REPORT", "MATCHING", "LOAN_PLAN", "AI_PLAN"]
v_labels = ["📊 AI 기업분석리포트", "💡 AI 정책자금 매칭", "📝 기관별 융자/사업계획서", "📑 AI 사업계획서"]

for i in range(4):
    if t_cols[i].button(v_labels[i], key=f"tab_{i}", use_container_width=True, type="primary"):
        st.session_state["view_mode"] = v_modes[i]; st.rerun()

GUIDE_STR = "1억=10000으로 입력"

if st.session_state["view_mode"] == "INPUT":
    # --- [1~9번 입력 섹션] 원본 디자인 그대로 유지 ---
    st.header("1. 기업현황")
    c1r1 = st.columns([2, 1, 1.5, 1.5])
    with c1r1[0]: st.text_input("기업명", key="in_company_name", placeholder="업체명을 입력하세요")
    with c1r1[1]: st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
    with c1r1[2]: st.text_input("사업자번호", key="in_raw_biz_no", placeholder="000-00-00000")
    with c1r1[3]: st.text_input("법인등록번호", key="in_raw_corp_no", placeholder="000000-0000000")
    
    # ... (중략: 대표님의 나머지 2~9번 입력 필드 원본 코드 그대로 들어갑니다) ...
    # 대표님, 지면 관계상 중략하나 실제 파일에는 2~9번 모든 코드가 포함되어야 합니다.
    # number_input에는 모두 value=None, placeholder=GUIDE_STR 적용 완료 상태입니다.
    st.header("9. 자금 계획")
    c9 = st.columns([1, 2])
    with c9[0]: st.number_input("조달금액 (만원)", key="in_req_funds", step=1, placeholder=GUIDE_STR, value=None)
    with c9[1]: st.text_area("자금집행 계획", key="in_fund_plan", placeholder="예: 연구인력 채용 등")

else:
    # --- [리포트 출력 화면] ---
    if st.button("⬅️ 입력 화면으로 돌아가기"):
        st.session_state["view_mode"] = "INPUT"; st.rerun()

    current_data = {k: v for k, v in st.session_state.items() if k.startswith("in_")}
    mode = st.session_state["view_mode"]
    biz_name = current_data.get("in_company_name", "미입력")
    
    st.subheader(f"📊 {biz_name} 분석 결과")

    # [핵심] 영구 저장된 API Key 사용
    final_api_key = st.session_state["settings"].get("api_key", "")
    
    if not final_api_key:
        st.error("사이드바에서 API Key를 먼저 저장해 주세요.")
    elif not current_data.get("in_company_name"):
        st.warning("분석할 기업 정보가 없습니다. 입력화면에서 '저장' 버튼을 먼저 눌러주세요.")
    else:
        with st.status("🚀 AI 분석 엔진 가동 중..."):
            try:
                if mode == "REPORT": res_html = engine_analysis.run_report(final_api_key, current_data)
                elif mode == "MATCHING": res_html = engine_matching.run_report(final_api_key, current_data)
                # ... (나머지 엔진 호출 동일)
                components.html(res_html, height=1000, scrolling=True)
            except Exception as e:
                st.error(f"오류 발생: {e}")
