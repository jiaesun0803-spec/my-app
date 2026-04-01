import streamlit as st
import json
import os
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
        except:
            return {"api_key": ""}
    return {"api_key": ""}


def save_settings(api_key):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump({"api_key": api_key}, f, ensure_ascii=False, indent=4)


def load_companies():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_companies(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# ==========================================
# 1. AI 리포트 생성 엔진
# ==========================================

def generate_ai_report(api_key, data, mode):

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash-latest')

    prompts = {
        "REPORT": "이 기업의 시장 경쟁력과 성장 가능성을 분석한 전문 경영 리포트를 HTML 형식으로 작성해줘.",
        "MATCHING": "이 기업의 조건에 가장 적합한 정부지원 정책자금 3가지를 매칭하여 리포트해줘.",
        "LOAN_PLAN": "금융권 및 기관 제출용 사업계획서 핵심 요약본을 전문적인 톤으로 작성해줘.",
        "AI_PLAN": "이 기업의 신규 사업 아이템을 기반으로 한 미래 비전 사업계획서를 HTML 형식으로 작성해줘."
    }

    base_prompt = f"""
    기업명: {data.get('in_company_name')}
    업종: {data.get('in_industry')}
    핵심 아이템: {data.get('in_item_desc')}

    {prompts[mode]}
    """

    response = model.generate_content(base_prompt)

    return response.text.replace("```html", "").replace("```", "")


# ==========================================
# 2. 기본 설정
# ==========================================

st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")


if "view_mode" not in st.session_state:
    st.session_state.view_mode = "INPUT"

if "settings" not in st.session_state:
    st.session_state.settings = load_settings()

if "company_list" not in st.session_state:
    st.session_state.company_list = load_companies()

if "active_company" not in st.session_state:
    st.session_state.active_company = ""


# ==========================================
# 3. 사이드바
# ==========================================

st.sidebar.header("⚙️ AI 엔진 설정")

saved_key = st.session_state.settings.get("api_key", "")

new_key = st.sidebar.text_input(
    "Gemini API Key 입력",
    value=saved_key,
    type="password"
)

if st.sidebar.button("💾 영구 저장"):
    save_settings(new_key)
    st.session_state.settings["api_key"] = new_key
    st.sidebar.success("저장 완료")


st.sidebar.markdown("---")
st.sidebar.header("📁 업체 관리")

tab_save, tab_load = st.sidebar.tabs(["저장", "불러오기"])


with tab_save:

    if st.button("현재 정보 저장"):

        company_name = st.session_state.get("in_company_name", "").strip()

        if company_name == "":
            st.error("기업명을 입력하세요")
        else:

            company_data = {
                k: v
                for k, v in st.session_state.items()
                if k.startswith("in_")
            }

            st.session_state.company_list[company_name] = company_data
            save_companies(st.session_state.company_list)

            st.session_state.active_company = company_name

            st.success("저장 완료")


with tab_load:

    if st.session_state.company_list:

        selected = st.selectbox(
            "업체 선택",
            list(st.session_state.company_list.keys())
        )

        if st.button("데이터 불러오기"):

            company_data = st.session_state.company_list[selected]

            for k, v in company_data.items():
                st.session_state[k] = v

            st.session_state.active_company = selected

            st.success("불러오기 완료")


# ==========================================
# 4. 상단 리포트 버튼
# ==========================================

st.title("📊 AI 컨설팅 대시보드")

col1, col2, col3, col4 = st.columns(4)

if col1.button("📊 기업진단 리포트"):
    st.session_state.view_mode = "REPORT"

if col2.button("💡 정책자금 매칭 + 보증가능성 리포트"):
    st.session_state.view_mode = "MATCHING"

if col3.button("📝 기관별 융자/사업계획서"):
    st.session_state.view_mode = "LOAN_PLAN"

if col4.button("📑 AI 사업계획서"):
    st.session_state.view_mode = "AI_PLAN"


# ==========================================
# 5. 입력 화면
# ==========================================

if st.session_state.view_mode == "INPUT":

    st.header("기업 정보 입력")

    st.text_input("기업명", key="in_company_name")
    st.text_input("업종", key="in_industry")
    st.text_area("핵심 아이템", key="in_item_desc")


# ==========================================
# 6. 리포트 화면
# ==========================================

else:

    if st.button("⬅️ 입력 화면으로 돌아가기"):
        st.session_state.view_mode = "INPUT"
        st.rerun()

    active_company = st.session_state.get("active_company", "")

    if active_company:

        saved_data = st.session_state.company_list.get(active_company, {})

        for k, v in saved_data.items():
            st.session_state[k] = v

    current_data = {
        k: v
        for k, v in st.session_state.items()
        if k.startswith("in_")
    }

    company_name = current_data.get("in_company_name", "")

    api_key = st.session_state.settings.get("api_key", "")

    if company_name == "":
        st.warning("기업 정보를 입력하고 저장 후 다시 시도하세요")

    elif api_key == "":
        st.error("API Key 입력 필요")

    else:

        with st.spinner("AI 리포트 생성중..."):

            html = generate_ai_report(
                api_key,
                current_data,
                st.session_state.view_mode
            )

            components.html(html, height=1200, scrolling=True)
