# =========================================================
# AI Consulting Dashboard (STABLE FINAL VERSION)
# 업체 상태 유지 / 리포트 오류 해결 / GitHub 실행 안정화
# =========================================================

import streamlit as st
import json
import os
import streamlit.components.v1 as components

# =========================================================
# Optional AI Providers
# =========================================================

try:
    import google.generativeai as genai
except:
    genai = None

try:
    from openai import OpenAI
except:
    OpenAI = None


# =========================================================
# Files
# =========================================================

SETTINGS_FILE = "settings.json"
DATA_FILE = "companies_data.json"


# =========================================================
# Default Settings
# =========================================================

DEFAULT_SETTINGS = {
    "provider": "gemini",
    "api_key": "",
    "model": "gemini-1.5-flash-latest"
}


# =========================================================
# Load Settings (KeyError 방지)
# =========================================================

def load_settings():

    if os.path.exists(SETTINGS_FILE):

        try:

            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:

                data = json.load(f)

                merged = DEFAULT_SETTINGS.copy()
                merged.update(data)

                return merged

        except:

            pass

    return DEFAULT_SETTINGS.copy()


# =========================================================
# Save Settings
# =========================================================

def save_settings(provider, api_key, model):

    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:

        json.dump({

            "provider": provider,
            "api_key": api_key,
            "model": model

        }, f, ensure_ascii=False, indent=4)


# =========================================================
# Load Companies
# =========================================================

def load_companies():

    if os.path.exists(DATA_FILE):

        try:

            with open(DATA_FILE, "r", encoding="utf-8") as f:

                return json.load(f)

        except:

            return {}

    return {}


# =========================================================
# Save Companies
# =========================================================

def save_companies(data):

    with open(DATA_FILE, "w", encoding="utf-8") as f:

        json.dump(data, f, ensure_ascii=False, indent=4)


# =========================================================
# Session Init
# =========================================================

if "settings" not in st.session_state:

    st.session_state.settings = load_settings()

if "company_list" not in st.session_state:

    st.session_state.company_list = load_companies()

if "active_company" not in st.session_state:

    st.session_state.active_company = ""

if "view_mode" not in st.session_state:

    st.session_state.view_mode = "INPUT"


# =========================================================
# AI REPORT ENGINE
# =========================================================

def generate_ai_report(settings, data, mode):

    provider = settings["provider"]
    api_key = settings["api_key"]
    model = settings["model"]

    prompts = {

        "REPORT": "이 기업의 시장 경쟁력과 성장 가능성을 분석한 전문 경영 리포트를 HTML 형식으로 작성해줘.",

        "MATCHING": "이 기업 조건에 가장 적합한 정책자금 3가지를 추천하고 이유를 설명해줘.",

        "LOAN_PLAN": "금융기관 제출용 사업계획서 요약본을 작성해줘.",

        "AI_PLAN": "이 기업의 미래 성장 전략을 포함한 신규사업 계획서를 작성해줘."

    }

    prompt = f"""
기업명: {data.get('in_company_name')}
업종: {data.get('in_industry')}
핵심 아이템: {data.get('in_item_desc')}

요청:
{prompts.get(mode)}
HTML 형식으로 작성
"""

    try:

        if provider == "gemini":

            genai.configure(api_key=api_key)

            model = genai.GenerativeModel(model)

            res = model.generate_content(prompt)

            return res.text

        else:

            client = OpenAI(api_key=api_key)

            res = client.responses.create(

                model=model,
                input=prompt

            )

            return res.output_text

    except Exception as e:

        return f"<h3 style='color:red;'>AI 오류: {str(e)}</h3>"


# =========================================================
# PAGE SETUP
# =========================================================

st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")


# =========================================================
# SIDEBAR SETTINGS
# =========================================================

st.sidebar.header("⚙️ AI 엔진 설정")

provider = st.sidebar.selectbox(

    "Provider",
    ["gemini", "openai"],
    index=0 if st.session_state.settings["provider"] == "gemini" else 1

)

model = st.sidebar.text_input(

    "Model",
    value=st.session_state.settings["model"]

)

api_key = st.sidebar.text_input(

    "API Key",
    value=st.session_state.settings["api_key"],
    type="password"

)

if st.sidebar.button("💾 저장"):

    save_settings(provider, api_key, model)

    st.session_state.settings = load_settings()

    st.success("저장 완료")


# =========================================================
# COMPANY SAVE / LOAD
# =========================================================

st.sidebar.markdown("---")
st.sidebar.header("📁 업체 관리")

company_name = st.sidebar.text_input(

    "기업명 입력",
    value=st.session_state.active_company

)


# 저장

if st.sidebar.button("현재 정보 저장"):

    if company_name:

        current_data = {

            k: v for k, v in st.session_state.items()

            if k.startswith("in_")

        }

        current_data["in_company_name"] = company_name

        st.session_state.company_list[company_name] = current_data

        save_companies(st.session_state.company_list)

        st.session_state.active_company = company_name

        st.success("저장 완료")


# 불러오기

if st.session_state.company_list:

    selected = st.sidebar.selectbox(

        "업체 선택",
        list(st.session_state.company_list.keys())

    )

    if st.sidebar.button("데이터 불러오기"):

        data = st.session_state.company_list[selected]

        for k, v in data.items():

            st.session_state[k] = v

        st.session_state.active_company = selected

        st.success("불러오기 완료")


# =========================================================
# REPORT BUTTONS
# =========================================================

st.sidebar.markdown("---")
st.sidebar.header("🚀 리포트 생성")

MODES = ["REPORT", "MATCHING", "LOAN_PLAN", "AI_PLAN"]

LABELS = [

    "📊 AI 기업분석리포트",
    "💡 정책자금 매칭",
    "📝 기관 제출 사업계획서",
    "📑 미래 사업계획서"

]

for i in range(4):

    if st.sidebar.button(LABELS[i]):

        st.session_state.view_mode = MODES[i]


# =========================================================
# MAIN HEADER
# =========================================================

st.title("📊 AI 컨설팅 대시보드")

cols = st.columns(4)

for i in range(4):

    if cols[i].button(LABELS[i]):

        st.session_state.view_mode = MODES[i]


st.markdown("---")


# =========================================================
# INPUT SCREEN
# =========================================================

if st.session_state.view_mode == "INPUT":

    st.text_input("기업명", key="in_company_name")

    st.text_input("업종", key="in_industry")

    st.text_area("핵심 아이템", key="in_item_desc")


# =========================================================
# REPORT SCREEN
# =========================================================

else:

    if st.button("⬅ 입력 화면으로 돌아가기"):

        st.session_state.view_mode = "INPUT"

    data = {

        k: v for k, v in st.session_state.items()

        if k.startswith("in_")

    }

    if not st.session_state.settings["api_key"]:

        st.error("API KEY 입력 필요")

    elif not data.get("in_company_name"):

        st.warning("기업 정보를 입력하고 저장/불러오기 후 다시 시도해 주세요.")

    else:

        html = generate_ai_report(

            st.session_state.settings,
            data,
            st.session_state.view_mode

        )

        components.html(html, height=1200, scrolling=True)
