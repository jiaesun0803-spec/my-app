import streamlit as st
import json
import os
import streamlit.components.v1 as components

# =========================================================
# 0. Optional AI Providers
# =========================================================
try:
    import google.generativeai as genai
except Exception:
    genai = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# =========================================================
# 1. File Paths / Defaults
# =========================================================
SETTINGS_FILE = "settings.json"
DATA_FILE = "companies_data.json"

DEFAULT_SETTINGS = {
    "provider": "gemini",
    "api_key": "",
    "model": "gemini-1.5-flash-latest"
}

DEFAULT_INPUTS = {
    "in_company_name": "",
    "in_biz_type": "개인",
    "in_raw_biz_no": "",
    "in_raw_corp_no": "",
    "in_start_date": "",
    "in_biz_tel": "",
    "in_email_addr": "",
    "in_industry": "제조업",
    "in_lease_status": "자가",
    "in_biz_addr": "",
    "in_lease_deposit": None,
    "in_lease_rent": None,
    "in_has_extra_biz": "없음",
    "in_extra_biz_info": "",

    "in_rep_name": "",
    "in_rep_dob": "",
    "in_rep_phone": "",
    "in_rep_carrier": "선택",
    "in_home_addr": "",
    "in_home_status": "자가",
    "in_real_estate": [],
    "in_edu_level": "선택",
    "in_rep_major": "",
    "in_rep_career_1": "",
    "in_rep_career_2": "",

    "in_fin_delinquency": "없음",
    "in_tax_delinquency": "없음",
    "in_kcb_score": None,
    "in_nice_score": None,

    "in_export_revenue": "없음",
    "in_planned_export": "없음",
    "in_sales_cur": None,
    "in_sales_25": None,
    "in_sales_24": None,
    "in_sales_23": None,
    "in_exp_cur": None,
    "in_exp_25": None,
    "in_exp_24": None,
    "in_exp_23": None,

    "in_debt_kosme": None,
    "in_debt_semas": None,
    "in_debt_kodit": None,
    "in_debt_kibo": None,
    "in_debt_foundation": None,
    "in_debt_corp_coll": None,
    "in_debt_rep_cred": None,
    "in_debt_rep_coll": None,

    "in_cert_0": False,
    "in_cert_1": False,
    "in_cert_2": False,
    "in_cert_3": False,
    "in_cert_4": False,
    "in_cert_5": False,
    "in_cert_6": False,
    "in_cert_7": False,

    "in_has_patent": "없음",
    "in_pat_cnt": None,
    "in_pat_desc": "",
    "in_has_gov": "없음",
    "in_gov_cnt": None,
    "in_gov_desc": "",

    "in_item_desc": "",
    "in_sales_route": "",
    "in_item_diff": "",
    "in_market_status": "",
    "in_process_desc": "",
    "in_target_cust": "",
    "in_revenue_model": "",
    "in_future_plan": "",

    "in_req_funds": None,
    "in_fund_plan": ""
}

CERT_LIST = [
    "중소기업확인서(소상공인확인서)",
    "창업확인서",
    "여성기업확인서",
    "이노비즈",
    "벤처인증",
    "뿌리기업확인서",
    "ISO인증",
    "HACCP인증"
]

MODEL_OPTIONS = {
    "gemini": [
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro-latest"
    ],
    "openai": [
        "gpt-4.1-mini",
        "gpt-4.1",
        "gpt-4o-mini"
    ]
}

# =========================================================
# 2. Load / Save Helpers
# =========================================================
def load_settings():
    data = {}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                if isinstance(raw, dict):
                    data = raw
        except Exception:
            data = {}
    merged = DEFAULT_SETTINGS.copy()
    merged.update(data)
    return merged


def save_settings(provider, api_key, model):
    payload = {
        "provider": provider,
        "api_key": api_key,
        "model": model
    }
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=4)


def load_companies():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                if isinstance(raw, dict):
                    return raw
        except Exception:
            return {}
    return {}


def save_companies(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


# =========================================================
# 3. Session Init
# =========================================================
def init_session():
    if "view_mode" not in st.session_state:
        st.session_state["view_mode"] = "INPUT"

    if "settings" not in st.session_state:
        st.session_state["settings"] = load_settings()
    else:
        merged = DEFAULT_SETTINGS.copy()
        merged.update(st.session_state["settings"])
        st.session_state["settings"] = merged

    if "company_list" not in st.session_state:
        st.session_state["company_list"] = load_companies()

    if "edit_api_key" not in st.session_state:
        st.session_state["edit_api_key"] = False

    if "selected_company_name" not in st.session_state:
        st.session_state["selected_company_name"] = ""

    for k, v in DEFAULT_INPUTS.items():
        if k not in st.session_state:
            st.session_state[k] = v


def apply_company_data(loaded):
    merged = DEFAULT_INPUTS.copy()
    if isinstance(loaded, dict):
        merged.update(loaded)
    for k, v in merged.items():
        st.session_state[k] = v


def get_current_company_data():
    return {k: st.session_state.get(k) for k in DEFAULT_INPUTS.keys()}


# =========================================================
# 4. Utility Functions
# =========================================================
def safe_int(value):
    try:
        if value is None or value == "":
            return 0
        return int(float(str(value).replace(",", "").strip()))
    except Exception:
        return 0


def get_kcb_grade(score):
    s = safe_int(score)
    if s >= 942:
        return "1등급", "#43A047"
    elif s >= 832:
        return "3등급", "#66BB6A"
    elif s >= 630:
        return "6등급", "#EF6C00"
    else:
        return f"{s}점(등급외)", "#E53935"


def get_nice_grade(score):
    s = safe_int(score)
    if s >= 900:
        return "1등급", "#1E88E5"
    elif s >= 840:
        return "3등급", "#42A5F5"
    elif s >= 665:
        return "6등급", "#EF6C00"
    else:
        return f"{s}점(등급외)", "#E53935"


def selected_certs(data):
    result = []
    for i, name in enumerate(CERT_LIST):
        if data.get(f"in_cert_{i}", False):
            result.append(name)
    return result


def calc_total_debt(data):
    debt_keys = [
        "in_debt_kosme", "in_debt_semas", "in_debt_kodit", "in_debt_kibo",
        "in_debt_foundation", "in_debt_corp_coll", "in_debt_rep_cred", "in_debt_rep_coll"
    ]
    return sum(safe_int(data.get(k)) for k in debt_keys)


def calc_recent_sales(data):
    for key in ["in_sales_cur", "in_sales_25", "in_sales_24", "in_sales_23"]:
        v = safe_int(data.get(key))
        if v > 0:
            return v
    return 0


def calc_policy_score(data):
    score = 0
    comments = []

    avg_credit = 0
    kcb = safe_int(data.get("in_kcb_score"))
    nice = safe_int(data.get("in_nice_score"))
    if kcb > 0 and nice > 0:
        avg_credit = (kcb + nice) / 2
    else:
        avg_credit = max(kcb, nice)

    if data.get("in_fin_delinquency") == "있음" or data.get("in_tax_delinquency") == "있음":
        score += 0
        comments.append("연체/체납 이력 존재")
    else:
        if avg_credit >= 900:
            score += 20
            comments.append("신용 우수")
        elif avg_credit >= 800:
            score += 15
            comments.append("신용 양호")
        elif avg_credit >= 700:
            score += 10
            comments.append("신용 보통")
        elif avg_credit > 0:
            score += 5
            comments.append("신용 보완 필요")
        else:
            score += 5
            comments.append("신용 미입력")

    sales = calc_recent_sales(data)
    if sales >= 100000:
        score += 15
        comments.append("매출 10억 이상")
    elif sales >= 50000:
        score += 12
        comments.append("매출 5억 이상")
    elif sales >= 10000:
        score += 9
        comments.append("매출 1억 이상")
    elif sales > 0:
        score += 5
        comments.append("매출 발생")
    else:
        score += 2
        comments.append("매출 정보 부족")

    debt = calc_total_debt(data)
    if sales > 0:
        ratio = round((debt / sales) * 100, 1)
    else:
        ratio = 999 if debt > 0 else 0

    if ratio <= 30:
        score += 15
        comments.append("부채 안정")
    elif ratio <= 70:
        score += 12
        comments.append("부채 무난")
    elif ratio <= 120:
        score += 8
        comments.append("부채 보통")
    else:
        score += 4
        comments.append("부채 높음")

    cert_count = len(selected_certs(data))
    if cert_count >= 4:
        score += 10
        comments.append("인증 다수")
    elif cert_count >= 2:
        score += 7
        comments.append("인증 보유")
    elif cert_count == 1:
        score += 4
        comments.append("기본 인증 보유")
    else:
        score += 1
        comments.append("인증 없음")

    pat_cnt = safe_int(data.get("in_pat_cnt"))
    if data.get("in_has_patent") == "있음":
        if pat_cnt >= 3:
            score += 10
            comments.append("특허 다수")
        elif pat_cnt >= 1:
            score += 7
            comments.append("특허 보유")
        else:
            score += 5
            comments.append("특허 있음")
    else:
        score += 1
        comments.append("특허 없음")

    if data.get("in_export_revenue") == "있음":
        score += 15
        comments.append("수출 실적 보유")
    elif data.get("in_planned_export") == "있음":
        score += 7
        comments.append("수출 예정")
    else:
        score += 2
        comments.append("수출 없음")

    if score >= 75:
        grade = "가능"
        color = "#2E7D32"
    elif score >= 58:
        grade = "유망"
        color = "#1976D2"
    elif score >= 40:
        grade = "보완필요"
        color = "#EF6C00"
    else:
        grade = "어려움"
        color = "#C62828"

    return {
        "score": score,
        "grade": grade,
        "color": color,
        "comments": comments
    }


def estimate_guarantee(data):
    p = 50

    kcb = safe_int(data.get("in_kcb_score"))
    nice = safe_int(data.get("in_nice_score"))
    avg = max(kcb, nice) if (kcb == 0 or nice == 0) else (kcb + nice) / 2

    if avg >= 900:
        p += 18
    elif avg >= 850:
        p += 14
    elif avg >= 780:
        p += 10
    elif avg >= 700:
        p += 6
    elif avg >= 630:
        p += 2
    else:
        p -= 8

    if data.get("in_fin_delinquency") == "있음":
        p -= 25
    if data.get("in_tax_delinquency") == "있음":
        p -= 20

    sales = calc_recent_sales(data)
    if sales >= 100000:
        p += 10
    elif sales >= 30000:
        p += 7
    elif sales >= 10000:
        p += 4
    elif sales > 0:
        p += 2
    else:
        p -= 5

    debt = calc_total_debt(data)
    ratio = (debt / sales * 100) if sales > 0 else 999 if debt > 0 else 0

    if ratio <= 50:
        p += 8
    elif ratio <= 100:
        p += 4
    elif ratio <= 150:
        p += 0
    elif ratio <= 250:
        p -= 6
    else:
        p -= 12

    cert_count = len(selected_certs(data))
    if cert_count >= 3:
        p += 5
    elif cert_count >= 1:
        p += 2

    if data.get("in_has_patent") == "있음":
        p += 4

    p = max(5, min(95, int(round(p))))

    if p >= 80:
        label = "승인 가능성 높음"
        color = "#2E7D32"
    elif p >= 65:
        label = "조건부 유망"
        color = "#1976D2"
    elif p >= 50:
        label = "보완 후 검토"
        color = "#EF6C00"
    else:
        label = "승인 가능성 낮음"
        color = "#C62828"

    return {"probability": p, "label": label, "color": color}


# =========================================================
# 5. AI Report Engine
# =========================================================
def build_prompt(data, mode):
    policy = calc_policy_score(data)
    guarantee = estimate_guarantee(data)

    common = f"""
너는 정책자금, 보증기관, 중진공 사업계획서 작성에 특화된 전문 컨설턴트다.
아래 기업 정보를 바탕으로 한국어 HTML 리포트를 작성해라.

[기업 정보]
- 기업명: {data.get('in_company_name')}
- 사업자유형: {data.get('in_biz_type')}
- 업종: {data.get('in_industry')}
- 핵심 아이템: {data.get('in_item_desc')}
- 판매 루트: {data.get('in_sales_route')}
- 경쟁력: {data.get('in_item_diff')}
- 시장 현황: {data.get('in_market_status')}
- 공정도: {data.get('in_process_desc')}
- 타겟 고객: {data.get('in_target_cust')}
- 수익 모델: {data.get('in_revenue_model')}
- 향후 계획: {data.get('in_future_plan')}
- 조달 필요 자금: {safe_int(data.get('in_req_funds'))}만원
- 자금 집행 계획: {data.get('in_fund_plan')}

[재무 참고]
- 최근 매출: {calc_recent_sales(data)}만원
- 총 부채: {calc_total_debt(data)}만원

[자동 진단]
- 정책자금 점수: {policy['score']}점
- 정책자금 등급: {policy['grade']}
- 보증 확률 추정: {guarantee['probability']}%
- 보증 판단: {guarantee['label']}

[작성 조건]
- 반드시 HTML 본문 형태로 출력
- 보기 좋은 제목, 섹션, 표, 박스를 포함
- 컨설팅 보고서형 / PDF 변환용 스타일
- 과장 없이 실무적 문장으로 작성
"""

    prompts = {
        "REPORT": common + """
[리포트 목적]
기업 진단 리포트 작성.
아래 구조로 작성:
1. 요약 진단
2. 기업 현황 분석
3. 강점 / 리스크
4. 정책자금 및 보증 관점 코멘트
5. 전략 제안
""",
        "MATCHING": common + """
[리포트 목적]
정책자금 매칭 리포트 작성.
아래 구조로 작성:
1. 한눈에 보는 적합도
2. 추천 정책자금 3가지
3. 추천 사유
4. 보완 포인트
5. 즉시 진행 / 보완 후 진행 구분
""",
        "LOAN_PLAN": common + """
[리포트 목적]
금융기관 및 기관 제출용 사업계획서 핵심 요약본 작성.
아래 구조로 작성:
1. 사업 개요
2. 시장성
3. 경쟁력
4. 자금 필요성
5. 자금 활용 계획
6. 기대 효과
""",
        "AI_PLAN": common + """
[리포트 목적]
신규 사업 또는 미래 비전 사업계획서 작성.
아래 구조로 작성:
1. 미래 성장 방향
2. 신규사업 제안
3. 시장 기회
4. 실행 로드맵
5. 기대 효과
""",
    }
    return prompts.get(mode, prompts["REPORT"])


def generate_ai_report(settings, data, mode):
    provider = settings.get("provider", "gemini")
    api_key = settings.get("api_key", "")
    model_name = settings.get("model", DEFAULT_SETTINGS["model"])

    if not api_key:
        return "<div style='padding:20px;color:red;'>API Key가 설정되지 않았습니다.</div>"

    prompt = build_prompt(data, mode)

    try:
        if provider == "gemini":
            if genai is None:
                return "<div style='padding:20px;color:red;'>google-generativeai 패키지가 설치되지 않았습니다.</div>"
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            text = getattr(response, "text", "")
            return text.replace("```html", "").replace("```", "")

        if provider == "openai":
            if OpenAI is None:
                return "<div style='padding:20px;color:red;'>openai 패키지가 설치되지 않았습니다.</div>"
            client = OpenAI(api_key=api_key)
            response = client.responses.create(
                model=model_name,
                input=prompt
            )
            text = getattr(response, "output_text", "")
            return text.replace("```html", "").replace("```", "")

        return "<div style='padding:20px;color:red;'>지원하지 않는 Provider입니다.</div>"

    except Exception as e:
        policy = calc_policy_score(data)
        guarantee = estimate_guarantee(data)
        certs = ", ".join(selected_certs(data)) if selected_certs(data) else "없음"

        fallback_html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
                    background:#f7f9fc;
                    color:#1f2937;
                    padding:24px;
                }}
                .wrap {{
                    max-width:1100px;
                    margin:0 auto;
                    background:white;
                    border-radius:18px;
                    padding:36px;
                    box-shadow:0 8px 24px rgba(0,0,0,0.06);
                }}
                .title {{
                    font-size:30px;
                    font-weight:800;
                    margin-bottom:8px;
                }}
                .sub {{
                    color:#64748b;
                    margin-bottom:24px;
                }}
                .box {{
                    background:#f8fafc;
                    border:1px solid #e2e8f0;
                    border-radius:14px;
                    padding:16px;
                    margin-bottom:16px;
                }}
                table {{
                    width:100%;
                    border-collapse:collapse;
                    margin-top:10px;
                }}
                th, td {{
                    border:1px solid #cbd5e1;
                    padding:10px;
                    text-align:left;
                    font-size:14px;
                }}
                th {{
                    background:#e2e8f0;
                }}
            </style>
        </head>
        <body>
            <div class="wrap">
                <div class="title">{data.get('in_company_name', '기업')} 자동 리포트</div>
                <div class="sub">AI 생성 실패로 기본 리포트를 표시합니다.</div>

                <div class="box">
                    <b>정책자금 점수:</b> {policy['score']}점 / {policy['grade']}<br>
                    <b>보증 가능성:</b> {guarantee['probability']}% / {guarantee['label']}
                </div>

                <div class="box">
                    <h3>기업 기본 정보</h3>
                    <table>
                        <tr><th>기업명</th><td>{data.get('in_company_name', '')}</td></tr>
                        <tr><th>업종</th><td>{data.get('in_industry', '')}</td></tr>
                        <tr><th>핵심 아이템</th><td>{data.get('in_item_desc', '')}</td></tr>
                        <tr><th>판매 루트</th><td>{data.get('in_sales_route', '')}</td></tr>
                        <tr><th>경쟁력</th><td>{data.get('in_item_diff', '')}</td></tr>
                        <tr><th>시장 현황</th><td>{data.get('in_market_status', '')}</td></tr>
                        <tr><th>타겟 고객</th><td>{data.get('in_target_cust', '')}</td></tr>
                        <tr><th>수익 모델</th><td>{data.get('in_revenue_model', '')}</td></tr>
                        <tr><th>향후 계획</th><td>{data.get('in_future_plan', '')}</td></tr>
                    </table>
                </div>

                <div class="box">
                    <h3>진단 요약</h3>
                    <table>
                        <tr><th>최근 매출</th><td>{calc_recent_sales(data):,}만원</td></tr>
                        <tr><th>총 부채</th><td>{calc_total_debt(data):,}만원</td></tr>
                        <tr><th>보유 인증</th><td>{certs}</td></tr>
                        <tr><th>특허 여부</th><td>{data.get('in_has_patent', '없음')}</td></tr>
                        <tr><th>수출 여부</th><td>{data.get('in_export_revenue', '없음')}</td></tr>
                        <tr><th>조달 필요 자금</th><td>{safe_int(data.get('in_req_funds')):,}만원</td></tr>
                    </table>
                </div>

                <div class="box" style="color:#b91c1c;">
                    AI 오류 내용: {str(e)}
                </div>
            </div>
        </body>
        </html>
        """
        return fallback_html


# =========================================================
# 6. Page Setup / Style
# =========================================================
st.set_page_config(page_title="AI 컨설팅 시스템", layout="wide")

st.markdown("""
<style>
    [data-testid="stWidgetLabel"] p {
        font-weight: 400 !important;
        font-size: 14px !important;
        color: #31333F !important;
        margin-bottom: 2px !important;
    }
    h2 {
        font-weight: 700 !important;
        margin-top: 25px !important;
    }
    input::placeholder, textarea::placeholder {
        font-size: 0.85em !important;
        color: #888 !important;
    }
    [data-testid="stCheckbox"] label p {
        font-size: 18px !important;
        font-weight: 500 !important;
        color: #333 !important;
    }
    .summary-box-compact {
        background-color: #E8F5E9;
        padding: 12px;
        border-radius: 10px;
        height: 145px;
        border: 1px solid #ddd;
        text-align: center;
        display: flex;
        flex-direction: column;
        justify-content: center;
        margin-top: 25px;
    }
    .score-result-box {
        background-color: #F1F8E9;
        padding: 12px;
        border-radius: 10px;
        height: 145px;
        border: 1px solid #C8E6C9;
        text-align: center;
        display: flex;
        flex-direction: column;
        justify-content: center;
        margin-top: 25px;
    }
    .result-title {
        font-size: 18px !important;
        font-weight: 700 !important;
        color: #2E7D32;
        margin-bottom: 5px !important;
    }
    .blue-bold-label-16 {
        color: #1E88E5 !important;
        font-size: 16px !important;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

init_session()

# =========================================================
# 7. Sidebar
# =========================================================
st.sidebar.header("⚙️ AI 엔진 설정")

saved_settings = st.session_state["settings"]
current_provider = saved_settings.get("provider", "gemini")
if current_provider not in MODEL_OPTIONS:
    current_provider = "gemini"

provider = st.sidebar.selectbox(
    "Provider",
    options=list(MODEL_OPTIONS.keys()),
    index=list(MODEL_OPTIONS.keys()).index(current_provider)
)

model_list = MODEL_OPTIONS[provider]
saved_model = saved_settings.get("model", model_list[0])
if saved_model not in model_list:
    saved_model = model_list[0]

model = st.sidebar.selectbox(
    "Model",
    options=model_list,
    index=model_list.index(saved_model)
)

api_key = st.sidebar.text_input(
    "API Key",
    value=saved_settings.get("api_key", ""),
    type="password"
)

if st.sidebar.button("💾 저장", use_container_width=True):
    save_settings(provider, api_key, model)
    st.session_state["settings"] = load_settings()
    st.sidebar.success("저장 완료")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("📁 업체 관리")
tab_save, tab_load = st.sidebar.tabs(["💾 저장하기", "📂 불러오기"])

with tab_save:
    if st.button("현재 정보 저장", use_container_width=True):
        c_name = st.session_state.get("in_company_name", "").strip()
        if c_name:
            current_data = get_current_company_data()
            st.session_state["company_list"][c_name] = current_data
            save_companies(st.session_state["company_list"])
            st.session_state["selected_company_name"] = c_name
            st.success(f"'{c_name}' 저장 완료!")
        else:
            st.error("기업명을 입력하세요.")

with tab_load:
    company_names = list(st.session_state["company_list"].keys())
    if company_names:
        default_idx = 0
        if st.session_state["selected_company_name"] in company_names:
            default_idx = company_names.index(st.session_state["selected_company_name"])

        target = st.selectbox("업체 선택", options=company_names, index=default_idx)
        if st.button("데이터 불러오기", use_container_width=True):
            loaded = st.session_state["company_list"][target]
            apply_company_data(loaded)
            st.session_state["selected_company_name"] = target
            st.success(f"'{target}' 불러오기 완료!")
            st.rerun()
    else:
        st.info("저장된 업체가 없습니다.")

st.sidebar.markdown("---")
st.sidebar.header("🚀 리포트 생성")

s_modes = ["REPORT", "MATCHING", "LOAN_PLAN", "AI_PLAN"]
s_labels = [
    "📊 AI 기업분석리포트",
    "💡 AI 정책자금 매칭",
    "📝 기관별 융자/사업계획서",
    "📑 AI 사업계획서"
]

for i in range(4):
    if st.sidebar.button(s_labels[i], key=f"side_{i}", use_container_width=True):
        st.session_state["view_mode"] = s_modes[i]
        st.rerun()

# =========================================================
# 8. Main Top Area
# =========================================================
st.title("📊 AI 컨설팅 대시보드")

t_cols = st.columns(4)
for i in range(4):
    if t_cols[i].button(s_labels[i], key=f"top_{i}", use_container_width=True, type="primary"):
        st.session_state["view_mode"] = s_modes[i]
        st.rerun()

st.markdown("<hr style='margin-top:0;'>", unsafe_allow_html=True)

GUIDE_STR = "1억=10000으로 입력"

# =========================================================
# 9. Input Screen
# =========================================================
if st.session_state["view_mode"] == "INPUT":
    st.header("1. 기업현황")
    c1_f1 = st.columns([2, 1, 1.5, 1.5])
    with c1_f1[0]:
        st.text_input("기업명", key="in_company_name")
    with c1_f1[1]:
        st.radio("사업자유형", ["개인", "법인"], horizontal=True, key="in_biz_type")
    with c1_f1[2]:
        st.text_input("사업자번호", key="in_raw_biz_no", placeholder="000-00-00000")
    with c1_f1[3]:
        st.text_input("법인등록번호", key="in_raw_corp_no", placeholder="000000-0000000")

    c1_f2 = st.columns([1, 1, 1, 1])
    with c1_f2[0]:
        st.text_input("사업개시일", key="in_start_date", placeholder="YYYY.MM.DD")
    with c1_f2[1]:
        st.text_input("사업장 전화번호", key="in_biz_tel", placeholder="000-00-0000")
    with c1_f2[2]:
        st.text_input("이메일 주소", key="in_email_addr", placeholder="example@email.com")
    with c1_f2[3]:
        st.selectbox("현사업장 업종", ["제조업", "서비스업", "IT업", "도소매업", "건설업", "기타"], key="in_industry")

    c1_f3 = st.columns([1.2, 3, 0.9, 0.9])
    with c1_f3[0]:
        st.radio("사업장 임대여부", ["자가", "임대"], horizontal=True, key="in_lease_status")
    with c1_f3[1]:
        st.text_input("사업장 주소", key="in_biz_addr", placeholder="소재지를 입력하세요")
    with c1_f3[2]:
        st.number_input("보증금 (만원)", key="in_lease_deposit", step=1, placeholder=GUIDE_STR, value=None)
    with c1_f3[3]:
        st.number_input("월임대료 (만원)", key="in_lease_rent", step=1, placeholder=GUIDE_STR, value=None)

    c1_f4 = st.columns([1.2, 3, 1.8])
    with c1_f4[0]:
        st.radio("추가 사업장 여부", ["없음", "있음"], horizontal=True, key="in_has_extra_biz")
    with c1_f4[1]:
        st.text_input("추가사업장 정보입력", key="in_extra_biz_info", placeholder="사업장명/사업자등록번호")
    with c1_f4[2]:
        st.empty()
    st.markdown("---")

    st.header("2. 대표자 정보")
    c2r1 = st.columns([1, 1, 1, 1])
    with c2r1[0]:
        st.text_input("대표자명", key="in_rep_name")
    with c2r1[1]:
        st.text_input("생년월일", key="in_rep_dob")
    with c2r1[2]:
        st.text_input("연락처", key="in_rep_phone")
    with c2r1[3]:
        st.selectbox("통신사", ["선택", "SKT", "KT", "LGU+", "알뜰폰"], key="in_rep_carrier")

    c2r2 = st.columns([2, 1, 1])
    with c2r2[0]:
        st.text_input("거주지 주소", key="in_home_addr")
    with c2r2[1]:
        st.radio("거주지 상태", ["자가", "임대"], horizontal=True, key="in_home_status")
    with c2r2[2]:
        st.multiselect("부동산 보유현황", ["아파트", "빌라", "토지", "공장", "임야"], key="in_real_estate")

    c2r3 = st.columns([0.8, 0.8, 1.2, 1.2])
    with c2r3[0]:
        st.selectbox("최종학력", ["선택", "중졸", "고졸", "대졸", "석사", "박사"], key="in_edu_level")
    with c2r3[1]:
        st.text_input("전공", key="in_rep_major")
    with c2r3[2]:
        st.text_input("경력사항 1", key="in_rep_career_1")
    with c2r3[3]:
        st.text_input("경력사항 2", key="in_rep_career_2")
    st.markdown("---")

    st.header("3. 대표자 신용정보")
    c3_col1, c3_col2, c3_col3 = st.columns([1.5, 1.3, 1.8])
    with c3_col1:
        l_r1 = st.columns(2)
        l_r1[0].radio("금융연체여부", ["없음", "있음"], horizontal=True, key="in_fin_delinquency")
        l_r1[1].radio("세금체납여부", ["없음", "있음"], horizontal=True, key="in_tax_delinquency")
        l_r2 = st.columns(2)
        s_kcb = l_r2[0].number_input("KCB 점수", key="in_kcb_score", step=1, value=None)
        s_nice = l_r2[1].number_input("NICE 점수", key="in_nice_score", step=1, value=None)

    with c3_col2:
        vk, vn = safe_int(s_kcb), safe_int(s_nice)
        if st.session_state.get("in_fin_delinquency") == "있음" or st.session_state.get("in_tax_delinquency") == "있음":
            status = "🔴 진행 위험"
        elif vk > 700 or vn > 700:
            status = "🟢 진행 원활"
        else:
            status = "🟡 진행 주의"

        st.markdown(
            f'<div class="summary-box-compact"><p style="font-weight:700;">신용상태요약</p><p style="font-size:1.45em; font-weight:800;">{status}</p></div>',
            unsafe_allow_html=True
        )

    with c3_col3:
        kg, kc = get_kcb_grade(vk)
        ng, nc = get_nice_grade(vn)
        res_c1, res_c2 = st.columns(2)
        with res_c1:
            st.markdown(
                f'<div class="score-result-box"><p class="result-title">KCB 결과</p><p style="font-size:1.8em; font-weight:800; color:{kc};">{vk}점</p><p>{kg}</p></div>',
                unsafe_allow_html=True
            )
        with res_c2:
            st.markdown(
                f'<div class="score-result-box"><p class="result-title">NICE 결과</p><p style="font-size:1.8em; font-weight:800; color:{nc};">{vn}점</p><p>{ng}</p></div>',
                unsafe_allow_html=True
            )
    st.markdown("---")

    st.header("4. 매출현황")
    exp_cols = st.columns(2)
    with exp_cols[0]:
        has_exp = st.radio("수출매출 여부", ["없음", "있음"], horizontal=True, key="in_export_revenue")
    with exp_cols[1]:
        st.radio("수출예정 여부", ["없음", "있음"], horizontal=True, key="in_planned_export")

    mc = st.columns(4)
    m_keys = [("금년 매출", "in_sales_cur"), ("25년 매출", "in_sales_25"), ("24년 매출", "in_sales_24"), ("23년 매출", "in_sales_23")]
    for i, (t, k) in enumerate(m_keys):
        mc[i].number_input(f"{t} (만원)", key=k, step=1, placeholder=GUIDE_STR, value=None)

    if has_exp == "있음":
        st.markdown("<p style='font-size:14px; font-weight:600;'>[수출매출 상세역사]</p>", unsafe_allow_html=True)
        ec = st.columns(4)
        e_keys = [("금년 수출액", "in_exp_cur"), ("25년 수출액", "in_exp_25"), ("24년 수출액", "in_exp_24"), ("23년 수출액", "in_exp_23")]
        for i, (t, k) in enumerate(e_keys):
            ec[i].number_input(f"{t} (만원)", key=k, step=1, placeholder=GUIDE_STR, value=None)
    st.markdown("---")

    st.header("5. 부채현황")
    debt_items = [
        ("중진공", "in_debt_kosme"),
        ("소진공", "in_debt_semas"),
        ("신보", "in_debt_kodit"),
        ("기보", "in_debt_kibo"),
        ("재단", "in_debt_foundation"),
        ("회사담보", "in_debt_corp_coll"),
        ("대표신용", "in_debt_rep_cred"),
        ("대표담보", "in_debt_rep_coll")
    ]
    for r in range(0, 8, 4):
        cols = st.columns(4)
        for i in range(4):
            cols[i].number_input(f"{debt_items[r+i][0]} (만원)", key=debt_items[r+i][1], step=1, placeholder=GUIDE_STR, value=None)
    st.markdown("---")

    st.header("6. 보유 인증")
    for i in range(0, 8, 4):
        cols = st.columns(4)
        for j in range(4):
            if i + j < len(CERT_LIST):
                cols[j].checkbox(CERT_LIST[i+j], key=f"in_cert_{i+j}")
    st.markdown("---")

    st.header("7. 특허 및 정부지원")
    c7 = st.columns(2)
    with c7[0]:
        st.radio("특허 보유 여부", ["없음", "있음"], horizontal=True, key="in_has_patent")
        st.number_input("보유 건수", key="in_pat_cnt", step=1, value=None)
        st.text_area("특허 상세 내용", key="in_pat_desc")
    with c7[1]:
        st.radio("정부지원 수혜이력", ["없음", "있음"], horizontal=True, key="in_has_gov")
        st.number_input("수혜 건수", key="in_gov_cnt", step=1, value=None)
        st.text_area("수혜 사업명 상세", key="in_gov_desc")
    st.markdown("---")

    st.header("8. 비즈니스 상세 정보")
    r8_1 = st.columns(2)
    with r8_1[0]:
        st.text_area("핵심 아이템", key="in_item_desc", height=100, placeholder="제품/서비스 기능 상세")
    with r8_1[1]:
        st.text_area("판매 루트(유통망)", key="in_sales_route", height=100, placeholder="주요 거래처 및 채널")
    r8_2 = st.columns(2)
    with r8_2[0]:
        st.text_area("경쟁력 및 차별성", key="in_item_diff", height=100, placeholder="타사 대비 강점")
    with r8_2[1]:
        st.text_area("시장 현황", key="in_market_status", height=100, placeholder="업계 분위기")
    r8_3 = st.columns(2)
    with r8_3[0]:
        st.text_area("공정도", key="in_process_desc", height=100, placeholder="생산 과정 요약")
    with r8_3[1]:
        st.text_area("타겟 고객", key="in_target_cust", height=100, placeholder="주요 구매층")
    r8_4 = st.columns(2)
    with r8_4[0]:
        st.text_area("수익 모델", key="in_revenue_model", height=100, placeholder="매출 발생 구조")
    with r8_4[1]:
        st.text_area("앞으로의 계획", key="in_future_plan", height=100, placeholder="향후 목표")
    st.markdown("---")

    st.header("9. 자금 계획")
    c9 = st.columns([1, 2])
    with c9[0]:
        st.markdown('<p class="blue-bold-label-16">이번 조달 필요 자금 (만원)</p>', unsafe_allow_html=True)
        st.number_input("조달금액", key="in_req_funds", label_visibility="collapsed", step=1, placeholder=GUIDE_STR, value=None)
    with c9[1]:
        st.markdown('<p style="font-size:14px;">상세 자금 집행 계획</p>', unsafe_allow_html=True)
        st.text_area("자금집행", key="in_fund_plan", label_visibility="collapsed")

    st.markdown("---")

    current_data = get_current_company_data()
    policy = calc_policy_score(current_data)
    guarantee = estimate_guarantee(current_data)

    st.subheader("실시간 자동 진단 요약")
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("정책자금 점수", f"{policy['score']}점")
    g2.metric("정책자금 등급", policy["grade"])
    g3.metric("보증 확률", f"{guarantee['probability']}%")
    g4.metric("보증 판단", guarantee["label"])

# =========================================================
# 10. Report Screen
# =========================================================
else:
    if st.button("⬅️ 입력 화면으로 돌아가기"):
        st.session_state["view_mode"] = "INPUT"
        st.rerun()

    current_data = get_current_company_data()
    mode = st.session_state["view_mode"]
    biz_name = current_data.get("in_company_name", "미입력")
    settings = st.session_state["settings"]

    if not settings.get("api_key", ""):
        st.error("사이드바에서 API Key를 먼저 저장해 주세요.")
    elif not biz_name or biz_name == "미입력":
        st.warning("기업 정보를 입력하고 저장/불러오기 후 다시 시도해 주세요.")
    else:
        with st.status("🚀 AI 리포트 생성 중..."):
            res_html = generate_ai_report(settings, current_data, mode)
            components.html(res_html, height=1200, scrolling=True)
