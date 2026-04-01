# =========================================================
# AI Consulting Dashboard (GitHub Deployable Full Version)
# Streamlit 기반 컨설턴트용 AI 경영 진단 시스템
# =========================================================

import streamlit as st
import json
import os
import time
from datetime import datetime
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
# File Settings
# ===============================
SETTINGS_FILE = "settings.json"
DATA_FILE = "companies_data.json"


DEFAULT_SETTINGS = {
    "provider": "gemini",
    "api_key": "",
    "model_name": "gemini-1.5-flash-latest"
}


# ===============================
# Load / Save Settings
# ===============================
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_SETTINGS.copy()


def save_settings(provider, api_key, model_name):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "provider": provider,
            "api_key": api_key,
            "model_name": model_name
        }, f, ensure_ascii=False, indent=4)


# ===============================
# Load / Save Companies
# ===============================
def load_companies():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_companies(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# ===============================
# Initialize Session
# ===============================
if "settings" not in st.session_state:
    st.session_state.settings = load_settings()

if "companies" not in st.session_state:
    st.session_state.companies = load_companies()

if "view_mode" not in st.session_state:
    st.session_state.view_mode = "INPUT"

if "report_type" not in st.session_state:
    st.session_state.report_type = "기업 진단 리포트"


# ===============================
# Utility Functions
# ===============================
def safe_int(value):
    try:
        return int(float(value))
    except:
        return 0


def business_months(start):
    try:
        dt = datetime.strptime(start, "%Y.%m.%d")
        today = datetime.today()
        return (today.year - dt.year) * 12 + (today.month - dt.month)
    except:
        return 0


def debt_ratio(sales, debt):
    if sales == 0:
        return 0
    return round(debt / sales * 100, 1)


# ===============================
# Policy Score Engine
# ===============================
def calc_policy_score(data):

    score = 0

    credit = safe_int(data.get("credit", 0))
    if credit >= 900:
        score += 20
    elif credit >= 800:
        score += 15
    elif credit >= 700:
        score += 10
    else:
        score += 5

    months = business_months(data.get("start_date", ""))
    if months >= 36:
        score += 15
    elif months >= 12:
        score += 10
    else:
        score += 5

    sales = safe_int(data.get("sales", 0))
    if sales >= 100000:
        score += 15
    elif sales >= 10000:
        score += 10
    else:
        score += 5

    debt = safe_int(data.get("debt", 0))
    ratio = debt_ratio(sales, debt)

    if ratio < 50:
        score += 15
    elif ratio < 100:
        score += 10
    else:
        score += 5

    if data.get("cert", False):
        score += 10

    if data.get("patent", False):
        score += 10

    if data.get("export", False):
        score += 15

    return score


def policy_grade(score):

    if score >= 75:
        return "가능"
    elif score >= 60:
        return "유망"
    elif score >= 40:
        return "보완필요"
    else:
        return "어려움"


# ===============================
# Guarantee Probability Engine
# ===============================
def guarantee_probability(score):

    if score >= 80:
        return "승인 가능성 높음", 85
    elif score >= 65:
        return "조건부 가능", 70
    elif score >= 50:
        return "보완 필요", 55
    else:
        return "승인 어려움", 30


# ===============================
# AI Generator
# ===============================
def generate_ai_report(prompt):

    settings = st.session_state.settings

    if settings["provider"] == "gemini":

        if genai is None:
            return "<h3>Gemini 패키지 없음</h3>"

        genai.configure(api_key=settings["api_key"])
        model = genai.GenerativeModel(settings["model_name"])

        response = model.generate_content(prompt)
        return response.text

    elif settings["provider"] == "openai":

        if OpenAI is None:
            return "<h3>OpenAI 패키지 없음</h3>"

        client = OpenAI(api_key=settings["api_key"])

        response = client.responses.create(
            model=settings["model_name"],
            input=prompt
        )

        return response.output_text


# ===============================
# Sidebar
# ===============================
st.sidebar.title("⚙️ AI 설정")

provider = st.sidebar.selectbox(
    "Provider",
    ["gemini", "openai"],
    index=0
)

model = st.sidebar.text_input(
    "Model",
    value="gemini-1.5-flash-latest"
)

api_key = st.sidebar.text_input(
    "API Key",
    type="password"
)

if st.sidebar.button("저장"):
    save_settings(provider, api_key, model)
    st.success("저장 완료")


# ===============================
# Company Save
# ===============================
st.sidebar.title("📁 업체 저장")

company_name = st.sidebar.text_input("업체명")

if st.sidebar.button("현재 업체 저장"):

    st.session_state.companies[company_name] = st.session_state.get("company_data", {})

    save_companies(st.session_state.companies)

    st.success("저장 완료")


# ===============================
# Load Company
# ===============================
if st.session_state.companies:

    selected_company = st.sidebar.selectbox(
        "업체 선택",
        list(st.session_state.companies.keys())
    )

    if st.sidebar.button("불러오기"):

        st.session_state.company_data = st.session_state.companies[selected_company]

        st.success("불러오기 완료")


# ===============================
# Main UI
# ===============================
st.title("📊 AI 컨설팅 대시보드")


company = {}

company["name"] = st.text_input("기업명")
company["industry"] = st.text_input("업종")
company["start_date"] = st.text_input("사업개시일 (YYYY.MM.DD)")
company["sales"] = st.number_input("매출 (만원)")
company["debt"] = st.number_input("부채 (만원)")
company["credit"] = st.number_input("신용점수")
company["cert"] = st.checkbox("인증 보유")
company["patent"] = st.checkbox("특허 보유")
company["export"] = st.checkbox("수출 여부")

st.session_state.company_data = company


# ===============================
# Score Result
# ===============================
score = calc_policy_score(company)
grade = policy_grade(score)
guarantee_text, probability = guarantee_probability(score)


st.subheader("정책자금 가능성")

st.metric("점수", score)
st.metric("등급", grade)

st.subheader("보증 가능성")

st.metric("판단", guarantee_text)
st.metric("확률", f"{probability}%")


# ===============================
# AI Report Generate
# ===============================
if st.button("AI 리포트 생성"):

    prompt = f"""
기업명: {company["name"]}
업종: {company["industry"]}
매출: {company["sales"]}
부채: {company["debt"]}
신용점수: {company["credit"]}
정책자금 점수: {score}
정책자금 등급: {grade}

이 기업에 대한 컨설팅 리포트를 작성하세요.
"""

    html = generate_ai_report(prompt)

    components.html(html, height=800, scrolling=True)
