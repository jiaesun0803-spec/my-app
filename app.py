# =========================================================
# AI Consulting Dashboard (Full Version - Restored UI)
# 기존 대시보드 UI 유지 + GitHub 실행 가능 버전
# =========================================================

import streamlit as st
import json
import os
import streamlit.components.v1 as components

# ===============================
# Optional AI Providers
# ===============================
try:
    import google.generativeai as genai
except:
    genai = None

try:
    from openai import OpenAI
except:
    OpenAI = None


# ===============================
# File Paths
# ===============================
SETTINGS_FILE = "settings.json"
DATA_FILE = "companies_data.json"


# ===============================
# Settings Load / Save
# ===============================
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {
        "provider": "gemini",
        "api_key": "",
        "model": "gemini-1.5-flash-latest"
    }


def save_settings(provider, api_key, model):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "provider": provider,
            "api_key": api_key,
            "model": model
        }, f, ensure_ascii=False, indent=4)


# ===============================
# Company Save / Load
# ===============================
def load_companies():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}


def save_companies(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# ===============================
# AI Report Engine
# ===============================
def generate_ai_report(settings, data, mode):

    provider = settings["provider"]
    api_key = settings["api_key"]
    model_name = settings["model"]

    prompts = {
        "REPORT": "이 기업의 시장 경쟁력과 성장 가능성을 분석한 전문 경영 리포트를 HTML 형식으로 작성해줘.",
        "MATCHING": "이 기업의 조건에 가장 적합한 정부지원 정책자금 3가지를 매칭하여 리포트해줘.",
        "LOAN_PLAN": "금융권 및 기관 제출용 사업계획서 핵심 요약본을 전문적인 톤으로 작성해줘.",
        "AI_PLAN": "이 기업의 신규 사업 아이템을 기반으로 한 미래 비전 사업계획서를 HTML 형식으로 작성해줘."
    }

    prompt = f"""
[기업 정보]
기업명: {data.get('in_company_name')}
업종: {data.get('in_industry')}
핵심 아이템: {data.get('in_item_desc')}

요청:
{prompts.get(mode)}
"""

    try:

        if provider == "gemini":

            if genai is None:
                return "<h3>Gemini 라이브러리 없음</h3>"

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text.replace("```html", "").replace("```", "")

        elif provider == "openai":

            if OpenAI is None:
                return "<h3>OpenAI 라이브러리 없음</h3>"

            client = OpenAI(api_key=api_key)
            response = client.responses.create(
                model=model_name,
                input=prompt
            )
            return response.output_text

    except Exception as e:
        return f"<div style='color:red;'>AI 오류: {str(e)}</div>"


# ===============================
# Streamlit Page Setup
# ===============================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")


# ===============================
# Session Init
# ===============================
if "settings" not in st.session_state:
    st.session_state.settings = load_settings()

if "company_list" not in st.session_state:
    st.session_state.company_list = load_companies()

if "view_mode" not in st.session_state:
    st.session_state.view_mode = "INPUT"


# ===============================
# Sidebar
# ===============================
st.sidebar.header("⚙️ AI 엔진 설정")

provider = st.sidebar.selectbox(
    "Provider",
    ["gemini", "openai"]
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


# ===============================
# Company Save / Load Sidebar
# ===============================
st.sidebar.markdown("---")
st.sidebar.header("📁 업체 관리")

company_name = st.sidebar.text_input("기업명 입력")

if st.sidebar.button("현재 정보 저장"):

    if company_name:

        data = {
            k: v for k, v in st.session_state.items()
            if k.startswith("in_")
        }

        st.session_state.company_list[company_name] = data
        save_companies(st.session_state.company_list)
        st.success("저장 완료")

if st.session_state.company_list:

    target = st.sidebar.selectbox(
        "업체 선택",
        list(st.session_state.company_list.keys())
    )

    if st.sidebar.button("불러오기"):

        loaded = st.session_state.company_list[target]

        for k, v in loaded.items():
            st.session_state[k] = v

        st.success("불러오기 완료")


# ===============================
# Report Sidebar Buttons
# ===============================
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

    if st.sidebar.button(LABELS[i], use_container_width=True):

        st.session_state.view_mode = MODES[i]


# ===============================
# Top Buttons
# ===============================
st.title("📊 AI 컨설팅 대시보드")

cols = st.columns(4)

for i in range(4):

    if cols[i].button(LABELS[i], use_container_width=True):

        st.session_state.view_mode = MODES[i]


st.markdown("---")


# ===============================
# INPUT MODE
# ===============================
if st.session_state.view_mode == "INPUT":

    st.header("기업 정보")

    st.text_input("기업명", key="in_company_name")
    st.text_input("업종", key="in_industry")
    st.text_area("핵심 아이템", key="in_item_desc")

else:

    if st.button("⬅ 입력 화면으로 돌아가기"):
        st.session_state.view_mode = "INPUT"

    data = {
        k: v for k, v in st.session_state.items()
        if k.startswith("in_")
    }

    if not st.session_state.settings["api_key"]:
        st.error("API KEY 입력 필요")

    else:

        html = generate_ai_report(
            st.session_state.settings,
            data,
            st.session_state.view_mode
        )

        components.html(html, height=1200, scrolling=True)
